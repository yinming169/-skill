"""按 manifest 逐个提取，合并成统一的 extract.json。

统一结构：
  files: [{file, kind, source_type, rows:[{text,x,y,page}], inserts:[...], tables:[...]}]
  rows:  所有文件的行，带 file 标记
"""
import argparse
import os

from common import read_json, setup_stdout, write_json


def run_one(entry):
    kind = entry["kind"]
    path = entry["path"]
    if kind == "dxf":
        from extract_dxf import extract_dxf
        return extract_dxf(path)
    if kind == "pdf":
        from extract_pdf import extract_pdf
        return extract_pdf(path)
    if kind == "image":
        try:
            from extract_ocr import extract_image
            return extract_image(path)
        except ImportError:
            return {"file": path, "source_type": "image_no_ocr", "rows": [],
                    "inserts": [], "tables": [],
                    "error": "未安装 OCR 依赖（paddleocr），请人工录入或改用矢量 PDF"}
    return {"file": path, "source_type": "skipped", "rows": [],
            "inserts": [], "tables": [], "error": entry["note"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("--out", default="work/extract.json")
    a = ap.parse_args()

    man = read_json(a.manifest)
    files, merged_rows = [], []
    for e in man["files"]:
        print(f"提取 {e['name']} ...", end="", flush=True)
        try:
            res = run_one(e)
        except Exception as ex:
            res = {"file": e["path"], "source_type": "error", "rows": [],
                   "inserts": [], "tables": [], "error": f"{type(ex).__name__}: {ex}"}
        res["kind"] = e["kind"]
        res["name"] = e["name"]
        files.append(res)
        for r in res.get("rows", []):
            r["file"] = e["name"]
            merged_rows.append(r)
        n = len(res.get("rows", []))
        flag = f" [!] {res['error']}" if res.get("error") else ""
        print(f" {n} 行{flag}")

    out = {"manifest": man["input"], "files": files, "rows": merged_rows}
    write_json(a.out, out)

    ok = sum(1 for f in files if not f.get("error"))
    print(f"\n完成 {ok}/{len(files)} 个文件，共 {len(merged_rows)} 行 -> {a.out}")
    for f in files:
        if f.get("error"):
            print(f"  ! {f['name']}: {f['error']}")


if __name__ == "__main__":
    setup_stdout()
    main()
