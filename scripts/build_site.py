"""Build site/data.json, everything the page shows, from the snapshot and the checks.
Every number on the page comes from here: the page itself computes nothing.
Usage: python scripts/build_site.py     (after scripts/flatten.py and tests/mutants.py)"""
import csv, copy, json, pathlib, re, sys, xml.etree.ElementTree as ET
from decimal import Decimal, ROUND_HALF_UP
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "tests"))
import checks, suite

TABLES = ROOT / "data" / "tables"
STORES = ["dogsuppy.com", "dogsuppy.de", "dogsuppy.dk", "dogsuppy.no", "dogsuppy.se", "dogsuppy.co.uk", "dogsuppy.pl", "dogsuppy.it"]
D2 = Decimal("0.01")

def q2(x): return str(Decimal(x).quantize(D2, ROUND_HALF_UP))
def pct(x): return str((Decimal(x) * 100).quantize(Decimal("0.1"), ROUND_HALF_UP))

def ecb():
    root = ET.parse(ROOT / "data" / "ecb" / "eurofxref-daily.xml").getroot()
    day = next(e for e in root.iter() if e.get("time"))
    return day.get("time"), {c.get("currency"): Decimal(c.get("rate")) for c in day}

def main():
    if not (TABLES / "listing.csv").exists():
        sys.exit("no data/tables: run scripts/flatten.py first")
    mut_file = ROOT / "tests" / "mutants.json"
    if not mut_file.exists():
        sys.exit("no tests/mutants.json: run tests/mutants.py first")
    tables = checks.load_csv(TABLES)
    con = checks.connect(tables)
    found = {(r["store"], r["key"]): r for r in checks.rows(con, "checks_bundle_compare_at")}
    all_rows = checks.rows(con, "checks_all")
    log = json.loads((ROOT / "data" / "raw" / "read_log.json").read_text())
    kept = {}
    for store, handle, title, price, compare, available, url in con.execute(
            "SELECT store, handle, title, price, compare_at_price, available, url FROM listing_clean WHERE excluded_reason IS NULL").fetchall():
        kept.setdefault((store, handle), {"title": title, "prices": set(), "compare": compare, "available": available, "url": url})["prices"].add(price)
    unit = {k: next(iter(v["prices"])) for k, v in kept.items() if len(v["prices"]) == 1}

    # --- the 19 bundles, line by line ---
    bundles = []
    lines = [l for l in tables["bundle_line"]]
    for (store, handle) in dict.fromkeys((l["store"], l["bundle_handle"]) for l in lines):
        b = kept[(store, handle)]
        price = next(iter(b["prices"]))
        rows, alts, total = [], [], Decimal(0)
        for l in (l for l in lines if l["store"] == store and l["bundle_handle"] == handle):
            u = unit[(store, l["component_handle"])]
            entry = {"qty": int(l["qty"]), "label": l["label"], "handle": l["component_handle"],
                     "jar_title": kept[(store, l["component_handle"])]["title"], "unit": q2(u), "line": q2(u * int(l["qty"])),
                     "url": f"https://{store}/products/{l['component_handle']}"}
            if l["is_default"] == "true":
                rows.append(entry); total += u * int(l["qty"])
            else:
                entry["slot"] = int(l["slot"]); alts.append(entry)
        for a in alts:
            d = next(r for r, l in zip(rows, [l for l in lines if l["store"] == store and l["bundle_handle"] == handle and l["is_default"] == "true"]) if int(l["slot"]) == a["slot"])
            a["replaces"] = d["label"]; a["total_with_it"] = q2(total - Decimal(d["line"]) + Decimal(a["line"]))
        row = found.get((store, handle))
        item = {"store": store, "handle": handle, "title": b["title"], "url": b["url"], "available": bool(b["available"]),
                "price": q2(price), "compare_at": q2(b["compare"]), "jars": rows, "alternatives": alts,
                "jar_total": q2(total), "status": "mismatch" if row else "pass",
                "gap": q2(b["compare"] - total), "discount_shown": pct(1 - price / b["compare"]),
                "discount_on_today": pct(1 - price / total)}
        if row:   # which single jar price would make the struck price add up?
            moved = [r for r in rows if Decimal(r["unit"]) == max(Decimal(x["unit"]) for x in rows)]
            fixed = sum(Decimal(r["line"]) for r in rows if r not in moved)
            n = sum(r["qty"] for r in moved)
            item["implied_jar_price"] = q2((b["compare"] - fixed) / n)
            item["implied_note"] = {"n": n, "fixed": [{"qty": r["qty"], "unit": r["unit"]} for r in rows if r not in moved]}
        bundles.append(item)
    bundles.sort(key=lambda x: (x["status"] != "mismatch", -abs(float(x["gap"])), x["handle"] != "bun-prurito-stress", x["title"]))
    it_rows = [b for b in bundles if b["status"] == "mismatch"]
    implied = {b["implied_jar_price"] for b in it_rows}

    # --- data mutations shown on the page ---
    t = copy.deepcopy(tables)
    for r in t["listing"]:
        if r["store"] == "dogsuppy.com" and r["handle"] == "dental-powder": r["price"] = "37.70"
    raise_db = [r["key"] for r in checks.rows(checks.connect(t), "checks_all") if r["store"] == "dogsuppy.com"]
    t = copy.deepcopy(tables)
    jars_3390 = sorted({j["handle"] for b in it_rows for j in b["jars"] if j["unit"] == "33.90"})
    for r in t["listing"]:
        if r["store"] == "dogsuppy.it" and r["handle"] in jars_3390: r["price"] = "29.90"
    at_2990 = [r["key"] for r in checks.rows(checks.connect(t), "checks_all")]

    # --- range matrix and Dental Bright ladder (section 2, no verdicts) ---
    day, rates = ecb()
    currency = {r["store"]: r["currency"] for r in tables["store"]}
    fam = {}
    for r in csv.DictReader(open(ROOT / "mapping" / "families.csv", encoding="utf-8")):
        fam.setdefault(r["family"], {})[r["store"]] = {"price": q2(unit[(r["store"], r["handle"])]), "currency": currency[r["store"]],
                                                        "handle": r["handle"]}
    matrix = [{"family": f, "cells": [cells.get(s) for s in STORES]} for f, cells in fam.items()]
    def eur(p, c): return p if c == "EUR" else p / rates[c]
    ladder = sorted(({"store": s, "price": c["price"], "currency": c["currency"], "eur": q2(eur(Decimal(c["price"]), c["currency"])),
                      "rate": str(rates.get(c["currency"], "")) } for s, c in fam["Dental Bright (60 scoops)"].items()),
                    key=lambda x: Decimal(x["eur"]))

    # --- the three open questions, numbers from the snapshot ---
    cb_com, cb_it = unit[("dogsuppy.com", "clean-bite-sticks-schone-tanden-en-verwijderen-van-tandplak-5-sticks-per-zakje")], unit[("dogsuppy.it", "dental-sticks")]
    big_com, small_com = unit[("dogsuppy.com", "maxi-pack-anti-jeuk-voor-grote-honden-100-natuurlijk-90-snoepjes")], unit[("dogsuppy.com", "probiotica-forte-anti-jeuk-hond")]
    big_uk, small_uk = unit[("dogsuppy.co.uk", "largedog-itch-relief")], unit[("dogsuppy.co.uk", "probiotica-forte-anti-itch-dog")]
    hidden = con.execute("SELECT handle, title, product_type FROM listing_clean WHERE store = 'dogsuppy.com' AND handle LIKE 'maxi-pack-dental-bright%'").fetchone()
    per = lambda p, n: (p / n).quantize(Decimal("0.001"), ROUND_HALF_UP)
    questions = {
        "clean_bite": {"sku": "5430003031353", "com": q2(cb_com), "it": q2(cb_it), "diff_pct": pct(cb_it / cb_com - 1)},
        "jar_90": {"com_90": q2(big_com), "com_60": q2(small_com), "com_per_90": str(per(big_com, 90)), "com_per_60": str(per(small_com, 60)),
                   "com_pct": pct((big_com / 90) / (small_com / 60) - 1),
                   "uk_90": q2(big_uk), "uk_60": q2(small_uk), "uk_per_90": str(per(big_uk, 90)), "uk_per_60": str(per(small_uk, 60)),
                   "uk_pct": pct((big_uk / 90) / (small_uk / 60) - 1)},
        "handle_title": {"handle": hidden[0], "title": hidden[1], "type": hidden[2]},
    }

    db_skus = sorted({r[0] for r in con.execute(
        "SELECT DISTINCT l.sku FROM listing_clean l JOIN (SELECT * FROM (VALUES " +
        ", ".join(f"('{s}', '{c['handle']}')" for s, c in fam["Dental Bright (60 scoops)"].items()) +
        ") v(store, handle)) v ON v.store = l.store AND v.handle = l.handle").fetchall()})
    excl = con.execute("SELECT COUNT(*), SUM(CASE WHEN excluded_reason IS NULL THEN 1 ELSE 0 END) FROM listing_clean").fetchone()
    mut = json.loads(mut_file.read_text())
    passed, fails = suite.suite()
    reqs = log["requests"]
    data = {
        "read_at_utc": log["read_at_utc"],
        "catalogue_requests": sum(1 for r in reqs if "products.json" in r["url"]),
        "currency_requests": sum(1 for r in reqs if "cart.js" in r["url"]),
        "stores": [{"store": s, "currency": currency[s], "variants": sum(1 for r in tables["listing"] if r["store"] == s)} for s in STORES],
        "ecb_day": day, "ecb_rates": {k: str(v) for k, v in rates.items() if k in ("DKK", "GBP", "NOK", "PLN", "SEK")},
        "bundles": bundles, "mismatch_count": len(it_rows), "short_total": q2(sum(-Decimal(b["gap"]) for b in it_rows)), "pass_count": len(bundles) - len(it_rows),
        "implied_jar_price": sorted(implied), "checks_all_rows": len(all_rows),
        "mutation_raise_dental_bright": raise_db, "mutation_it_jars_2990": at_2990, "it_jars_moved": jars_3390,
        "dental_bright_skus": db_skus, "variants_total": excl[0], "variants_checked": int(excl[1]),
        "matrix_stores": STORES, "matrix": matrix, "ladder": ladder, "questions": questions,
        "tests": {"cases": passed, "failures": fails, "mutants_caught": mut["caught"], "mutants_total": mut["total"],
                  "mutants": [m["mutant"] for m in mut["mutants"]]},
        "sql_view": (ROOT / "sql" / "10_checks_bundle_compare_at.sql").read_text(encoding="utf-8"),
    }
    (ROOT / "site" / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print(f"{len(bundles)} bundles: {data['pass_count']} add up, {len(it_rows)} do not; implied jar price {sorted(implied)}")
    print(f"mutation .com Dental Bright +0.10 -> {raise_db}")
    print(f"mutation .it jars at 29.90 -> {at_2990}")
    print(f"tests {passed} cases, {len(fails)} failures; mutants {mut['caught']}/{mut['total']}")

def render_page():
    """Fill site_src/index.html with the numbers from site/data.json and write site/index.html."""
    import datetime, shutil
    d = json.loads((ROOT / "site" / "data.json").read_text())
    head = next(b for b in d["bundles"] if b["handle"] == "bun-prurito-stress")
    read = datetime.datetime.fromisoformat(d["read_at_utc"])
    day = datetime.date.fromisoformat(d["ecb_day"])
    q = d["questions"]
    jars_now = {j["unit"] for b in d["bundles"] if b["status"] == "mismatch" for j in b["jars"] if j["handle"] in d["it_jars_moved"]}
    assert len(jars_now) == 1 and len(d["implied_jar_price"]) == 1
    values = {
        "it_total": head["jar_total"], "it_struck": head["compare_at"], "shown": head["discount_shown"], "today": head["discount_on_today"],
        "pass_count": d["pass_count"], "mismatch_count": d["mismatch_count"],
        "jar_implied": d["implied_jar_price"][0], "jar_now": jars_now.pop(),
        "read_date": f"{read.day} {read:%B %Y}", "read_date_short": f"{read.day} {read:%b}", "read_time": f"{read:%H:%M}",
        "catalogue_requests": d["catalogue_requests"], "variants_checked": d["variants_checked"], "variants_total": d["variants_total"],
        "db_sku_count": len(d["dental_bright_skus"]), "ecb_day_long": f"{day.day} {day:%B %Y}",
        "cb_sku": q["clean_bite"]["sku"], "cb_com": q["clean_bite"]["com"], "cb_it": q["clean_bite"]["it"], "cb_pct": q["clean_bite"]["diff_pct"],
        "j_com_pct": q["jar_90"]["com_pct"].lstrip("-"), "j_com_90": q["jar_90"]["com_per_90"], "j_com_60": q["jar_90"]["com_per_60"],
        "j_uk_pct": q["jar_90"]["uk_pct"].lstrip("-"), "j_uk_90": q["jar_90"]["uk_per_90"], "j_uk_60": q["jar_90"]["uk_per_60"],
        "checks_rows": d["checks_all_rows"], "trap_count": d["tests"]["cases"] - 1,
        "mut_db_count": len(d["mutation_raise_dental_bright"]), "mut_it_count": len(d["mutation_it_jars_2990"]),
        "mut_total": d["tests"]["mutants_total"], "mut_caught": d["tests"]["mutants_caught"],
        "data_json": json.dumps(d, ensure_ascii=False).replace("</", "<\\/"),
    }
    # the sentences around these numbers assume their direction: stop if the data says otherwise
    assert not q["jar_90"]["com_pct"].startswith("-") and q["jar_90"]["uk_pct"].startswith("-")
    page = (ROOT / "site_src" / "index.html").read_text(encoding="utf-8")
    for k, v in values.items():
        page = page.replace("{{" + k + "}}", str(v))
    missing = re.findall(r"\{\{(\w+)\}\}", page)
    if missing:
        sys.exit(f"template keys without a value: {missing}")
    (ROOT / "site" / "index.html").write_text(page, encoding="utf-8")
    fav = pathlib.Path("/Users/frederic/ProjetsDev/the-ai-pipe-website/website/public")
    for f in ("favicon.svg", "favicon.png"):
        if (fav / f).exists() and not (ROOT / "site" / f).exists():
            shutil.copy(fav / f, ROOT / "site" / f)
    print(f"site/index.html written ({len(page) // 1024} KB)")


if __name__ == "__main__":
    main()
    render_page()
