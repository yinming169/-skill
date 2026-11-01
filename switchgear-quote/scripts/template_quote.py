"""按用户标准「分项报价表」格式（6 列）生成材料清单，并自动配齐配套件。

标准格式（样例见 assets/标准参考格式.xlsx）：
    第1行  标题「分项报价表」（A:F 合并）
    第2行  项目名称（A:F 合并）
    第3行  表头：序号 | 名 称（元器件） | 型 号 规 格 | 单位 | 数量 | 备注
    第4行  设备名称（A:C 合并） | 台 | 柜数
    明细行  序号 | 名称 | 型号规格 | 单位 | 数量 | 备注
    壳体行  序号 | 壳体(W*L*H): | 规格 | 台 | 1 | 品牌
    汇总行  材料小计 / 制造费 / 利润 / 税费 / 产品报价（单位=台）
    序号连续编号（汇总行也占号）。

用法:
    python template_quote.py <源清单.xlsx> --out <新清单.xlsx>

逻辑:
    1. 解析源表（兼容 6 列标准格式 与 8 列含单价/金额格式）
    2. 按 accessory_rules.json 计算每柜应配附件
    3. 与原表已有数量比对，只补差额（不重复计算）
    4. 新增行紧跟触发设备插入
    5. 每柜输出一张「分项报价表」，附「配套核对表」
"""
import argparse
import json
import os
import re

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side

FONT_NAME = "宋体"
FONT_SZ = 11
THIN = Side(style="thin", color="000000")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
COL_W = {"A": 5.6, "B": 18.1, "C": 30.7, "D": 5.6, "E": 5.7, "F": 12.3}
ROW_H = {"title": 25, "project": 25, "header": 25, "cab": 25, "data": 25}
SUB_TOTAL_KEYS = ("小计", "合计")
SUMMARY_LABELS = ("材料小计", "制造费", "利润", "税费", "产品报价")
SHELL_KEY = "壳体"
HEADERS = ["序号", "名 称（元器件）", "型 号 规 格", "单位", "数量", "备注"]


def _to_int(v):
    if v is None or v == "":
        return 0
    try:
        return int(float(str(v)))
    except Exception:
        m = re.search(r"\d+", str(v))
        return int(m.group(0)) if m else 0


# ---------- 解析源表 ----------
def _is_cab_row(row):
    a, b, d = row[0].value, row[1].value, row[3].value
    return (isinstance(a, str) and a.strip()
            and str(d).strip() == "台"
            and not (b is not None and str(b).strip()))


def _is_header_row(row):
    a, b = row[0].value, row[1].value
    if isinstance(a, str) and a.strip() == "序号":
        return True
    return isinstance(b, str) and "名" in b and "称" in b


def _is_summary_row(row):
    b = row[1].value
    if not isinstance(b, str):
        return False
    b = b.strip()
    return any(k in b for k in SUMMARY_LABELS) or any(k in b for k in SUB_TOTAL_KEYS)


def parse_workbook(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=False)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=8))
    n = len(rows)

    title = rows[0][0].value if n else ""
    project = rows[1][0].value if n > 1 else ""

    # 备注列：表头 F 为「备注」→ 第 6 列；为「单价/金额」→ 无备注列
    remark_col = 5
    for row in rows:
        if row[0].value is not None and str(row[0].value).strip() == "序号":
            f = row[5].value if len(row) > 5 else None
            f = str(f).strip() if f is not None else ""
            if "备注" in f:
                remark_col = 5
            elif "单价" in f or "金额" in f:
                remark_col = None
            break

    cabinets, i = [], 0
    while i < n:
        if _is_cab_row(rows[i]):
            cab = {"name": str(rows[i][0].value).strip(),
                   "count": _to_int(rows[i][4].value) or 1,
                   "items": []}
            i += 1
            while i < n:
                if _is_cab_row(rows[i]) or _is_summary_row(rows[i]):
                    break
                if _is_header_row(rows[i]):
                    i += 1
                    continue
                name = rows[i][1].value
                if name and str(name).strip():
                    cab["items"].append({
                        "name": str(name).strip(),
                        "model": str(rows[i][2].value).strip() if rows[i][2].value else "",
                        "unit": str(rows[i][3].value).strip() if rows[i][3].value else "",
                        "qty": _to_int(rows[i][4].value),
                        "remark": (str(rows[i][remark_col].value).strip()
                                   if remark_col is not None and rows[i][remark_col].value else ""),
                    })
                i += 1
            if cab["items"]:
                cabinets.append(cab)
        else:
            i += 1
    return {"title": title, "project": project, "cabinets": cabinets}


