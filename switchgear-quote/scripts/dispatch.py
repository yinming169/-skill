"""图纸分流：扫描输入目录，判定每个文件的链路，输出 manifest.json。"""
import argparse
import os

from common import ensure_dir, write_json

DRAWING_EXT = {".dwg", ".dxf", ".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
SKIP_HINT = ("~$", ".tmp", ".bak")


def classify_file(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".dxf":
        return "dxf", "DXF 直接解析（最可靠）"
    if ext == ".dwg":
        return "dwg_need_convert", "DWG 需先转 DXF"
    if ext == ".pdf":
        return "pdf", "PDF 按文字层判定（矢量/扫描）"
    if ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"):
        return "image", "图片走 OCR"
    return "unknown", "不支持"


def scan(target):
    files = []
    if os.path.isfile(target):
        files = [target]
    else:
        for root, _, names in os.walk(target):
            for n in names:
                if any(h in n for h in SKIP_HINT):
                    continue
                p = os.path.join(root, n)
                if os.path.splitext(p)[1].lower() in DRAWING_EXT:
                    files.append(p)

    entries = []
    for p in sorted(files):
        kind, note = classify_file(p)
        entries.append({
            "path": os.path.abspath(p),
            "name": os.path.basename(p),
            "size_kb": round(os.path.getsize(p) / 1024, 1),
            "kind": kind,
            "note": note,
        })
    return entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="图纸文件或目录")
    ap.add_argument("--out", default="work", help="工作目录")
    a = ap.parse_args()

    ensure_dir(a.out)
    entries = scan(a.input)
    manifest = {"input": os.path.abspath(a.input), "files": entries}

    if not entries:
        print("未找到图纸文件（支持 dwg/dxf/pdf/png/jpg/tif）")
        return

    print(f"{'文件':<40} {'大小KB':>8}  链路")
    print("-" * 80)
    for e in entries:
        print(f"{e['name'][:38]:<40} {e['size_kb']:>8}  {e['note']}")

    dwg = [e for e in entries if e["kind"] == "dwg_need_convert"]
    if dwg:
        print("\n[!] 有 DWG 文件，必须先转 DXF。二选一：")
        print("    A. 用 CAD 打开 → 另存为 DXF（AutoCAD R2018 / 2007 均可）")
        print("    B. 装 ODA File Converter 后批量转：")
        print("       ODAFileConverter <输入目录> <输出目录> ACAD2018 DXF 0 1 *.dwg")

    out = os.path.join(a.out, "manifest.json")
    write_json(out, manifest)
    print(f"\nmanifest -> {out}")


if __name__ == "__main__":
    from common import setup_stdout
    setup_stdout()
    main()
