"""识别引擎：从提取结果中认出元器件型号、数量、柜体尺寸、柜型、铜排需求。

原则：只输出图纸上真实出现的型号。认不准的标 qty_conf=low 或 model=""，
交给人工复核，绝不凭经验补型号。
"""
import argparse
import re

from common import (copper_spec_by_current, copper_weight_kg, detect_voltage_class,
                    parse_cabinet_size, read_json, setup_stdout, write_json)

# ---------------- 元器件型号模式库 ----------------
# 每条: (类别, 名称, 正则, 单位)
# 正则只匹配"型号前缀+参数"，向右扩展由 _expand 负责
PATTERNS = [
    ("断路器", "微型断路器",
     r"(?:MCB(?!C)|iC65[A-Z]{0,3}|C65[A-Z]{0,3}|EA9[A-Z]{0,3}|SH20\d|GSH20\d|S20\d|DZ47[A-Z]{0,3}|NXB-?\d+|CDB[6A]?[A-Z]?|5SJ\d+|5SY\d+|iDPN[NV]?|C120[A-Z]?|A9[A-Z]?\d*)",
     "只"),
    ("断路器", "塑壳断路器",
     r"(?:MCCB|CM[135][A-Z]?-\d+|NSX\d+[A-Z]?|NSE\d+[A-Z]?|EZD\d+[A-Z]?|CVS\d+[A-Z]?|XT[1-4][A-Z]?\d*|Tmax\s?X?T?\d*|CDM[13][A-Z]?-\d+|NM1-\d+|NXM-\d+|DZ20[YJ]?-\d+|NS\d{2,3}[A-Z]?)",
     "只"),
    ("断路器", "框架断路器",
     r"(?:ACB|CW[123]-\d+|E[1-6][A-Z]?\s?\d{3,4}|MVS\d+|MT\d+[A-Z]?|NA1-\d+|DW45-\d+|DW15-\d+|DW10-\d+|DW16-\d+|DW17-\d+|IZM\d+)",
     "台"),
    ("接触器", "交流接触器",
     r"(?:LC1[DK]\d+|LC2[DK]\d+|AX\d+|AF\d*|A\d{2,3}(?![0-9])|CJX2-?\d+|CJ20-\d+|NXC-?\d+|3RT\d+|3TF\d+)",
     "只"),
    ("继电器", "热过载继电器",
     r"(?:LRD\d+|LRE\d+|LR3D\d+|TA\d+DU|TA25DU|NR2-?\d+|NR4-\d+|JR36-\d+|3RU\d+)",
     "只"),
    ("继电器", "中间继电器",
     r"(?:RXM\d+[A-Z]*|RXG\d+|CR-M\d+|MY\d+[A-Z]?|LY\d+[A-Z]?|3TH\d+|JZX-?\d+)",
     "只"),
    ("开关", "双电源自动转换开关",
     r"(?:WTS-[A-Z]?\d+[A-Z/]*|WATSN[A-Z]?-?\d+|CAP1-\d+|QTS\d+|ATS\d+|NH40-\d+)",
     "台"),
    ("开关", "隔离开关",
     r"(?:INT\d+[A-Z/]*|OT\d+[A-Z]*|INS\d+|NH40-\d+|HD\d+-\d+|HS\d+-\d+|QSA\d+|WG\d+)",
     "只"),
    ("互感器", "电流互感器",
     r"(?:LMZ[J1]?-?\d*[A-Z]*|LZZBJ\d+-\d+|BH-?\d+|SDH-?\d+|AKH-?\d+|CT\s?\d+/\d+)",
     "只"),
    ("仪表", "多功能电力仪表",
     r"(?:KWH\+?|PZ\d+-[A-Z0-9]+|PMC\d+[A-Z]*|ACR\d+[A-Z]*|DTSD\d+|DTS\d+|PD\d{3})",
     "台"),
    ("保护", "浪涌保护器",
     r"(?:OVR\s?\d*[A-Z]*|LiGZ[A-Z0-9]*|LiD\d+X?\d*|D40X?\d*|SPD\d*|FLT-?\d+)",
     "套"),
    ("保护", "熔断器",
     r"(?:RT18-?\d+|RT16-?\d+|NT\d+|RL\d+-\d+|FUSE\s?\d+)",
     "只"),
    ("补偿", "电力电容器",
     r"(?:BSMJ[\d\.\-]+|BKMJ[\d\.\-]+|BZMJ[\d\.\-]+|RMF\d+)",
     "只"),
    ("启动", "软启动器",
     r"(?:JJR\d+|STR\d+|ATS48D\d+|SS\d+)",
     "台"),
    ("变频", "变频器",
     r"(?:ATV\d+[A-Z]*|FR-[A-Z]?\d+|ACS\d+|MM\d+|VFD\d+)",
     "台"),
]

