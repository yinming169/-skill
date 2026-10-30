"""价格匹配：三级匹配价格库，逐项加价，输出 priced.json。

价格库只认用户提供的历史报价/采购价。匹配不到就留空，绝不猜价。
"""
import argparse
import difflib
import json
import os

from common import clean_money, norm_model, read_json, setup_stdout, write_json

TIERS = ("精确", "包含", "模糊", "名称+品牌")


def load_db(path):
    """读取价格库（xlsx/xls/csv）。返回统一列名的 dict 列表。"""
    import pandas as pd
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls", ".xlsm"):
        df = pd.read_excel(path, dtype=str)
    else:
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    alias = {
        "型号": ["型号", "规格型号", "型号规格", "规格", "model"],
        "名称": ["名称", "物料名称", "品名", "name"],
        "类别": ["类别", "分类", "类型", "category"],
        "品牌": ["品牌", "厂牌", "brand"],
        "单位": ["单位", "unit"],
        "单价": ["单价", "价格", "含税单价", "成本价", "price"],
        "供应商": ["供应商", "厂商", "渠道", "supplier"],
        "备注": ["备注", "说明", "remark"],
    }
    ren = {}
    for std, cands in alias.items():
        for c in cands:
            hit = [col for col in df.columns if col.strip().lower() == c.lower()]
            if hit:
                ren[hit[0]] = std
                break
    df = df.rename(columns=ren)
    if "型号" not in df.columns:
        raise SystemExit(f"价格库缺少「型号」列，现有列：{list(df.columns)}")
    for col in ("名称", "类别", "品牌", "单位", "单价", "供应商", "备注"):
        if col not in df.columns:
            df[col] = ""
    df = df.fillna("")
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "model": str(r["型号"]).strip(),
            "norm": norm_model(r["型号"]),
            "name": str(r["名称"]).strip(),
            "category": str(r["类别"]).strip(),
            "brand": str(r["品牌"]).strip(),
            "unit": str(r["单位"]).strip(),
            "price": clean_money(r["单价"]),
            "supplier": str(r["供应商"]).strip(),
            "note": str(r["备注"]).strip(),
        })
    return [r for r in rows if r["norm"]]


def match_by_name(name, db):
    """柜体部件专用：型号列常是尺寸，按名称匹配更靠谱。"""
    if not name:
        return None
    cands = []
    for r in db:
        rn = r["name"]
        if not rn:
            continue
        if rn == name:
            cands.append((0, r))
        elif rn in name or name in rn:
            cands.append((abs(len(rn) - len(name)), r))
    if cands:
        cands.sort(key=lambda x: x[0])
        return cands[0][1]
    return None


def match_one(model, name, brand, db, prefer_name=False):
    """返回 (价格库行, 匹配方式, 相似度)。"""
    if prefer_name:
        r = match_by_name(name, db)
        if r and r["price"] is not None:
            return r, "名称", 0.85

    n = norm_model(model)
    if not n:
        return None, "", 0.0

    # 1 精确
    for r in db:
        if r["norm"] == n:
            return r, "精确", 1.0

    # 2 包含（长串包含短串，且短串≥4 字符，避免 iC65 命中一切）
    cands = []
    for r in db:
        a, b = r["norm"], n
        if len(a) >= 4 and len(b) >= 4 and (a in b or b in a):
            cands.append((abs(len(a) - len(b)), r))
    if cands:
        cands.sort(key=lambda x: x[0])
        return cands[0][1], "包含", 0.9

    # 3 模糊
    best, best_score = None, 0.0
    for r in db:
        s = difflib.SequenceMatcher(None, n, r["norm"]).ratio()
        if s > best_score:
            best, best_score = r, s
    if best and best_score >= 0.86:
        return best, "模糊", round(best_score, 2)

    # 4 名称 + 品牌
    if name and brand:
        for r in db:
            if name in r["name"] and (not r["brand"] or brand in r["brand"] or r["brand"] in brand):
                return r, "名称+品牌", 0.8
    return None, "", 0.0


def markup_for(item, cfg):
    cat = item.get("category", "")
    if cat in cfg.get("by_category", {}):
        return cfg["by_category"][cat]
    text = (item.get("name", "") + item.get("model", ""))
    for kw, rate in cfg.get("by_keyword", {}).items():
        if kw in text:
            return rate
    return cfg.get("default", 0.12)


