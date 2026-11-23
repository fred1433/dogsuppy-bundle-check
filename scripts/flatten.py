"""Flatten the frozen snapshot (data/raw) into the three tables the checks read.

data/tables/listing.csv      one row per variant, as the store publishes it
data/tables/bundle_line.csv  the composition each bundle states in its own description
data/tables/store.csv        currency per store, read from /cart.js

This is the step that would load BigQuery each morning (bq load of the same three CSVs).
Usage: python scripts/flatten.py [raw_dir] [out_dir]
"""
import csv, html, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
STORES = ["dogsuppy.com", "dogsuppy.de", "dogsuppy.dk", "dogsuppy.no",
          "dogsuppy.se", "dogsuppy.co.uk", "dogsuppy.pl", "dogsuppy.it"]
# "Deze voordeelbundel bevat: 1x ...", "Questo Bundle Risparmio contiene: 2x ..."
CONTAINS = re.compile(r"\b(?:bevat|contiene|contains|enthält|indeholder|inneholder|innehåller|zawiera)\s*:\s*(.*)", re.I | re.S)
ITEM = re.compile(r"(\d+)\s*x\s+(.+?)(?=\s+\d+\s*x\s|$)", re.S)
ALTERNATIVE = re.compile(r"\s+(?:of|o|or|oder|eller|lub)\s+")

def text(body_html):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", body_html or ""))).strip()

def composition(body_html):
    """[(qty, [label, alternative...]), ...] or [] when the description lists no contents."""
    m = CONTAINS.search(text(body_html))
    if not m:
        return []
    listed = re.sub(r"\([^)]*\)", " ", m.group(1))          # drop "(2x 60 snoepjes)", "(con o senza carne, ...)"
    listed = re.sub(r"\s+", " ", listed).strip()
    return [(int(q), [a.strip() for a in ALTERNATIVE.split(label.strip()) if a.strip()])
            for q, label in ITEM.findall(listed)]

def main(raw=ROOT / "data" / "raw", out=ROOT / "data" / "tables"):
    raw, out = pathlib.Path(raw), pathlib.Path(out)
    if not (raw / "read_log.json").exists():
        sys.exit(f"no snapshot in {raw}: run scripts/fetch_snapshot.py first, or pass the folder that holds it")
    out.mkdir(parents=True, exist_ok=True)
    read_at = json.loads((raw / "read_log.json").read_text())["read_at_utc"]
    mapping = {(r["store"], r["label"]): r["component_handle"]
               for r in csv.DictReader(open(ROOT / "mapping" / "bundle_components.csv", encoding="utf-8"))}
    listing, lines, stores = [], [], []
    for s in STORES:
        currency = json.loads((raw / f"{s}.cart.json").read_text())["currency"]
        stores.append({"store": s, "currency": currency, "currency_source": "GET /cart.js", "read_at": read_at})
        for p in json.loads((raw / f"{s}.products.json").read_text())["products"]:
            for v in p["variants"]:
                listing.append({
                    "store": s, "currency": currency, "handle": p["handle"], "title": p["title"],
                    "product_type": p["product_type"] or "",
                    "tags": "," + ",".join(p["tags"]) + ",",          # ",a,b," so a LIKE '%,a,%' test is exact
                    "variant_id": v["id"], "variant_title": v["title"],
                    "sku": v["sku"] or "",                            # text: keeps the leading zero of 05430003031827
                    "price": v["price"], "compare_at_price": v["compare_at_price"] or "",
                    "available": str(bool(v["available"])).lower(),
                    "url": f"https://{s}/products/{p['handle']}", "read_at": read_at})
            for slot, (qty, labels) in enumerate(composition(p["body_html"]), start=1):
                for i, label in enumerate(labels):
                    lines.append({"store": s, "bundle_handle": p["handle"], "slot": slot, "qty": qty,
                                  "label": label, "component_handle": mapping.get((s, label), ""),
                                  "is_default": str(i == 0).lower()})
    for name, rows in (("listing", listing), ("bundle_line", lines), ("store", stores)):
        with open(out / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader(); w.writerows(rows)
    print(f"{len(listing)} variants, {len({(l['store'], l['bundle_handle']) for l in lines})} bundles with a stated composition, "
          f"{len(lines)} composition lines, {sum(1 for l in lines if not l['component_handle'])} unmapped -> {out}")

if __name__ == "__main__":
    main(*sys.argv[1:3])