# 型号前缀 → 品牌（顺序敏感，长前缀在前）
BRANDS = [
    ("iC65", "施耐德"), ("C65", "施耐德"), ("EA9", "施耐德"), ("NSX", "施耐德"),
    ("NSE", "施耐德"), ("EZD", "施耐德"), ("CVS", "施耐德"), ("LC1", "施耐德"),
    ("LC2", "施耐德"), ("LRD", "施耐德"), ("LRE", "施耐德"), ("RXM", "施耐德"),
    ("INT", "施耐德"), ("WTS", "施耐德万高"), ("WATSN", "施耐德万高"),
    ("ATV", "施耐德"), ("MVS", "施耐德"), ("MT", "施耐德"),
    ("SH20", "ABB"), ("GSH20", "ABB"), ("S20", "ABB"), ("XT1", "ABB"),
    ("XT2", "ABB"), ("XT3", "ABB"), ("XT4", "ABB"), ("Tmax", "ABB"),
    ("AX", "ABB"), ("AF", "ABB"), ("TA", "ABB"), ("CR-M", "ABB"), ("OT", "ABB"),
    ("5SJ", "西门子"), ("5SY", "西门子"), ("3RT", "西门子"), ("3TF", "西门子"),
    ("3RU", "西门子"), ("3TH", "西门子"),
    ("NXB", "正泰"), ("NXC", "正泰"), ("NR2", "正泰"), ("NM1", "正泰"),
    ("NXM", "正泰"), ("DZ47", "正泰"), ("CJX2", "正泰"), ("RT18", "正泰"),
    ("BSMJ", "正泰"), ("PZ", "正泰"),
    ("CDM", "德力西"), ("CDB", "德力西"), ("CJ20", "德力西"),
    ("CM1", "常熟开关"), ("CW1", "常熟开关"), ("CW2", "常熟开关"),
    ("NA1", "人民电器"), ("DW45", "人民电器"),
    ("LMZ", "国产"), ("BH-", "国产"),
]

UNIT_WORDS = ("只", "台", "个", "套", "块", "根", "组", "件")

# 柜号：AA1 / AP-01 / 1#柜 / AL1
CABINET_RE = re.compile(
    r"^\s*(?:([A-Z]{1,4}[-]?\d{1,3})|(\d{1,2})\s*#\s*(?:柜|箱)?|([A-Z]{1,3}\d{1,3})柜)\s*$"
)


def detect_brand(model):
    up = model.upper()
    for p, b in BRANDS:
        if up.startswith(p.upper()):
            return b
    return ""


_SPEC_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9/\-\.×]{1,10}")


def _is_spec_token(tok):
    """规格 token：必须同时含字母和数字（40KA/TM100/3P），纯数字是数量不能并。"""
    has_a = any(c.isalpha() and c.isascii() for c in tok)
    has_d = any(c.isdigit() for c in tok)
    return has_a and has_d and len(tok) <= 10


def _expand(text, start, end, max_chars=26):
    """从型号匹配处向右扩展，把 -C20A/2P、TM100 3P、40KA 这类后缀吃进来。"""
    out = text[start:end]
    i = end
    while i < len(text) and len(out) < max_chars:
        ch = text[i]
        if ch in " \t":
            m = _SPEC_TOKEN.match(text, i + 1)
            if not m:
                break
            tok = m.group(0)
            if _is_spec_token(tok) and len(out) + 1 + len(tok) <= max_chars:
                out += " " + tok
                i = m.end()
                continue
            break
        if ch in "-/×xX*." or ch.isalnum():
            out += ch
            i += 1
            continue
        break
    return out.strip()