# ---------- 规则引擎 ----------
def load_rules(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _match(name, rule, opts):
    for kw in rule.get("trigger", []):
        if kw not in name:
            continue
        for ex in rule.get("exclude", []):
            if ex in name:
                return False
        if rule.get("id") == "switch" and opts.get("exclude_mcb_from_switch"):
            if any(m in name for m in ("微型断路器", "MCB")):
                return False
        return True
    return False


def plan_cabinet(cab, cfg):
    """返回 {items: 已配齐的行, added: 新增行, report: 核对行}"""
    rules = cfg["rules"]
    opts = cfg.get("options", {})

    # 1) 打补丁：变频器规格未写明模拟量要求时追加
    items = [dict(it) for it in cab["items"]]
    for it in items:
        for rule in rules:
            if not rule.get("patch_model") or not _match(it["name"], rule, opts):
                continue
            m = it["model"]
            patch = rule["patch_model"]
            if patch in m:
                continue
            # 原文已含 2 路模拟量/4-20mA 说明的，不再重复追加
            if "4-20mA" in m or "模拟量" in m or ("2路" in m and "输入" in m and "输出" in m):
                continue
            it["model"] = m.rstrip("。，、；") + "，" + patch

    # 2) 统计应配
    agg = {}   # (name, model) -> {qty, pos, rule}
    for idx, it in enumerate(items):
        for rule in rules:
            if not _match(it["name"], rule, opts):
                continue
            for add in rule["add"]:
                key = (add["name"], add["model"])
                rec = agg.setdefault(key, {"qty": 0, "pos": -1, "rule": set(), "unit": add["unit"]})
                rec["qty"] += add["per"] * it["qty"]
                rec["pos"] = max(rec["pos"], idx)
                rec["rule"].add(rule["id"])

    # 3) 与原表比对：原表有这行就补数量，没有才新增行
    added, report = [], []
    for (name, model), rec in agg.items():
        same = [x for x in items if name in x["name"]]
        have = sum(x["qty"] for x in same)
        delta = rec["qty"] - have
        report.append({"name": name, "model": model, "need": rec["qty"],
                       "have": have, "add": max(0, delta),
                       "rule": "/".join(sorted(rec["rule"]))})
        if delta <= 0:
            continue
        if same:
            target = same[0]
            target["qty"] += delta
            target["is_changed"] = True
            target["delta"] = delta
        else:
            added.append((rec["pos"], {
                "name": name, "model": model, "unit": rec["unit"],
                "qty": delta, "is_new": True,
            }))

    # 4) 按位置插入（同位置保持稳定顺序）
    added.sort(key=lambda x: x[0])
    out, offset = list(items), 0
    last_pos, block = -2, []
    merged = []
    for pos, row in added:
        if pos != last_pos:
            if block:
                merged.append((last_pos, block))
            block, last_pos = [], pos
        block.append(row)
    if block:
        merged.append((last_pos, block))

    for pos, rows in reversed(merged):
        out[pos + 1:pos + 1] = rows  # 保持规则内的先后顺序

    report = [r for r in report if r["need"] > 0]
    return {"items": out, "added": [r for _, rows in merged for r in rows], "report": report}


# ---------- 写表 ----------
def _style(ws, r, c, value=None, bold=False, align="center"):
    cell = ws.cell(row=r, column=c, value=value)
    cell.font = Font(name=FONT_NAME, size=FONT_SZ, bold=bold)
    cell.border = BORDER
    cell.alignment = Alignment(horizontal=align, vertical="center", wrap_text=True)
    return cell


def _sheet_name(name, idx, total):
    if total == 1 and name in ("设备名称", "", "柜名"):
        return "分项报价表"
    safe = re.sub(r"[\[\]:*?/\\]", "", name).strip() or f"柜{idx}"
    return safe[:31]


def write_cabinet_sheet(ws, title, project, cab, plan):
    for k, v in COL_W.items():
        ws.column_dimensions[k].width = v

    ws.merge_cells("A1:F1")
    c = ws.cell(row=1, column=1, value=title or "分项报价表")
    c.font = Font(name="黑体", size=14, bold=True)
    c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = ROW_H["title"]

    ws.merge_cells("A2:F2")
    c = ws.cell(row=2, column=1, value=project or "项目名称：")
    c.font = Font(name=FONT_NAME, size=12, bold=True)
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[2].height = ROW_H["project"]

    for i, h in enumerate(HEADERS, start=1):
        _style(ws, 3, i, h)
    ws.row_dimensions[3].height = ROW_H["header"]

    ws.merge_cells(start_row=4, start_column=1, end_row=4, end_column=3)
    _style(ws, 4, 1, cab["name"], align="left")
    _style(ws, 4, 4, "台")
    _style(ws, 4, 5, cab["count"])
    _style(ws, 4, 6, None)
    ws.row_dimensions[4].height = ROW_H["cab"]

    items = plan["items"]
    shell_items = [it for it in items if SHELL_KEY in it["name"]]
    body = [it for it in items if SHELL_KEY not in it["name"]]

    r, seq = 5, 0
    for it in body:
        seq += 1
        _style(ws, r, 1, seq)
        _style(ws, r, 2, it["name"], align="left", bold=bool(it.get("is_new")))
        _style(ws, r, 3, it["model"], align="left")
        _style(ws, r, 4, it["unit"])
        c = _style(ws, r, 5, it["qty"])
        if it.get("is_changed"):
            c.font = Font(name=FONT_NAME, size=FONT_SZ, bold=True, color="C00000")
        _style(ws, r, 6, it.get("remark", ""))
        ws.row_dimensions[r].height = ROW_H["data"]
        r += 1

    # 壳体行：取源表壳体项放到明细末尾；源表没有则补占位行
    if shell_items:
        for sh in shell_items:
            seq += 1
            _style(ws, r, 1, seq)
            _style(ws, r, 2, sh["name"], align="left")
            _style(ws, r, 3, sh["model"], align="left")
            _style(ws, r, 4, sh["unit"] or "台")
            _style(ws, r, 5, sh["qty"] or 1)
            _style(ws, r, 6, sh.get("remark", ""))
            ws.row_dimensions[r].height = ROW_H["data"]
            r += 1
    else:
        seq += 1
        _style(ws, r, 1, seq)
        _style(ws, r, 2, "壳体(W*L*H):", align="left")
        _style(ws, r, 3, "")
        _style(ws, r, 4, "台")
        _style(ws, r, 5, 1)
        _style(ws, r, 6, "")
        ws.row_dimensions[r].height = ROW_H["data"]
        r += 1

    # 汇总行：材料小计 / 制造费 / 利润 / 税费 / 产品报价
    for label in SUMMARY_LABELS:
        seq += 1
        _style(ws, r, 1, seq)
        _style(ws, r, 2, label, align="left")
        _style(ws, r, 3, "")
        _style(ws, r, 4, "台")
        _style(ws, r, 5, None)
        _style(ws, r, 6, None)
        ws.row_dimensions[r].height = ROW_H["data"]
        r += 1

    ws.freeze_panes = "A5"


def write_report(ws, data, plans):
    widths = [26, 8, 14, 30, 10, 10, 10, 18]
    heads = ["柜名", "柜数", "配套件", "规格型号", "规则应配", "原表已有", "本次补齐", "触发规则"]
    for i, (h, w) in enumerate(zip(heads, widths), start=1):
        ws.column_dimensions[chr(64 + i)].width = w
        c = ws.cell(row=1, column=i, value=h)
        c.font = Font(name=FONT_NAME, size=FONT_SZ, bold=True)
        c.border = BORDER
        c.alignment = Alignment(horizontal="center", vertical="center")

    r = 2
    for cab, plan in zip(data["cabinets"], plans):
        for row in plan["report"]:
            vals = [cab["name"], cab["count"], row["name"], row["model"],
                    row["need"], row["have"], row["add"], row["rule"]]
            for i, v in enumerate(vals, start=1):
                c = ws.cell(row=r, column=i, value=v)
                c.font = Font(name=FONT_NAME, size=FONT_SZ)
                c.border = BORDER
                c.alignment = Alignment(horizontal="left" if i in (1, 3, 4) else "center",
                                        vertical="center", wrap_text=True)
                if i == 7 and v:
                    c.font = Font(name=FONT_NAME, size=FONT_SZ, bold=True, color="C00000")
            r += 1
    ws.freeze_panes = "A2"


# ---------- 主流程 ----------
def build(src, out, rules_path):
    data = parse_workbook(src)
    cfg = load_rules(rules_path)
    plans = [plan_cabinet(cab, cfg) for cab in data["cabinets"]]

    wb = Workbook()
    wb.remove(wb.active)

    total = len(data["cabinets"])
    used = set()
    for idx, (cab, plan) in enumerate(zip(data["cabinets"], plans), start=1):
        name = _sheet_name(cab["name"], idx, total)
        base, k = name, 1
        while name in used:
            k += 1
            name = f"{base[:28]}_{k}"
        used.add(name)
        write_cabinet_sheet(wb.create_sheet(name), data["title"], data["project"], cab, plan)

    write_report(wb.create_sheet("配套核对表"), data, plans)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    wb.save(out)

    all_items = [it for p in plans for it in p["items"]]
    return {"cabinets": total,
            "new_rows": sum(1 for it in all_items if it.get("is_new")),
            "changed_rows": sum(1 for it in all_items if it.get("is_changed")),
            "added_qty": sum(it.get("delta", it["qty"]) for it in all_items
                             if it.get("is_new") or it.get("is_changed"))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--out", required=True)
    ap.add_argument("--rules", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "references", "accessory_rules.json"))
    a = ap.parse_args()
    res = build(a.src, a.out, a.rules)
    print(f"柜数 {res['cabinets']}｜新增行 {res['new_rows']}｜改数量行 {res['changed_rows']}"
          f"｜合计补 {res['added_qty']} 件")
    print(f"-> {a.out}")


if __name__ == "__main__":
    from common import setup_stdout
    setup_stdout()
    main()
