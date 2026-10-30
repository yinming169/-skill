"""生成报价 Excel：封面 / 元器件清单 / 柜体部件 / 铜排清单 / 汇总 / 未匹配清单。

单价列留空时整行标黄，不写 0，避免"未报价"看起来像"免费"。
"""
import argparse
import datetime as dt

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from common import read_json, setup_stdout

THIN = Side(style="thin", color="B0B0B0")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HDR_FILL = PatternFill("solid", fgColor="1F4E79")
HDR_FONT = Font(bold=True, color="FFFFFF", size=10)
TITLE_FONT = Font(bold=True, size=16)
SUB_FONT = Font(bold=True, size=11)
YELLOW = PatternFill("solid", fgColor="FFF2CC")
GREY = PatternFill("solid", fgColor="F2F2F2")
MONEY = "#,##0.00"
PCT = "0.0%"


def _hdr(ws, row, cols, widths):
    for i, (c, w) in enumerate(zip(cols, widths), start=1):
        cell = ws.cell(row=row, column=i, value=c)
        cell.fill = HDR_FILL
        cell.font = HDR_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[row].height = 26


def _cell(ws, r, c, v, fmt=None, align="center", fill=None, bold=False):
    cell = ws.cell(row=r, column=c, value=v)
    cell.border = BORDER
    cell.alignment = Alignment(horizontal=align, vertical="center", wrap_text=(align == "left"))
    if fmt:
        cell.number_format = fmt
    if fill:
        cell.fill = fill
    if bold:
        cell.font = Font(bold=True)
    return cell


def sheet_items(wb, rows, title="元器件清单", group_by_cabinet=True):
    ws = wb.create_sheet(title)
    cols = ["序号", "柜号", "类别", "名称", "规格型号", "品牌", "单位", "数量",
            "单价(成本)", "加价率", "售价", "小计", "匹配", "供应商", "图纸依据/备注"]
    widths = [5, 9, 9, 16, 22, 11, 5, 7, 11, 8, 11, 12, 8, 14, 40]
    _hdr(ws, 1, cols, widths)

    r = 2
    seq = 1
    last_cab = None
    total_cost_row = []
    for it in rows:
        cab = it.get("cabinet", "")
        if group_by_cabinet and cab != last_cab:
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=len(cols))
            c = ws.cell(row=r, column=1, value=f"【{cab}】")
            c.font = SUB_FONT
            c.fill = GREY
            c.alignment = Alignment(horizontal="left", vertical="center")
            c.border = BORDER
            r += 1
            last_cab = cab

        has_price = it.get("cost") is not None
        fill = None if has_price else YELLOW
        _cell(ws, r, 1, seq, align="center", fill=fill)
        _cell(ws, r, 2, cab, fill=fill)
        _cell(ws, r, 3, it.get("category", ""), fill=fill)
        _cell(ws, r, 4, it.get("name", ""), align="left", fill=fill)
        _cell(ws, r, 5, it.get("model", ""), align="left", fill=fill)
        _cell(ws, r, 6, it.get("brand", ""), fill=fill)
        _cell(ws, r, 7, it.get("unit", ""), fill=fill)
        _cell(ws, r, 8, it.get("qty", 0), fill=fill)
        _cell(ws, r, 9, it.get("cost") if has_price else None, fmt=MONEY, fill=fill)
        _cell(ws, r, 10, it.get("markup", 0), fmt=PCT, fill=fill)
        if has_price:
            _cell(ws, r, 11, f"=I{r}*(1+J{r})", fmt=MONEY, fill=fill)
            _cell(ws, r, 12, f"=H{r}*K{r}", fmt=MONEY, fill=fill)
        else:
            _cell(ws, r, 11, None, fmt=MONEY, fill=fill)
            _cell(ws, r, 12, None, fmt=MONEY, fill=fill)
        _cell(ws, r, 13, it.get("match", ""), fill=fill)
        _cell(ws, r, 14, it.get("supplier", ""), fill=fill)
        _cell(ws, r, 15, (it.get("evidence") or it.get("basis") or "")[:200], align="left", fill=fill)
        total_cost_row.append(r)
        r += 1
        seq += 1

    if total_cost_row:
        _cell(ws, r, 1, "合计", bold=True, fill=GREY)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)
        _cell(ws, r, 8, f"=SUM(H{total_cost_row[0]}:H{total_cost_row[-1]})", bold=True, fill=GREY)
        _cell(ws, r, 9, None, fill=GREY)
        _cell(ws, r, 10, None, fill=GREY)
        _cell(ws, r, 11, None, fill=GREY)
        _cell(ws, r, 12, f"=SUM(L{total_cost_row[0]}:L{total_cost_row[-1]})", fmt=MONEY, bold=True, fill=GREY)
        ws.merge_cells(start_row=r, start_column=13, end_row=r, end_column=15)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{r-1}"
        return ws, r - 1  # 返回最后一条数据行，供汇总 SUM 使用（不能含合计行）
    return ws, 1


