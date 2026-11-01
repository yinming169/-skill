"""检索《低压成套开关设备的原理及其控制技术》OCR全文，返回PDF页码。"""
import argparse, csv, pathlib, re, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
BOOK=ROOT/'knowledge'/'txt'/'资料3_低压成套开关设备_OCR.md'
INDEX=ROOT/'knowledge'/'资料3_全文逐页索引.csv'
FALLBACK=ROOT.parent/'knowledge'/'txt'/'资料3_低压成套开关设备_OCR.md'
def search(terms, limit=12, context=1):
    path=BOOK if BOOK.is_file() else FALLBACK
    if not path.is_file(): raise FileNotFoundError('缺少资料3 OCR全文：请提供 knowledge/txt/资料3_低压成套开关设备_OCR.md')
    raw=path.read_text(encoding='utf-8'); p=re.split(r'<!--\s*p(\d+)\s*-->',raw)
    index={}
    index_path = INDEX if INDEX.is_file() else ROOT.parent/'knowledge'/'资料3_全文逐页索引.csv'
    if index_path.is_file():
        with index_path.open(encoding='utf-8-sig',newline='') as f:
            for row in csv.DictReader(f): index[int(row['PDF页码'])]=row['原图复核状态']
    result=[]
    for n,txt in zip(p[1::2],p[2::2]):
        if not all(t.casefold() in txt.casefold() for t in terms): continue
        lines=txt.splitlines(); offsets=[i for i,x in enumerate(lines) if any(t.casefold() in x.casefold() for t in terms)]; keep=set()
        for i in offsets:
            keep.update(range(max(0,i-context),min(len(lines),i+context+1)))
        page=int(n); result.append({'pdf_page':page,'printed_page_candidate':page-10 if page>=11 else None,'verification':index.get(page,'未记录，须查原图'),'excerpts':[lines[i].strip() for i in sorted(keep) if lines[i].strip()]})
        if len(result)>=limit:break
    return result
if __name__=='__main__':
    try: sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError: pass
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('terms',nargs='+');p.add_argument('--max',type=int,default=12);p.add_argument('--context',type=int,default=1);a=p.parse_args()
    try: hits=search(a.terms,a.max,a.context)
    except (OSError,ValueError) as e: print(str(e),file=sys.stderr);sys.exit(2)
    print('OCR检索线索：数字、公式、表格和页码须对照原版PDF；局部查看不代表全页校验。')
    for h in hits:
        print(f"\nPDF第{h['pdf_page']}页 / 书页候选 {h['printed_page_candidate']}（以原图为准） / {h['verification']}")
        for x in h['excerpts']:print(' ',x[:200])
    print(f'\n本次返回 {len(hits)} 页；关键词可能因OCR错字漏检。')