def price_rows(items, db, cfg, kind="item"):
    out, unmatched = [], []
    prefer_name = kind == "part"
    for it in items:
        r, how, score = match_one(it.get("model", ""), it.get("name", ""), it.get("brand", ""), db,
                                  prefer_name=prefer_name)
        qty = it.get("qty", 0) or 0
        rate = markup_for(it, cfg)
        row = dict(it)
        row["qty"] = qty
        row["markup"] = rate
        if r and r["price"] is not None:
            row["cost"] = r["price"]
            row["price"] = round(r["price"] * (1 + rate), 2)
            row["amount"] = round(row["price"] * qty, 2)
            row["cost_amount"] = round(r["price"] * qty, 2)
            row["match"] = how
            row["match_score"] = score
            row["db_model"] = r["model"]
            row["supplier"] = r["supplier"]
            if not row.get("brand"):
                row["brand"] = r["brand"]
        else:
            row["cost"] = None
            row["price"] = None
            row["amount"] = None
            row["cost_amount"] = None
            row["match"] = "未匹配"
            row["match_score"] = 0
            row["db_model"] = ""
            row["supplier"] = ""
            unmatched.append(row)
        out.append(row)
    return out, unmatched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("items", help="items.json")
    ap.add_argument("--db", required=True, help="价格库 xlsx/csv")
    ap.add_argument("--markup", default=None, help="加价配置 json（默认 references/markup_rates.json）")
    ap.add_argument("--out", default="work/priced.json")
    a = ap.parse_args()

    items_doc = read_json(a.items)
    db = load_db(a.db)
    if not db:
        raise SystemExit("价格库为空")

    mpath = a.markup or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                     "references", "markup_rates.json")
    cfg = json.load(open(mpath, encoding="utf-8")) if os.path.exists(mpath) else {"default": 0.12}

    comps, u1 = price_rows(items_doc.get("items", []), db, cfg)
    parts, u2 = price_rows(items_doc.get("cabinet_parts", []), db, cfg, kind="part")

    copper = []
    # 铜排只认按 kg 计价的价格库行，避免串到"接地铜排(元/m)"这类辅材
    cu_db = [r for r in db if r["unit"].lower() in ("kg", "千克", "公斤")
             or (r["category"] == "铜排" and r["unit"].lower() not in ("m", "米"))]
    for c in items_doc.get("copper", []):
        r, how, score = match_one(c["spec"], c["name"], "", cu_db)
        row = dict(c)
        row["category"] = "铜排"
        row["model"] = c.get("spec", "")
        row["cabinet"] = c.get("cabinet", "—")
        row["markup"] = cfg.get("by_category", {}).get("铜排", 0.15)
        if r and r["price"] is not None:
            # 价格库单价按 kg 计
            row["cost"] = r["price"]
            row["price"] = round(r["price"] * (1 + row["markup"]), 2)
            row["amount"] = round(row["price"] * c["weight_kg"], 2)
            row["cost_amount"] = round(r["price"] * c["weight_kg"], 2)
            row["match"] = how
            row["supplier"] = r["supplier"]
            row["db_model"] = r["model"]
            row["unit"] = "kg"
        else:
            row.update({"cost": None, "price": None, "amount": None, "cost_amount": None,
                        "match": "未匹配", "supplier": "", "db_model": "", "unit": "kg"})
            u2.append(row)
        copper.append(row)

    result = {
        "project": items_doc.get("project", {}),
        "voltage_class": items_doc.get("voltage_class"),
        "cabinet_size": items_doc.get("cabinet_size"),
        "cabinets": items_doc.get("cabinets", []),
        "items": comps,
        "cabinet_parts": parts,
        "copper": copper,
        "unmatched": u1 + u2,
        "warnings": items_doc.get("warnings", []),
        "db_size": len(db),
    }
    write_json(a.out, result)

    total_cost = sum(r["cost_amount"] or 0 for r in comps + parts + copper)
    total_price = sum(r["amount"] or 0 for r in comps + parts + copper)
    print(f"价格库 {len(db)} 条")
    print(f"元器件 {len(comps)} 项，柜体部件 {len(parts)} 项，铜排 {len(copper)} 项")
    print(f"未匹配 {len(result['unmatched'])} 项（必须人工补价）")
    if total_cost:
        print(f"成本合计 {total_cost:,.2f}  报价合计 {total_price:,.2f}  毛利 {total_price - total_cost:,.2f} "
              f"({(total_price - total_cost) / total_price * 100:.1f}%)")
    print(f"-> {a.out}")


if __name__ == "__main__":
    setup_stdout()
    main()
