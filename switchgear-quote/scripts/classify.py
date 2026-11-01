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
     r"(?:MCB(?!C)|iC65[A-Z]{0,3}|C65[A-Z]{0,3}|EA9[A-Z]{0,3}|CH3[A-Z]?-\d+|SH20\d|GSH20\d|S20\d|DZ47[A-Z]{0,3}|NXB-?\d+|CDB[6A]?[A-Z]?|5SJ\d+|5SY\d+|iDPN[NV]?|C120[A-Z]?|A9[A-Z]?\d*)",
     "只"),
    ("断路器", "塑壳断路器",
     r"(?:MCCB|CM[135][A-Z]?-\d+|NSX\d+[A-Z]?|NSE\d+[A-Z]?|EZD\d+[A-Z]?|CVS\d+[A-Z]?|XT[1-4][A-Z]?\d*|Tmax\s?X?T?\d*|CDM[13][A-Z]?-\d+|NM1-\d+|NXM-\d+|DZ20[YJ]?-\d+|NS\d{2,3}[A-Z]?)",
     "只"),
    ("断路器", "框架断路器",
     r"(?:ACB|CW[123]-\d+|E[1-6][A-Z]?\s?\d{3,4}|MVS\d+|MT\d+[A-Z]?|NA1-\d+|DW45-\d+|DW15-\d+|DW10-\d+|DW16-\d+|DW17-\d+|IZM\d+)",
     "台"),
    ("接触器", "交流接触器",
     r"(?:LC1[DK]\d+|LC2[DK]\d+|AX\d+|AF\d+|A\d{3}(?![0-9])|CJX2-?\d+|CJ20-\d+|NXC-?\d+|3RT\d+|3TF\d+)",
     "只"),
    ("继电器", "热过载继电器",
     r"(?:LRD\d+|LRE\d+|LR3D\d+|TA\d+DU|TA25DU|NR2-?\d+|NR4-\d+|JR36-\d+|3RU\d+)",
     "只"),
    ("继电器", "中间继电器",
     r"(?:RXM\d+[A-Z]*|RXG\d+|CR-M\d+|MY\d+[A-Z]?|LY\d+[A-Z]?|3TH\d+|JZX-?\d+)",
     "只"),
    ("控制电器", "指示灯",
     r"(?:CJK22-DP|AD16-\d+[A-Z]*|ND16-\d+[A-Z]*|XB2-[A-Z]+\d+)",
     "只"),
    ("控制电器", "电位器",
     r"(?:LA42DWQ-?\d+|WXD\d+-?\d*|RV24YN\d*)",
     "只"),
    ("控制电器", "按钮",
     r"(?:CJK22-[A-Z]+|LA\d+[A-Z]*-?[A-Z]?|XB2-[A-Z]+\d+)",
     "只"),
    ("控制电器", "万能转换开关",
     r"(?:LW\d+[A-Z]?-?\d*|K1-\d+)",
     "只"),
    ("控制电器", "电位器",
     r"(?:LA42DWQ-?\d+|WXD\d+-?\d*|RV24YN\d*)",
     "只"),
    ("控制电器", "端子",
     r"(?:UK\d+[A-Z]*|SAK\d+[A-Z]*|TBR\d+)",
     "个"),
    ("测量与控制", "温度控制器",
     r"(?:TL5K[A-Z]?-?[A-Z0-9]*|WK-?\d+|KTS\d+)",
     "套"),
    ("测量与控制", "电子表",
     r"(?:PZ\d+[A-Z]?)",
     "只"),
    ("测量与控制", "信号变送器",
     r"(?:BM-[A-Z]+/?[A-Z]*|MINI MCR-[A-Z0-9-]+)",
     "只"),
    ("开关", "双电源自动转换开关",
     r"(?:WTS-[A-Z]?\d+[A-Z/]*|WATSN[A-Z]?-?\d+|CAP1-\d+|QTS\d+|ATS\d+|NH40-\d+)",
     "台"),
    ("开关", "隔离开关",
     r"(?:INT\d+[A-Z/]*|OT\d+[A-Z]*|INS\d+|NH40-\d+|HD\d+-\d+|HS\d+-\d+|QSA\d+|WG\d+|HR\d+-\d+)",
     "只"),
    ("互感器", "电流互感器",
     r"(?:LMZ[J1]?-?\d*[A-Z]*|LZZBJ\d+-\d+|BH-?\d+|SDH-?\d+|AKH-?\d+|CT\s?\d+/\d+)",
     "只"),
    ("仪表", "多功能电力仪表",
     r"(?:KWH\+?|PMC\d+[A-Z]*|ACR\d+[A-Z]*|AEM\d+|DTSD\d+|DTS\d+|PD\d{3})",
     "台"),
    ("保护", "马达保护器",
     r"(?:ST5\d{2}|MPR-?\d+|PMC-?\d{3}|3UF\d+|EOCR[A-Z]*|LDS-?\d+|EMR-?\d+)",
     "只"),
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

