"""Mutation test of the SQL: break the views on purpose, one change at a time, and check the suite notices.
Usage: python tests/mutants.py      (writes tests/mutants.json)"""
import json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests")); sys.path.insert(0, str(ROOT / "scripts"))
import checks, suite

MUTANTS = [
    ("10_checks_bundle_compare_at.sql", "THEN qty * unit_price END", "THEN unit_price END", "drop the quantity (2x counted once)"),
    ("10_checks_bundle_compare_at.sql", "c.gap > 0.005", "c.gap > 0.5", "widen the tolerance to 50 cents"),
    ("10_checks_bundle_compare_at.sql", "WHERE NOT a.is_default", "WHERE FALSE", "ignore the \"or\" alternative"),
    ("10_checks_bundle_compare_at.sql", "WHERE l.unpriced > 0 OR c.gap", "WHERE c.gap", "pass bundles whose jars cannot be priced"),
    ("01_listing_clean.sql", "WHEN price = 0 THEN", "WHEN price < 0 THEN", "count gifts and builders at 0.00"),
    ("01_listing_clean.sql", "WHEN handle LIKE '%geschenk%' OR title LIKE '🎁%' THEN 'gift'", "WHEN FALSE THEN 'gift'", "count a paid gift (no 0.00 price) as stock"),
    ("01_listing_clean.sql", "WHEN product_type = 'Hidden' THEN 'hidden'", "WHEN FALSE THEN 'hidden'", "count Hidden listings"),
    ("01_listing_clean.sql", "LTRIM(sku, '0') AS sku_key", "sku AS sku_key", "compare SKUs without dropping the leading zero"),
    ("01_listing_clean.sql", "kept_peers > 0", "kept_peers > 1", "keep landing-page copies"),
    ("01_listing_clean.sql", "kept_native_peers > 0", "kept_native_peers > 1", "keep marketplace-import copies"),
    ("01_listing_clean.sql", "WHEN handle LIKE 'b2b-%' THEN", "WHEN handle LIKE 'b2b-x%' THEN", "count B2B listings as retail"),
    ("11_checks_compare_at_not_above_price.sql", "compare_at_price <= price", "compare_at_price < price", "accept a struck price equal to the price"),
    ("12_checks_bundle_unparsed.sql", "b.bundle_handle IS NULL", "b.bundle_handle IS NOT NULL", "report parsed bundles instead of unparsed ones"),
    ("13_checks_same_sku_two_prices.sql", "HAVING MIN(price) <> MAX(price)", "HAVING MIN(price) > MAX(price)", "never compare the two prices"),
]

def main():
    base = {p.name: p.read_text(encoding="utf-8") for p in checks.sql_files()}
    passed, fails = suite.suite(base)
    if fails:
        sys.exit("the unmutated SQL already fails the suite:\n" + "\n".join(fails))
    results = []
    for fname, old, new, label in MUTANTS:
        if base[fname].count(old) != 1:
            sys.exit(f"mutant '{label}': text not found exactly once in {fname}")
        text = dict(base); text[fname] = base[fname].replace(old, new)
        try:
            _, fails = suite.suite(text)
        except Exception as e:          # a mutant that breaks the SQL outright also counts as caught
            fails = [f"error: {e}"]
        results.append({"mutant": label, "file": fname, "caught": bool(fails), "first_failure": fails[0] if fails else None})
        print(f"{'caught  ' if fails else 'SURVIVED'} {label}: {fails[0] if fails else ''}"[:160])
    caught = sum(r["caught"] for r in results)
    (ROOT / "tests" / "mutants.json").write_text(json.dumps({"cases": passed, "caught": caught, "total": len(results), "mutants": results}, indent=1))
    print(f"{caught}/{len(results)} mutants caught by {passed} cases")
    sys.exit(0 if caught == len(results) else 1)

if __name__ == "__main__":
    main()
