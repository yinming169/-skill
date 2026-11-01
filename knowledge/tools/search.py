"""五本资料全文检索。

用法:
    python tools/search.py "断路器 分断能力"          # 多个词 = AND
    python tools/search.py "铜排" --book 资料3         # 限定书目
    python tools/search.py "选择性" --ctx 3 --max 10   # 上下文行数、最多命中数

输出: 书名 / 页号 / 上下文片段
"""
import argparse
import glob
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TXT_DIR = os.path.join(BASE, "txt")
OCR_DIR = os.path.join(BASE, "ocr")

# 资料3 的 PDF 页 = 书页 + 10
PAGE_OFFSET = {"资料3": 10}


def load_docs():
    """返回 [(book, name, page, text)]。

    同时保留文字层及 OCR，不假设任一版本数字可信；结果可能重复。
    """
    docs = []
    md_files = sorted(glob.glob(os.path.join(TXT_DIR, "*.md")))
    for path in md_files:
        base = os.path.basename(path).replace(".md", "")
        book = base.split("_")[0]
        name = base
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        parts = re.split(r"<!--\s*p(\d+)\s*-->", content)
        # parts = [前导, 页号, 正文, 页号, 正文...]
        for i in range(1, len(parts) - 1, 2):
            page = int(parts[i])
            text = parts[i + 1]
            if text.strip():
                docs.append((book, name, page, text))
    # OCR 单页文件
    for book_dir in sorted(glob.glob(os.path.join(OCR_DIR, "*"))):
        if not os.path.isdir(book_dir):
            continue
        name = os.path.basename(book_dir)
        book = name.split("_")[0]
        for path in sorted(glob.glob(os.path.join(book_dir, "p*.txt"))):
            m = re.search(r"p(\d+)\.txt$", path)
            if not m:
                continue
            page = int(m.group(1))
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            text = re.sub(r"<!--\s*page\s*\d+\s*-->", "", text)
            if text.strip():
                docs.append((book, name, page, text))
    return docs


def book_label(name):
    """资料3_低压成套开关设备 -> 资料3 低压成套开关设备"""
    return name.replace("_", " ", 1)


def display_page(book, page):
    off = PAGE_OFFSET.get(book, 0)
    if off and page > off:
        return f"PDF p{page} (书页候选 {page - off}，以原图为准)"
    return f"p{page}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="+", help="关键词，多个为 AND")
    ap.add_argument("--book", default="", help="限定书目，如 资料3")
    ap.add_argument("--ctx", type=int, default=1, help="上下文行数")
    ap.add_argument("--max", type=int, default=30, help="最多命中页数")
    ap.add_argument("--exact", action="store_true", help="整串匹配（默认分词 AND）")
    a = ap.parse_args()

    print("提示：检索结果仅为文字层或OCR线索，数字、公式及表格须核原图；版本现行性须另行核实。")
    docs = load_docs()
    if not docs:
        print("未找到已提取的文本，请先运行提取/OCR。")
        return

    terms = [" ".join(a.query)] if a.exact else a.query
    hits = 0
    scanned = 0
    for book, name, page, text in docs:
        if a.book and not name.startswith(a.book):
            continue
        scanned += 1
        low = text.lower()
        if not all(t.lower() in low for t in terms):
            continue
        hits += 1
        lines = text.split("\n")
        print(f"\n■ {book_label(name)}　{display_page(book, page)}")
        shown = set()
        for idx, ln in enumerate(lines):
            if any(t.lower() in ln.lower() for t in terms):
                lo = max(0, idx - a.ctx)
                hi = min(len(lines), idx + a.ctx + 1)
                for j in range(lo, hi):
                    if j in shown:
                        continue
                    shown.add(j)
                    mark = ">" if j == idx else " "
                    s = lines[j].strip()
                    if s:
                        print(f"  {mark} {s[:160]}")
        if hits >= a.max:
            print(f"\n... 已达上限 {a.max} 页，用 --max 调整")
            break

    print(f"\n命中 {hits} 页（共扫描 {scanned} 页）")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