def find_models(line):
    """返回 [(类别, 名称, 型号, 单位, span_start, span_end)]"""
    found, used = [], []
    for cat, name, pat, unit in PATTERNS:
        for m in re.finditer(pat, line, re.I):
            s, e = m.span()
            if any(s < ue and e > us for us, ue in used):
                continue
            model = _expand(line, s, e)
            if len(model) < 3:
                continue
            e2 = s + len(model)
            # 互感器变比（75/5、100/5）是选型关键参数，单独并回来
            if cat == "互感器":
                m2 = re.match(r"\s+(\d{1,5}/\d{1,2})\b", line[e2:])
                if m2:
                    model += " " + m2.group(1)
                    e2 += len(m2.group(0))
            used.append((s, e2))
            found.append((cat, name, model, unit, s, e2))
    found.sort(key=lambda x: x[4])
    return found


def guess_qty(line, span_end, unit):
    """在同一行里猜数量：优先取单位词前面的整数，其次取型号后第一个 1-3 位整数。"""
    tail = line[span_end:]
    m = re.search(r"(\d{1,3})\s*(" + "|".join(UNIT_WORDS) + ")", tail)
    if m:
        return int(m.group(1)), "high"
    m = re.search(r"^\D{0,8}?(\d{1,3})\b", tail)
    if m:
        return int(m.group(1)), "medium"
    return 1, "low"


_CAB_CODE_RE = re.compile(r"\b([A-Z]{1,4}-?\d{1,3})\b")


def _guess_cabinet_id(lines):
    """从标题行（含"柜/箱"）里捞柜号，如 '低压配电柜 AP-01' → AP-01。"""
    for ln in lines[:40]:
        if "柜" not in ln and "箱" not in ln:
            continue
        m = _CAB_CODE_RE.search(ln.upper())
        if m:
            code = m.group(1)
            # 排除把型号当柜号（如 KYN28、GGD）
            if not re.match(r"^(KYN|XGN|GGD|GCK|GCS|MNS|XL|PZ|HXGN)", code):
                return code
    return ""


def split_cabinets(rows):
    cabinets, cur = [], None
    for r in rows:
        txt = r.get("text", "").strip()
        if not txt:
            continue
        m = CABINET_RE.match(txt)
        if m and len(txt) <= 10:
            cid = (m.group(1) or m.group(3) or (m.group(2) + "#柜")).replace(" ", "")
            cur = {"id": cid, "rows": []}
            cabinets.append(cur)
            continue
        if cur is None:
            cur = {"id": "全部", "rows": []}
            cabinets.append(cur)
        cur["rows"].append(r)
    return cabinets or [{"id": "全部", "rows": rows}]


# ---------------- 原理图图块识别（首选路径） ----------------
# 电气原理图/系统图上，每个元器件是一个图块（INSERT）。
# 统计图块引用次数 = 真实数量；就近匹配文字标注 = 型号。
# 这比从全图文字里猜数量可靠得多。
ELEC_LAYER_KEYS = ("系统", "原理", "控制", "电气")
EXCLUDE_LAYER_KEYS = ("平面", "导线", "图框", "轴线", "COLUMN", "AXIS", "BXT",
                      "文字", "DIM", "标注", "TEXT", "填充", "HATCH")


def _collect(extract, key):
    """兼容两种结构：单文件（顶层有 inserts/texts）与多文件合并（files 数组）。"""
    files = extract.get("files")
    if files:
        out = []
        for f in files:
            out.extend(f.get(key, []))
        return out
    return list(extract.get(key, []))


def extract_by_blocks(extract, max_dist=900.0):
    """按图块识别元器件。返回 (items, stats)。"""
    inserts = _collect(extract, "inserts")
    texts = _collect(extract, "texts")
    if not inserts or not texts:
        return [], {"blocks": 0, "matched": 0, "reason": "无图块或无文字"}

    cand = [i for i in inserts
            if any(k in i.get("layer", "") for k in ELEC_LAYER_KEYS)
            and not any(k in i.get("layer", "") for k in EXCLUDE_LAYER_KEYS)]

    items, matched = [], 0
    for ins in cand:
        best, best_d = None, max_dist
        for t in texts:
            dx = t["x"] - ins["x"]
            dy = t["y"] - ins["y"]
            d = (dx * dx + dy * dy) ** 0.5
            if d >= best_d:
                continue
            if not find_models(t["text"]):
                continue
            best_d, best = d, t["text"]
        if not best:
            continue
        matched += 1
        # 一个标注通常只对应一个型号，取第一个
        found = find_models(best)
        if not found:
            continue
        cat, name, model, unit, _, _ = found[0]
        items.append({
            "cabinet": "全部",
            "category": cat, "name": name, "model": model,
            "brand": detect_brand(model), "unit": unit,
            "qty": 1, "qty_conf": "high",
            "source": "原理图图块",
            "evidence": f"图块 {ins['block']}@{ins['layer']}",
        })

    items = merge_duplicates(items)
    return items, {"blocks": len(cand), "matched": matched,
                   "total_inserts": len(inserts)}