def sheet_copper(wb, rows):
    ws = wb.create_sheet("铜排清单")
    cols = ["序号", "名称", "规格", "数量(柜)", "长度(m)", "重量(kg)",
            "单价(元/kg)", "加价率", "售价(元/kg)", "金额", "推算依据"]
    widths = [5, 12, 18, 9, 9, 10, 12, 8, 12, 12, 55]
    _hdr(ws, 1, cols, widths)
    r = 2
    for i, it in enumerate(rows, start=1):
        has = it.get("cost") is not None
        fill = None if has else YELLOW
        _cell(ws, r, 1, i, fill=fill)
        _cell(ws, r, 2, it.get("name", ""), fill=fill)
        _cell(ws, r, 3, it.get("spec", ""), fill=fill)
        _cell(ws, r, 4, it.get("qty", 0), fill=fill)
        _cell(ws, r, 5, it.get("length_m", 0), fmt="#,##0.00", fill=fill)
        _cell(ws, r, 6, it.get("weight_kg", 0), fmt="#,##0.00", fill=fill)
        _cell(ws, r, 7, it.get("cost") if has else None, fmt=MONEY, fill=fill)
        _cell(ws, r, 8, it.get("markup", 0), fmt=PCT, fill=fill)
        if has:
            _cell(ws, r, 9, f"=G{r}*(1+H{r})", fmt=MONEY, fill=fill)
            _cell(ws, r, 10, f"=F{r}*I{r}", fmt=MONEY, fill=fill)
        else:
            _cell(ws, r, 9, None, fmt=MONEY, fill=fill)
            _cell(ws, r, 10, None, fmt=MONEY, fill=fill)
        _cell(ws, r, 11, it.get("basis", ""), align="left", fill=fill)
        r += 1
    if r > 2:
        _cell(ws, r, 1, "合计", bold=True, fill=GREY)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=9)
        _cell(ws, r, 10, f"=SUM(J2:J{r-1})", fmt=MONEY, bold=True, fill=GREY)
        _cell(ws, r, 11, None, fill=GREY)
        ws.freeze_panes = "A2"
        return ws, r - 1
    return ws, 1


