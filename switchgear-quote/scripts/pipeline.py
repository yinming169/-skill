"""一键流水线：图纸 → 报价单。

    python pipeline.py --input 图纸目录 --db 价格库.xlsx --out 报价单.xlsx
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def run(script, args):
    cmd = [sys.executable, os.path.join(HERE, script)] + args
    print(f"\n$ {script} {' '.join(args)}")
    r = subprocess.run(cmd, cwd=HERE)
    if r.returncode != 0:
        raise SystemExit(f"{script} 失败，退出码 {r.returncode}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="图纸文件或目录")
    ap.add_argument("--db", required=True, help="价格库 xlsx/csv")
    ap.add_argument("--out", default="报价单.xlsx")
    ap.add_argument("--work", default="work")
    ap.add_argument("--cabinet-name", default="")
    a = ap.parse_args()

    os.makedirs(a.work, exist_ok=True)
    man = os.path.join(a.work, "manifest.json")
    ext = os.path.join(a.work, "extract.json")
    itm = os.path.join(a.work, "items.json")
    prc = os.path.join(a.work, "priced.json")

    run("dispatch.py", [a.input, "--out", a.work])
    run("extract.py", [man, "--out", ext])
    cls_args = [ext, "--out", itm]
    if a.cabinet_name:
        cls_args += ["--cabinet-name", a.cabinet_name]
    run("classify.py", cls_args)
    run("price_match.py", [itm, "--db", a.db, "--out", prc])
    run("build_quote.py", [prc, "--out", a.out])

    print(f"\n完成：{os.path.abspath(a.out)}")


if __name__ == "__main__":
    main()