# ---------------- 型号规范化：只写通用代号，不带厂家系列 ----------------
# 实际订货可能换牌，型号里保留厂家系列会锁死供应商。
# 微断统一 MCB，塑壳统一 MCCB，框架统一 ACB，规格参数原样保留。
# 用映射表而非正则替换：正则会吃掉壳架数字（NSX100N -> MCCB，丢了 100N）。
_SERIES_MAP = {
    # 微型断路器
    "IC65N": "MCB", "IC65H": "MCB", "IC65L": "MCB", "IC65": "MCB",
    "C65N": "MCB", "C65H": "MCB", "C65": "MCB",
    "EA9": "MCB", "SH200": "MCB", "GSH200": "MCB", "S200": "MCB", "S20": "MCB",
    "5SJ": "MCB", "5SY": "MCB", "DZ47": "MCB", "NXB": "MCB", "CDB": "MCB",
    "IDPN": "MCB", "C120": "MCB", "A9": "MCB",
    # 塑壳断路器
    "CM1": "MCCB", "CM3": "MCCB", "CM5": "MCCB",
    "NSX": "MCCB", "NSE": "MCCB", "EZD": "MCCB", "CVS": "MCCB",
    "XT1": "MCCB", "XT2": "MCCB", "XT3": "MCCB", "XT4": "MCCB", "XT": "MCCB",
    "TMAX": "MCCB", "CDM1": "MCCB", "CDM3": "MCCB", "NM1": "MCCB",
    "NXM": "MCCB", "DZ20": "MCCB", "NS": "MCCB",
    # 框架断路器
    "CW1": "ACB", "CW2": "ACB", "CW3": "ACB",
    "MVS": "ACB", "MT": "ACB", "NA1": "ACB",
    "DW45": "ACB", "DW15": "ACB", "DW16": "ACB", "DW17": "ACB", "DW10": "ACB",
    "E1N": "ACB", "E2N": "ACB", "E2S": "ACB", "E3N": "ACB", "E3S": "ACB",
    "E4S": "ACB", "E6H": "ACB",
}
_SERIES_SORTED = sorted(_SERIES_MAP, key=len, reverse=True)


# 塑壳壳架电流后的分断等级字母 M/L/H（如 250M/3300 -> 250/3300）。
# B/C/D 曲线字母、N/S 等级不动；只动 M/L/H 且后接斜杠（避免误删其它字母）。
_RATING_LETTER = re.compile(r"(?<=\d)[MLH](?=/)")


def _strip_rating_letter(m):
    return _RATING_LETTER.sub("", m)


def to_generic_model(model):
    """把厂家系列型号换成通用代号，保留规格参数，并去掉 M/L/H 分断等级字母。

    CM3-250M/3300      -> MCCB-250/3300
    NSX100N TM100 3P   -> MCCB-100N TM100 3P
    iC65N-C20A/2P      -> MCB-C20A/2P
    CW3-1600/3         -> ACB-1600/3
    已是 MCB/MCCB/ACB 开头的同样走剥离 + 连字符规范化。
    """
    if not model:
        return model
    m = str(model).strip()
    up = m.upper()
    if up.startswith(("MCB", "MCCB", "ACB")):
        raw = m
    else:
        raw = m
        for series in _SERIES_SORTED:
            if up.startswith(series):
                rest = m[len(series):].lstrip("-— ").strip()
                tag = _SERIES_MAP[series]
                raw = f"{tag}-{rest}" if rest else tag
                break
    return _strip_rating_letter(raw)