def sheet_summary(wb, items_end, parts_end, copper_end, project):
    ws = wb.create_sheet("汇总")
    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 26
    ws.column_dimensions["C"].width = 16
    ws.column_dimensions["D"].width = 16
    ws.column_dimensions["E"].width = 14

    ws["A1"] = "报价汇总"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:E1")

    rows = [
        ("一", "元器件清单", f"=SUM('元器件清单'!L2:L{items_end})"),
        ("二", "柜体部件清单", f"=SUM('柜体部件'!L2:L{parts_end})"),
        ("三", "铜排清单", f"=SUM('铜排清单'!J2:J{copper_end})"),
    ]
    r = 3
    _hdr(ws, r, ["序号", "分项", "金额(元)", "占比", "备注"], [6, 26, 16, 12, 24])
    r += 1
    first = r
    for no, name, formula in rows:
        _cell(ws, r, 1, no)
        _cell(ws, r, 2, name, align="left")
        _cell(ws, r, 3, formula, fmt=MONEY)
        _cell(ws, r, 4, f"=IF($C${first+3}=0,0,C{r}/$C${first+3})", fmt=PCT)
        _cell(ws, r, 5, "", align="left")
        r += 1

    _cell(ws, r, 1, "", fill=GREY)
    _cell(ws, r, 2, "设备材料合计", bold=True, fill=GREY, align="left")
    _cell(ws, r, 3, f"=SUM(C{first}:C{r-1})", fmt=MONEY, bold=True, fill=GREY)
    _cell(ws, r, 4, "", fill=GREY)
    _cell(ws, r, 5, "", fill=GREY)
    total_row = r
    r += 2

    # 税费与总价
    _cell(ws, r, 2, "增值税率", align="left")
    _cell(ws, r, 3, project.get("tax_rate", 0.13), fmt=PCT)
    r += 1
    _cell(ws, r, 2, "税额", align="left")
    _cell(ws, r, 3, f"=C{total_row}*C{r-1}", fmt=MONEY)
    tax_row = r
    r += 1
    _cell(ws, r, 2, "含税总价", bold=True, fill=GREY, align="left")
    _cell(ws, r, 3, f"=C{total_row}+C{tax_row}", fmt=MONEY, bold=True, fill=GREY)
    r += 2

    # 利润口径说明
    _cell(ws, r, 2, "报价说明", bold=True, align="left")
    r += 1
    notes = [
        "1. 单价为成本价，售价 = 单价 × (1+加价率)，加价率按类别分别设定（见 references/markup_rates.json）。",
        "2. 黄色底纹行为价格库未匹配项，需人工补价后再出正式报价。",
        "3. 铜排用量为按额定电流与柜体尺寸推算值，非图纸标注，报价前必须复核。",
        "4. 柜体部件数量为按柜型标准配置估算，实际以柜厂配置单为准。",
    ]
    for n in notes:
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=5)
        c = ws.cell(row=r, column=2, value=n)
        c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        r += 1
    return ws


