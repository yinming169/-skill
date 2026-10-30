"""PDF 图纸提取：文字层 + 表格 + 扫描件判定。

矢量 PDF（CAD 导出）文字可选中 → 直接抽取，准确率高。
扫描件（无文字层）→ 标记 is_scanned，交给 extract_ocr 或人工。
"""
import os

import fitz  # PyMuPDF


def extract_pdf(path, max_pages=None, want_tables=True):
    doc = fitz.open(path)
    pages, all_rows, all_tables = [], [], []
    scanned_pages = []

    for i, page in enumerate(doc):
        if max_pages and i >= max_pages:
            break
        d = page.get_text("dict")
        rows, char_count = [], 0
        for block in d.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                txt = "".join(s.get("text", "") for s in spans).strip()
                if not txt:
                    continue
                char_count += len(txt)
                bbox = line.get("bbox", (0, 0, 0, 0))
                size = max((s.get("size", 0) for s in spans), default=0)
                rows.append({
                    "page": i + 1,
                    "text": txt,
                    "x": round(bbox[0], 1),
                    "y": round(bbox[1], 1),
                    "size": round(size, 1),
                })
        rows.sort(key=lambda r: (r["y"], r["x"]))
        is_scanned = char_count < 20
        if is_scanned:
            scanned_pages.append(i + 1)
        pages.append({"page": i + 1, "is_scanned": is_scanned,
                      "char_count": char_count, "row_count": len(rows)})
        all_rows.extend(rows)

        if want_tables and not is_scanned:
            try:
                import pdfplumber
                with pdfplumber.open(path) as pdf:
                    if i < len(pdf.pages):
                        for tb in pdf.pages[i].extract_tables() or []:
                            if tb and len(tb) > 1:
                                all_tables.append({
                                    "page": i + 1,
                                    "rows": [[(c or "").replace("\n", " ").strip() for c in r] for r in tb],
                                })
            except Exception as e:
                pages[-1]["table_error"] = str(e)

    doc.close()
    return {
        "file": os.path.abspath(path),
        "source_type": "pdf_scanned" if len(scanned_pages) == len(pages) and pages else "pdf_vector",
        "pages": pages,
        "rows": all_rows,
        "tables": all_tables,
        "scanned_pages": scanned_pages,
        "inserts": [],
        "texts": [],
    }


if __name__ == "__main__":
    import sys
    from common import setup_stdout, write_json
    setup_stdout()
    res = extract_pdf(sys.argv[1])
    out = sys.argv[2] if len(sys.argv) > 2 else None
    if out:
        write_json(out, res)
        print(f"写入 {out}")
    print(f"类型 {res['source_type']} / 页 {len(res['pages'])} / 行 {len(res['rows'])} / 表 {len(res['tables'])}")
    if res["scanned_pages"]:
        print(f"扫描页: {res['scanned_pages']} —— 需 OCR 或人工复核")