def breaking_capacity(model):
    """断路器极限分断能力（按用户规则）：
    MCB          -> 10kA
    MCCB         -> >50kA
    ACB In<=2500 -> 65kA ；In>2500 -> 85kA
    """
    m = (model or "").upper()
    if "ACB" in m:
        mm = re.search(r"ACB-?\s*0*(\d+)", m)
        if mm:
            In = int(mm.group(1))
            return "65kA" if In <= 2500 else "85kA"
        return "65kA"
    if "MCCB" in m:
        return ">50kA"
    if "MCB" in m:
        return "10kA"
    return ""


def extract_items(extract):
    rows = extract.get("rows", [])
    lines = [r.get("text", "") for r in rows if r.get("text")]
    all_text = "\n".join(lines)

    # 图块名也当型号来源（DXF 里常直接以型号命名块）
    block_hits = {}
    for ins in _collect(extract, "inserts"):
            blk = ins.get("block", "")
            if blk in block_hits:
                continue
            for cat, name, model, unit, _, _ in find_models(blk):
                block_hits[blk] = (cat, name, model, unit)
                break

    voltage = detect_voltage_class(all_text)
    size = parse_cabinet_size(lines)
    cabinets = split_cabinets(rows)
    # 单柜图纸没有独立柜号行时，从标题里捞一个柜号，别一律写"全部"
    if len(cabinets) == 1 and cabinets[0]["id"] == "全部":
        cid = _guess_cabinet_id(lines)
        if cid:
            cabinets[0]["id"] = cid

    items, warnings = [], []

    # ---- 路径 1（首选）：原理图图块识别 ----
    block_items, bstats = extract_by_blocks(extract)

    # ---- 路径 2（补充）：文字扫描（材料表、系统图标注、控制原理图）----
    text_items = []
    for cab in cabinets:
        for r in cab["rows"]:
            line = r.get("text", "")
            for cat, name, model, unit, s, e in find_models(line):
                qty, conf = guess_qty(line, e, unit)
                text_items.append({
                    "cabinet": cab["id"],
                    "category": cat,
                    "name": name,
                    "model": model,
                    "brand": detect_brand(model),
                    "unit": unit,
                    "qty": qty,
                    "qty_conf": conf,
                    "source": r.get("file", ""),
                    "evidence": line[:80],
                })

    # ---- 路径 3（兜底）：块名本身即型号 ----
    block_name_items = []
    for blk in block_hits:
        cat, name, model, unit = block_hits[blk]
        cnt = sum(1 for ins in _collect(extract, "inserts") if ins.get("block") == blk)
        if cnt:
            block_name_items.append({
                "cabinet": cabinets[0]["id"] if len(cabinets) == 1 else "全部",
                "category": cat, "name": name, "model": model,
                "brand": detect_brand(model), "unit": unit,
                "qty": cnt, "qty_conf": "high",
                "source": "图块名", "evidence": f"图块 {blk} ×{cnt}",
            })

    # ---- 合并：图块识别为准，文字/块名补充未覆盖的型号 ----
    if block_items:
        seen = {i["model"].upper() for i in block_items}
        items = list(block_items)
        for it in text_items + block_name_items:
            if it["model"].upper() not in seen:
                seen.add(it["model"].upper())
                items.append(it)
        warnings.append(
            f"已按原理图图块识别：电气图层图块 {bstats['blocks']} 个，"
            f"匹配到型号 {bstats['matched']} 个，生成 {len(block_items)} 种物料；"
            f"其余 {len(items) - len(block_items)} 项来自图纸文字（材料表/标注）补充。"
        )
    else:
        items = text_items + block_name_items
        if text_items or block_name_items:
            warnings.append("未识别到原理图图块，已退回文字扫描模式，数量置信度偏低。")

    # 型号规范化：统一成通用代号（MCB/MCCB/ACB），去掉厂家系列，便于订货换牌
    for it in items:
        it["model"] = to_generic_model(it["model"])

    items = merge_duplicates(items)

    # 断路器统一计算极限分断能力（塑壳剥掉 M/L/H 后只注明 kA 数值）
    for it in items:
        if it["model"].upper().startswith(("MCB", "MCCB", "ACB")) or "断路" in it["name"]:
            it["breaking_capacity"] = breaking_capacity(it["model"])

    if not items:
        warnings.append("未识别到任何元器件型号。请检查：图纸是否为扫描件、型号是否在图块属性里、或需人工录入。")
    low = [i for i in items if i["qty_conf"] == "low"]
    if low:
        warnings.append(f"{len(low)} 项数量置信度低，必须人工核对。")

    return {
        "voltage_class": voltage,
        "cabinet_size": {"w": size[0], "h": size[1], "d": size[2], "basis": size[3]} if size else None,
        "cabinets": [{"id": c["id"], "rows": len(c["rows"])} for c in cabinets],
        "items": items,
        "warnings": warnings,
        "text_lines": len(lines),
    }


