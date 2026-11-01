"""检索 Elora Grid 电气符号目录的成套柜相关条目；结果仅供对照。"""
import argparse, json, pathlib, re
INDEX = pathlib.Path(__file__).resolve().parents[1] / 'references' / 'elora-symbols' / 'index.json'
ALIASES = {'断路器':'circuit breaker','开关':'switch','隔离':'isolator','互感器':'transformer','变压器':'transformer','继电器':'relay','接触器':'contactor','熔断器':'fuse','母线':'busbar','铜排':'busbar','电容':'capacitor','电机':'motor','仪表':'meter','浪涌':'surge','端子':'terminal'}
def search(query, limit=20):
    query = ALIASES.get(query.strip(), query.strip()).casefold()
    if not query: return []
    data = json.loads(INDEX.read_text(encoding='utf-8'))
    hits=[]
    for entry in data['entries']:
        values=[entry.get('name') or '', entry.get('abbreviation') or '', *(entry.get('aliases') or [])]
        score=max((3 if str(v).casefold()==query else 2 if query in str(v).casefold() else 0) for v in values)
        if score: hits.append((score,entry))
    return [e for _,e in sorted(hits,key=lambda x:(-x[0],x[1]['name']))[:limit]]
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('query');p.add_argument('--limit',type=int,default=20);a=p.parse_args()
    for e in search(a.query,a.limit): print(e['name'], '|',e.get('abbreviation') or '-', '|',e['canonicalUrl'])