# ---------------- 四类元器件的标准型号写法（用户规则表，2026-11-01 定稿） ----------------
# 型号规格 = 技术要求描述（不写品牌具体型号，便于比价换牌）；
# 备注 = 配件/说明，辅助填写型号用，禁止并入型号规格。
STANDARD_MODELS = {
    "变频器": {
        "model": "V/F控制。过载能力150%，持续时间60s。额定输入输出电压/频率：AC 0-400V三相电压，频率0~60Hz。绝缘电压AC690V。二次控制回路工作电压AC220V。电机调速范围0-6000转。防护等级：IP20，柜内壁挂安装。选配2路4-20mA输入信号，选配2路4-20mA输出信号。选配操作器柜门嵌入式套件+中文液晶面板。",
        "note": "一个变频器配4个中间继电器、2个保险丝、30个UK3.0端子、3个CJK22-DP指示灯、2个信号变送器",
    },
    "马达保护器": {
        "model": "额定电流参考功率的2.5倍。电源电压：AC220V。含零序互感器。过载保护：指定脱扣等级（Class 20）。堵转保护：设定电流倍数（4-8倍In）和动作时间0.2s。不平衡/断相保护：设定不平衡度阈值（>40%）和动作时间。接地/漏电保护：设定动作电流值（0.1A,0.3A,1A）和时间。欠载保护：设定电流百分比（40%In）和动作延时。控制输出：继电器输出容量（用于控制接触器），几组常开/常闭点。通信接口：Profibus-DP。显示与操作：本地数码管/LCD显示单元，带按键编程。模拟量输出：4-20mA电流输出，对应实际电流。故障记录：记录历史故障信息。结构形式：分体式（显示单元与电流互感器分离）。",
        "note": "一个马保配4个中间继电器、4个保险丝、25个UK3.0端子、2个CJK22-DP指示灯、对应塑壳断路器含报警辅助点和合闸辅助点",
    },
    "软启动器": {
        "model": "额定工作电压：AC380V（常规）。控制电源：AC220V/AC380V/DC24V。结构形式：旁路外置。防护等级：IP20（柜内）。安装方式：柜装式IP3X。启动方式：电压斜坡/限流启动/转矩控制。停车方式：自由停车/软停车/泵控停车（防水锤）。模拟量：4～20mA（调速/限流）。通讯接口：RS485-Modbus。过流、过载、缺相、相序保护。过压、欠压、过热保护。堵转、短路、三相不平衡保护。本地显示面板。",
        "note": "一个软启动器配4个中间继电器、2个保险丝、30个UK3.0端子、3个CJK22-DP指示灯、2个信号变送器",
    },
    "多功能电力仪表": {
        "model": "多功能表。3*AC400V三相四线，辅助电源AC220V。壁挂安装，外径96*96，安装开孔91*91。全电量测量（电压、电流、有功功率、无功功率、功率因素等）。采样精度0.5级，数据采集完整性率≧99%。通过酸雾实验并提供型式试验报告复件。通信规约modbus rtu。",
        "note": "配4个熔断器",
    },
    "温度控制器": {
        "model": "TL5K-S1TC+温度传感器",
        "note": "含温控器、温湿度控制器。每一台电容柜都有一只",
    },
    "信号变送器": {
        "model": "BM-DI/II AC230V 1路4-20mA输入 2路4-20mA输出",
        "note": "信号放大器、隔离变送器",
    },
}