def merge_duplicates(items):
    """同柜号 + 同型号合并数量；数量置信度取最低。"""
    order = {"high": 3, "medium": 2, "low": 1}
    merged = {}
    for it in items:
        key = (it["cabinet"], it["model"].upper())
        if key in merged:
            m = merged[key]
            m["qty"] += it["qty"]
            if order[it["qty_conf"]] < order[m["qty_conf"]]:
                m["qty_conf"] = it["qty_conf"]
            if it["evidence"] not in m["evidence"]:
                m["evidence"] = (m["evidence"] + " | " + it["evidence"])[:120]
        else:
            merged[key] = dict(it)
    return list(merged.values())


# ---------------- 铜排推算 ----------------

def _find_bus_current(lines, items):
    """找主母排额定电流：显式标注 > 进线开关额定电流。"""
    for ln in lines:
        m = re.search(r"(?:主母排|母线|In|Ie|额定电流)[^\d]{0,8}(\d{2,4})\s*A", ln, re.I)
        if m:
            return int(m.group(1)), f"图纸标注：{ln[:40]}"
    best = 0
    for it in items:
        if it["category"] in ("断路器", "开关"):
            nums = [int(x) for x in re.findall(r"(\d{2,4})", it["model"])]
            for n in nums:
                if 16 <= n <= 6300 and n > best:
                    best = n
    if best:
        return best, f"按进线开关最大额定电流推定（{best}A）"
    return 0, "未找到额定电流"


