"""DXF 图纸提取：图块引用 + 属性 + 文字 + 表格线。

DWG 无法直接读，必须先转 DXF（CAD 另存 / ODA File Converter）。
"""
import os

import ezdxf

from common import write_json


def _iter_layouts(doc):
    """模型空间 + 所有图纸空间（标题栏常在图纸空间）。"""
    yield "Model", doc.modelspace()
    for name in doc.layouts.names():
        if name.lower() == "model":
            continue
        try:
            yield name, doc.layouts.get(name)
        except Exception:
            continue


def extract_dxf(path):
    doc = ezdxf.readfile(path)
    inserts, texts, tables = [], [], []
    block_count = {}

    for layout_name, layout in _iter_layouts(doc):
        for e in layout:
            t = e.dxftype()
            if t == "INSERT":
                name = e.dxf.name
                block_count[name] = block_count.get(name, 0) + 1
                attribs = {}
                try:
                    for att in e.attribs:
                        attribs[att.dxf.tag] = (att.dxf.text or "").strip()
                except Exception:
                    pass
                try:
                    ins = e.dxf.insert
                    x, y = float(ins[0]), float(ins[1])
                except Exception:
                    x = y = 0.0
                inserts.append({
                    "layout": layout_name,
                    "block": name,
                    "layer": e.dxf.layer,
                    "attribs": attribs,
                    "x": round(x, 2),
                    "y": round(y, 2),
                })
            elif t == "TEXT":
                v = (e.dxf.text or "").strip()
                if v:
                    p = e.dxf.insert
                    texts.append({"layout": layout_name, "text": v,
                                  "layer": e.dxf.layer,
                                  "x": round(float(p[0]), 2),
                                  "y": round(float(p[1]), 2),
                                  "h": round(float(e.dxf.height or 0), 2)})
            elif t == "MTEXT":
                v = e.plain_text().strip() if hasattr(e, "plain_text") else ""
                if v:
                    p = e.dxf.insert
                    texts.append({"layout": layout_name, "text": v,
                                  "layer": e.dxf.layer,
                                  "x": round(float(p[0]), 2),
                                  "y": round(float(p[1]), 2),
                                  "h": round(float(e.dxf.char_height or 0), 2)})
            elif t in ("LINE", "LWPOLYLINE", "POLYLINE"):
                # 仅统计，用于判断是否有表格框线（不还原结构，避免过度推断）
                tables.append({"layout": layout_name, "type": t})
            elif t == "DIMENSION":
                try:
                    v = e.get_measurement()
                    if isinstance(v, (int, float)):
                        texts.append({"layout": layout_name,
                                      "text": f"{v:.1f}",
                                      "layer": e.dxf.layer,
                                      "x": 0, "y": 0, "h": 0})
                except Exception:
                    pass

    # 按 y 倒序、x 正序聚合成"行"（同一 y 附近视为同一行）
    rows = _group_rows(texts)
    return {
        "file": os.path.abspath(path),
        "source_type": "dxf",
        "inserts": inserts,
        "texts": texts,
        "rows": rows,
        "block_count": block_count,
        "line_count": len(tables),
        "dxf_version": doc.dxfversion,
    }


def _group_rows(texts, tol=3.0):
    """把文字按坐标聚成行，输出 [{y, text}]。"""
    if not texts:
        return []
    items = sorted(texts, key=lambda d: (-d["y"], d["x"]))
    rows, cur, cur_y = [], [], None
    for it in items:
        if cur_y is None or abs(it["y"] - cur_y) <= tol:
            cur.append(it)
            cur_y = it["y"] if cur_y is None else cur_y
        else:
            rows.append(cur)
            cur = [it]
            cur_y = it["y"]
    if cur:
        rows.append(cur)
    out = []
    for r in rows:
        r = sorted(r, key=lambda d: d["x"])
        out.append({"y": r[0]["y"], "text": " ".join(x["text"] for x in r),
                    "parts": [x["text"] for x in r]})
    return out


if __name__ == "__main__":
    import sys
    from common import setup_stdout
    setup_stdout()
    res = extract_dxf(sys.argv[1])
    out = sys.argv[2] if len(sys.argv) > 2 else None
    if out:
        write_json(out, res)
        print(f"写入 {out}")
    print(f"图块 {len(res['inserts'])} 个 / 文字 {len(res['texts'])} 条 / 行 {len(res['rows'])} 行")