def _power_prefix(line):
    """从图纸标注提取电机功率，生成型号前缀：适配电机功率 7.5kW。"""
    m = re.search(r"(\d+(?:\.\d+)?)\s*[kK][wW]", str(line or ""))
    return f"适配电机功率 {m.group(1)}kW。" if m else ""


def spd_rule_model(model):
    """浪涌按规则表：SPD-T1/SR/4P（配 SCB 后备保护）。"""
    m = re.search(r"T(\d)", str(model or ""), re.I)
    t = m.group(1) if m else "2"
    return f"SPD-T{t}/SR/4P（配 SCB 后备保护）"

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

# IEC 元件代号 / 相线 / 端子，绝不能当柜号（KA2 继电器、SB1 按钮、L1 相线…）
_ELEM_CODE = re.compile(
    r"^(?:KA|KM|KT|KV|SB|SA|SQ|SE|SF|HG|HR|HW|HL|HY|GN|QF|QS|QC|FU|FA|TA|CT|PT|TV|"
    r"DI|DO|AI|AO|PI|PO|WK|WL|WN|GND|AK|BT|BR|WS|WT|WH|AC|DC|EL|PG|PS|PU|QC)\d",
    re.I)
_SINGLE_LETTER = re.compile(r"^[A-Z]\d{1,3}$", re.I)   # A2 / L1 / D01，柜号至少两位字母


def _is_cabinet_code(code):
    """柜号判定：排除元件代号、相线、单字母端子、以及本身是型号的串。"""
    if not code:
        return False
    if _ELEM_CODE.match(code) or _SINGLE_LETTER.match(code):
        return False
    return not find_models(code)


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


# ---- 型号串裁剪：空格后的 token 若属以下情况，说明型号已结束，不能再并 ----
_LOOP_TAG = re.compile(r"^W[KL]\d*$", re.I)                 # 回路标注 WK2 / WL1
_SHORT_LOOP_TAG = re.compile(r"^[A-Z]{2}\d{1,2}$", re.I)    # 回路标注 AJ1 / KM2（TM100 是3位，不受影响）
_CURRENT_ONLY = re.compile(r"^\d{1,4}\s*A$", re.I)           # 纯电流 65A（重复标注）
_NEW_MODEL_LIKE = re.compile(r"^[A-Z]{2,}\d*[A-Z]?[-\s]")    # 另一个型号起始 CW3- / CH3N-


def _starts_another_model(tok):
    """token 是否已是另一个元器件的型号开头。

    防止 ACB-1600/3 CW3-1600/3、MCCB-250/33002 CH3N-63/3P 这类
    「一行里叠写两个型号」被并成一个。
    """
    for _cat, _name, pat, _unit in PATTERNS:
        if re.match(pat, tok, re.I):
            return True
    return bool(_NEW_MODEL_LIKE.match(tok))


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
            # 三道停止条件：回路号 / 重复电流 / 下一个型号
            if _LOOP_TAG.match(tok) or _SHORT_LOOP_TAG.match(tok):
                break
            if _CURRENT_ONLY.match(tok) and re.search(r"\d+\s*A", out):
                break
            if _starts_another_model(tok):
                break
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


# DXF 匿名块名常是 GUID（a30-40cc-83dc-68ab58568b66），不能当型号
_GUID_LIKE = re.compile(r"^[0-9a-f]{2,}-[0-9a-f]{2,}(?:-[0-9a-f]{2,}){2,}$", re.I)