def derive_copper(items, size, cab_count, lines):
    current, basis = _find_bus_current(lines, items)
    if not current:
        return [], ["铜排：未找到主母排电流，无法推算，需人工填写"]

    spec, area = copper_spec_by_current(current)
    w = size[0] if size else 800
    # 双排/三排写法 2×(100×10) 才是多股，普通 50×6 是单根
    m = re.match(r"TMY-(\d)×\(", spec)
    strands = int(m.group(1)) if m else 1

    # 每柜主母排：3相 + N + PE = 5 根，长度 = 柜宽 + 搭接余量 0.3m
    per_cab_len = round((w + 300) / 1000, 2)
    total_len = round(per_cab_len * 5 * cab_count, 2)
    weight = copper_weight_kg(total_len, area, strands)

    rows = [{
        "name": "主母排", "spec": spec, "length_m": total_len,
        "weight_kg": weight, "qty": cab_count,
        "basis": f"{basis}；按 {cab_count} 柜 × 5 根(3P+N+PE) × (柜宽{w}+搭接300mm) 推算",
    }]

    # 分支排估算：按回路数 × 0.8m
    branches = len([i for i in items if i["category"] in ("断路器", "开关")])
    if branches:
        bl = round(branches * 0.8, 2)
        bspec, barea = copper_spec_by_current(max(63, current // max(branches, 1)))
        rows.append({
            "name": "分支排", "spec": bspec, "length_m": bl,
            "weight_kg": copper_weight_kg(bl, barea, 1), "qty": branches,
            "basis": f"按 {branches} 个开关回路 × 0.8m 估算（粗估，需按实际排布复核）",
        })

    return rows, [f"铜排为推算值，非图纸标注，报价前请复核：{basis}"]


# ---------------- 柜体部件 ----------------

def cabinet_parts(size, cab_count, voltage, has_meter=True):
    """按柜型/尺寸生成标准柜体部件清单（数量为估算，需复核）。"""
    w, h, d = (size or (800, 2200, 600))
    per = []
    per.append(("柜体", "柜架（C型材/8MF）", f"{w}×{h}×{d}", "套", 1, "按柜数"))
    per.append(("柜体", "前门板", f"{w}×{h}", "块", 1, "1 块/柜"))
    per.append(("柜体", "后门板/封板", f"{w}×{h}", "块", 1, "1 块/柜"))
    per.append(("柜体", "侧板", f"{d}×{h}", "块", 2, "2 块/柜（边柜）"))
    per.append(("柜体", "顶板", f"{w}×{d}", "块", 1, "1 块/柜"))
    per.append(("柜体", "底板", f"{w}×{d}", "块", 1, "1 块/柜"))
    per.append(("柜体", "安装板", f"{w-80}×{h-200}", "块", 1, "1 块/柜"))
    per.append(("柜体", "门锁", "MS818/AB301", "把", 1, "1 把/柜"))
    per.append(("柜体", "铰链", "CL201-1", "只", 4, "4 只/柜"))
    per.append(("绝缘", "母线框", "按母排规格", "套", 1, "1 套/柜"))
    per.append(("绝缘", "支撑绝缘子", "MNS-40×40", "只", 6, "按母排长度估"))
    per.append(("辅材", "铜排热缩管", "φ按排宽", "m", round((w + 300) / 1000 * 5, 1), "同母排长度"))
    per.append(("辅材", "行线槽", "40×40", "m", 6, "按柜深估算"))
    per.append(("辅材", "接地铜排", "TMY-30×4", "m", 2, "2m/柜"))
    per.append(("辅材", "标牌/标记号", "标准", "套", 1, "1 套/柜"))
    per.append(("辅材", "紧固件", "标准件", "套", 1, "1 套/柜"))
    per.append(("照明", "柜内照明灯", "LED-5W", "套", 1, "1 套/柜"))
    per.append(("照明", "门开关", "LX19-001", "只", 1, "1 只/柜"))
    if voltage == "低压":
        per.append(("温控", "加热器", "50W", "只", 1, "1 只/柜"))
        per.append(("温控", "温湿度控制器", "WK-1", "只", 1, "1 只/柜"))
        per.append(("温控", "轴流风机", "φ120", "只", 2, "2 只/柜"))
    else:
        per.append(("温控", "加热器", "100W", "只", 2, "高压柜 2 只/柜"))
        per.append(("温控", "温湿度控制器", "WK-2", "只", 1, "1 只/柜"))
        per.append(("温控", "带电显示装置", "DXN-10", "套", 1, "高压柜必备"))

    out = []
    for cat, name, spec, unit, qty, basis in per:
        out.append({
            "category": cat, "name": name, "model": spec, "unit": unit,
            "qty": qty * cab_count, "basis": f"{basis} × {cab_count} 柜",
            "qty_conf": "medium",
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("extract", help="extract.json")
    ap.add_argument("--out", default="work/items.json")
    ap.add_argument("--cabinet-name", default="", help="强制单柜名（如 AP-01）")
    a = ap.parse_args()

    ext = read_json(a.extract)
    res = extract_items(ext)
    lines = [r.get("text", "") for r in ext.get("rows", [])]

    size = res["cabinet_size"]
    size_t = (size["w"], size["h"], size["d"]) if size else None
    cab_count = max(1, len(res["cabinets"]))
    if a.cabinet_name:
        for c in res["cabinets"]:
            c["id"] = a.cabinet_name
        for it in res["items"]:
            it["cabinet"] = a.cabinet_name

    copper, cwarn = derive_copper(res["items"], size_t, cab_count, lines)
    res["copper"] = copper
    res["cabinet_parts"] = cabinet_parts(size_t, cab_count, res["voltage_class"])
    res["warnings"].extend(cwarn)

    write_json(a.out, res)

    print(f"柜型判定：{res['voltage_class']}")
    if size:
        print(f"柜体尺寸：{size['w']}×{size['h']}×{size['d']} mm（{size['basis']}）")
    else:
        print("柜体尺寸：未识别")
    print(f"柜数：{cab_count}  识别元器件：{len(res['items'])} 项")
    for it in res["items"][:15]:
        print(f"  [{it['cabinet']}] {it['name']:<12} {it['model']:<22} {it['qty']:>3}{it['unit']}  ({it['qty_conf']})")
    if len(res["items"]) > 15:
        print(f"  ... 共 {len(res['items'])} 项")
    if res["warnings"]:
        print("\n[!] 需注意：")
        for w in res["warnings"]:
            print(f"  - {w}")
    print(f"\n-> {a.out}")


if __name__ == "__main__":
    setup_stdout()
    main()