def sheet_cover(wb, project, stats):
    ws = wb.create_sheet("封面", 0)
    ws.column_dimensions["A"].width = 4
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 46

    ws["B2"] = project.get("title", "高低压成套开关柜报价单")
    ws["B2"].font = Font(bold=True, size=20)
    ws.merge_cells("B2:C2")
    ws["B2"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 40

    info = [
        ("项目名称", project.get("name", "")),
        ("客户/需方", project.get("customer", "")),
        ("报价单位", project.get("vendor", "")),
        ("柜型", project.get("voltage_class", "")),
        ("柜体尺寸", project.get("cabinet_size", "")),
        ("柜数", project.get("cabinet_count", "")),
        ("柜号清单", project.get("cabinet_ids", "")),
        ("报价日期", project.get("date", dt.date.today().strftime("%Y-%m-%d"))),
        ("版本", project.get("version", "V1.0")),
    ]
    r = 5
    for k, v in info:
        c1 = ws.cell(row=r, column=2, value=k)
        c1.font = Font(bold=True)
        c1.fill = GREY
        c1.border = BORDER
        c1.alignment = Alignment(horizontal="right", vertical="center")
        c2 = ws.cell(row=r, column=3, value=v)
        c2.border = BORDER
        c2.alignment = Alignment(horizontal="left", vertical="center")
        ws.row_dimensions[r].height = 22
        r += 1

    r += 1
    ws.cell(row=r, column=2, value="识别统计").font = SUB_FONT
    r += 1
    for k, v in stats:
        ws.cell(row=r, column=2, value=k).border = BORDER
        ws.cell(row=r, column=2).alignment = Alignment(horizontal="right", vertical="center")
        ws.cell(row=r, column=3, value=v).border = BORDER
        ws.cell(row=r, column=3).alignment = Alignment(horizontal="left", vertical="center")
        r += 1
    return ws


def build(priced, out):
    wb = Workbook()
    wb.remove(wb.active)

    items = priced.get("items", [])
    parts = priced.get("cabinet_parts", [])
    copper = priced.get("copper", [])
    unmatched = priced.get("unmatched", [])

    _, items_end = sheet_items(wb, items, "元器件清单", True)
    _, parts_end = sheet_items(wb, parts, "柜体部件", False)
    _, copper_end = sheet_copper(wb, copper)

    size = priced.get("cabinet_size") or {}
    project = {
        "title": "高低压成套开关柜报价单",
        "name": priced.get("project", {}).get("name", ""),
        "voltage_class": priced.get("voltage_class", ""),
        "cabinet_size": f"{size.get('w')}×{size.get('h')}×{size.get('d')} mm" if size else "未识别",
        "cabinet_count": len(priced.get("cabinets", [])) or 1,
        "cabinet_ids": "、".join(c.get("id", "") for c in priced.get("cabinets", [])),
        "date": dt.date.today().strftime("%Y-%m-%d"),
    }
    stats = [
        ("识别元器件", f"{len(items)} 项"),
        ("柜体部件", f"{len(parts)} 项"),
        ("铜排规格", f"{len(copper)} 项"),
        ("价格未匹配", f"{len(unmatched)} 项（见未匹配清单）"),
        ("价格库条数", priced.get("db_size", 0)),
    ]
    sheet_cover(wb, project, stats)
    sheet_summary(wb, items_end, parts_end, copper_end, project)

    # 未匹配清单放最后
    ws = wb.create_sheet("未匹配清单")
    cols = ["柜号", "类别", "名称", "规格型号", "品牌", "单位", "数量", "原因"]
    _hdr(ws, 1, cols, [10, 10, 18, 26, 12, 6, 8, 34])
    for i, it in enumerate(unmatched, start=2):
        _cell(ws, i, 1, it.get("cabinet", ""), fill=YELLOW)
        _cell(ws, i, 2, it.get("category", ""), fill=YELLOW)
        _cell(ws, i, 3, it.get("name", ""), align="left", fill=YELLOW)
        _cell(ws, i, 4, it.get("model", ""), align="left", fill=YELLOW)
        _cell(ws, i, 5, it.get("brand", ""), fill=YELLOW)
        _cell(ws, i, 6, it.get("unit", ""), fill=YELLOW)
        _cell(ws, i, 7, it.get("qty", 0), fill=YELLOW)
        _cell(ws, i, 8, "价格库无匹配，请补价" if it.get("model") else "型号缺失，请人工确认", align="left", fill=YELLOW)
    if not unmatched:
        ws.cell(row=2, column=1, value="全部匹配成功")
    ws.freeze_panes = "A2"

    # 警告页脚
    warns = priced.get("warnings", [])
    if warns:
        ws2 = wb.create_sheet("复核提示")
        ws2.column_dimensions["A"].width = 120
        ws2["A1"] = "复核提示（务必人工确认后再对外报价）"
        ws2["A1"].font = Font(bold=True, size=13, color="C00000")
        for i, w in enumerate(warns, start=3):
            ws2.cell(row=i, column=1, value=f"· {w}").alignment = Alignment(wrap_text=True, vertical="top")

    wb.save(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("priced", help="priced.json")
    ap.add_argument("--out", default="报价单.xlsx")
    a = ap.parse_args()
    data = read_json(a.priced)
    path = build(data, a.out)
    print(f"报价单 -> {path}")
    print(f"  元器件 {len(data.get('items', []))} 项 / 柜体部件 {len(data.get('cabinet_parts', []))} 项 / "
          f"铜排 {len(data.get('copper', []))} 项 / 未匹配 {len(data.get('unmatched', []))} 项")


if __name__ == "__main__":
    setup_stdout()
    main()