def find_models(line):
    """返回 [(类别, 名称, 型号, 单位, span_start, span_end)]"""
    if _GUID_LIKE.match(line.strip()):
        return []
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
            # 排除把柜型当柜号（KYN28、GGD），以及 KA2/SB1 这类元件代号
            if (not re.match(r"^(KYN|XGN|GGD|GCK|GCS|MNS|XL|PZ|HXGN)", code)
                    and _is_cabinet_code(code)):
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
            # 只有真柜号才切分；KA2/SB1/L1 这类元件代号继续当普通行
            if _is_cabinet_code(cid):
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


_CT_RATIO = re.compile(r"^\d{2,5}\s*/\s*\d{1,2}$")


def extract_by_blocks(extract, max_dist=1200.0):
    """按图块识别元器件。返回 (items, stats)。

    匹配优先级：型号标注 > 纯变比标注（2000/5 → 电流互感器）。
    一个图块 = 1 个元器件；同型号的多个图块由 merge_duplicates 累加数量。
    """
    inserts = _collect(extract, "inserts")
    texts = _collect(extract, "texts")
    if not inserts or not texts:
        return [], {"blocks": 0, "matched": 0, "reason": "无图块或无文字"}

    cand = [i for i in inserts
            if any(k in i.get("layer", "") for k in ELEC_LAYER_KEYS)
            and not any(k in i.get("layer", "") for k in EXCLUDE_LAYER_KEYS)]

    # 预计算每段文字的型号，避免 图块数×文字数 次重复正则
    text_models = {}
    for t in texts:
        key = t["text"]
        if key not in text_models:
            text_models[key] = find_models(key)

    # 柜号标注坐标（只认真柜号），图块按最近柜号归柜
    cab_marks = []
    for t in texts:
        s = t["text"].strip()
        if len(s) <= 10:
            m = CABINET_RE.match(s)
            if m:
                cid = (m.group(1) or m.group(3) or (m.group(2) + "#柜")).replace(" ", "")
                if _is_cabinet_code(cid):
                    cab_marks.append((t["x"], t["y"], cid))

    def _nearest_cab(ins):
        if not cab_marks:
            return "全部"
        return min(cab_marks, key=lambda c: (c[0] - ins["x"]) ** 2 + (c[1] - ins["y"]) ** 2)[2]

    items, matched = [], 0
    for ins in cand:
        best, best_d = None, max_dist
        ratio, ratio_d = None, max_dist
        for t in texts:
            dx = t["x"] - ins["x"]
            dy = t["y"] - ins["y"]
            d = (dx * dx + dy * dy) ** 0.5
            if d >= max_dist:
                continue
            if text_models.get(t["text"]):
                if d < best_d:
                    best_d, best = d, t["text"]
            elif d < ratio_d and _CT_RATIO.match(t["text"].strip()):
                ratio_d, ratio = d, t["text"].strip()
        if best:
            matched += 1
            cat, name, model, unit, _, _ = text_models[best][0]
            items.append({
                "cabinet": _nearest_cab(ins),
                "category": cat, "name": name, "model": model,
                "brand": detect_brand(model), "unit": unit,
                "qty": 1, "qty_conf": "high",
                "source": "原理图图块",
                "evidence": f"图块 {ins['block']}@{ins['layer']}",
            })
        elif ratio:
            # 纯变比标注（2000/5）没有型号前缀，按电流互感器处理
            matched += 1
            items.append({
                "cabinet": _nearest_cab(ins),
                "category": "互感器", "name": "电流互感器",
                "model": f"CT-{ratio}", "brand": "",
                "unit": "只", "qty": 1, "qty_conf": "medium",
                "source": "原理图图块",
                "evidence": f"图块 {ins['block']}@{ins['layer']} 变比 {ratio}",
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


def mccb_rule_model(line, base=""):
    """按用户规则表生成塑壳断路器完整写法（配电保护 / 电动机保护两种）。

    MCCB/3P In=250A。配电保护 Ue=AC400V,Ui=AC690V。Icu≧50kA。脱扣曲线 10-20倍In。固定式板前安装。
    """
    m_in = re.search(r"In\s*=\s*(\d{2,4})\s*A", line, re.I) or re.search(r"(\d{2,4})\s*A", line)
    in_val = m_in.group(1) if m_in else ""
    is_motor = bool(re.search(r"电动机保护|电机保护|马达保护", line))
    prot = "电动机保护" if is_motor else "配电保护"
    curve = "12-20倍In" if is_motor else "10-20倍In"
    m_p = re.search(r"/(\d)P", base or "", re.I)
    poles = (m_p.group(1) + "P") if m_p else "3P"
    in_part = f"In={in_val}A" if in_val else "In=  A"
    return (f"MCCB/{poles} {in_part}。{prot} Ue=AC400V,Ui=AC690V。"
            f"Icu≧50kA。脱扣曲线 {curve}。固定式板前安装。")


def breaking_capacity(model):
    """断路器极限分断能力（按用户规则）：MCB Icu≧10kA；MCCB Icu≧50kA；ACB 65/85kA。"""
    m = (model or "").upper()
    if "ACB" in m:
        mm = re.search(r"ACB-?\s*0*(\d+)", m)
        if mm:
            In = int(mm.group(1))
            return "Icu≧65kA" if In <= 2500 else "Icu≧85kA"
        return "Icu≧65kA"
    if "MCCB" in m:
        return "Icu≧50kA"
    if "MCB" in m:
        return "Icu≧10kA"
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
        # 塑壳按规则表完整写法（区分配电保护/电动机保护，含 In 与 Icu）
        if it.get("name") == "塑壳断路器":
            it["model"] = mccb_rule_model(it.get("evidence", ""), it["model"])
        # 中间继电器按规则表带底座
        if it.get("name") == "中间继电器" and "底座" not in it["model"]:
            it["model"] = f"{it['model']}+底座"
        # 浪涌按规则表带 SCB 后备保护
        if it.get("name") == "浪涌保护器":
            it["model"] = spd_rule_model(it["model"])
        # 电动机保护的塑壳 = 马保配套开关，辅助点直接写入型号（不进备注）
        if it.get("name") == "塑壳断路器" and "电动机保护" in it["model"]:
            it["model"] = it["model"].rstrip("。") + "。含报警辅助点和开关辅助点。"
        # 四类按用户规则表统一写法：型号=技术要求描述，备注=配件说明（不并入型号）
        std = STANDARD_MODELS.get(it.get("name", ""))
        if std:
            it["model"] = std["model"]
            it["note"] = std["note"]
            # 变频器/软启动：型号带图纸实际功率（功率按图纸，不写死）
            if it["name"] in ("变频器", "软启动器"):
                p = _power_prefix(it.get("evidence", ""))
                if p:
                    it["model"] = p + it["model"]

    items = merge_duplicates(items)

    # 断路器统一计算极限分断能力（塑壳剥掉 M/L/H 后只注明 kA 数值）
    for it in items:
        if it["model"].upper().startswith(("MCB", "MCCB", "ACB")) or "断路" in it["name"]:
            it["breaking_capacity"] = breaking_capacity(it["model"])

    # 柜号清单以实际出现为准（文字分柜 + 图块归柜两条来源合并）
    seen_ids = {c["id"] for c in cabinets}
    for it in items:
        if it["cabinet"] not in seen_ids:
            seen_ids.add(it["cabinet"])
            cabinets.append({"id": it["cabinet"], "rows": []})

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
    """找主母排额定电流：显式母排标注 > 框架断路器(进线) > 其他断路器最大值。

    注意：不能用任意 In= 标注，那是支路电流（塑壳/微断），会把主母排算小。
    """
    # 1) 显式主母排/母线标注
    for ln in lines:
        m = re.search(r"(?:主母排|母线槽|母线)[^\d]{0,8}(\d{2,4})\s*A", ln, re.I)
        if m:
            return int(m.group(1)), f"图纸标注：{ln[:40]}"

    # 2) 框架断路器（进线开关）额定电流
    best = 0
    for it in items:
        model = str(it.get("model", ""))
        if "ACB" in model.upper() or it.get("name") == "框架断路器":
            for n in re.findall(r"(\d{3,4})", model):
                n = int(n)
                if 100 <= n <= 6300 and n > best:
                    best = n
    if best:
        return best, f"按框架断路器额定电流（{best}A）"

    # 3) 其他断路器最大值兜底
    for it in items:
        if it.get("category") in ("断路器", "开关"):
            for n in re.findall(r"(\d{3,4})", str(it.get("model", ""))):
                n = int(n)
                if 16 <= n <= 6300 and n > best:
                    best = n
    if best:
        return best, f"按开关最大额定电流推定（{best}A）"
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

    # 接地铜排（PE 排）：每柜 2m，TMY-30×4，计入铜排总量（不单列辅材）
    pe_len = round(2 * cab_count, 2)
    rows.append({
        "name": "接地铜排", "spec": "TMY-30×4", "length_m": pe_len,
        "weight_kg": copper_weight_kg(pe_len, 30 * 4, 1), "qty": cab_count,
        "basis": f"按 {cab_count} 柜 × 2m/柜 估算",
    })

    return rows, [f"铜排为推算值，非图纸标注，报价前请复核：{basis}"]


# ---------------- 柜体部件 ----------------

def detect_cabinet_type(lines):
    """识别柜体型号：MNS抽屉式 / MNS固定式 / XL-21 / JXF / GGD。

    MNS 默认抽屉式（MNS 系统以抽屉为主）；识别不到返回空串。
    """
    text = "\n".join(lines).upper()
    if "MNS" in text:
        if re.search(r"MNS[^\n]{0,12}固定", text):
            return "MNS固定式"
        return "MNS抽屉式"
    if re.search(r"XL-?21", text):
        return "XL-21"
    if "JXF" in text:
        return "JXF"
    if "GGD" in text:
        return "GGD"
    return ""


def cabinet_parts(size, cab_count, voltage, cab_type="", has_meter=True):
    """按柜型/尺寸生成柜体、风机、温湿度传感器与辅材总成（数量为估算，需复核）。

    规则（用户指定，固定型号不再改）：
    - 柜体作为整体一行，型号只写「尺寸 + 柜体型号」，不写含件明细；
    - 柜体风机单独列项，固定型号 ZL-805+200FZY2-D AC220V；
    - 温湿度传感器单独列项，固定型号 TL5K-S1TC+温度传感器；
    - 其余辅材合并为一项「其他辅材（总成）」，型号直接写「若干」；
    - 接地铜排由 derive_copper 计入铜排总量。
    """
    w, h, d = (size or (800, 2200, 600))
    cab_model = f"{cab_type} {w}×{h}×{d}" if cab_type else f"{w}×{h}×{d}"
    per = [
        ("柜体", "柜体（整体）", cab_model, "套", 1, "1 套/柜"),
        ("辅材", "柜体风机", "ZL-805+200FZY2-D AC220V", "套", 2, "2 套/柜（规则表）"),
        ("辅材", "温湿度传感器", "TL5K-S1TC+温度传感器", "套", 1, "1 套/柜"),
        ("辅材", "其他辅材（总成）", "若干", "套", 1, "1 套/柜"),
    ]
    if voltage != "低压":
        per.append(("辅材", "带电显示装置", "DXN-10", "套", 1, "高压柜必备"))

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
    ap.add_argument("--cabinet-type", default="",
                    help="强制柜体型号：XL-21 / JXF / GGD / MNS抽屉式 / MNS固定式")
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
    cab_type = a.cabinet_type or detect_cabinet_type(lines)
    res["cabinet_type"] = cab_type
    res["cabinet_parts"] = cabinet_parts(size_t, cab_count, res["voltage_class"], cab_type)
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
