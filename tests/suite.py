"""The test suite, as plain functions, so tests/test_checks.py (pytest) and tests/mutants.py share it.
Each case: a small catalogue, the check view it targets, and the rows checks_all must return."""
import copy, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import checks

S, AT = "shop.test", "2026-11-23 15:54:42"

def item(handle, price, sku="", compare="", title=None, ptype="", tags="", vid=None, vtitle="Default Title"):
    return {"store": S, "currency": "EUR", "handle": handle, "title": title or handle, "product_type": ptype,
            "tags": "," + tags + ",", "variant_id": vid or abs(hash((handle, vtitle))) % 10**12, "variant_title": vtitle,
            "sku": sku, "price": price, "compare_at_price": compare, "available": "true",
            "url": f"https://{S}/products/{handle}", "read_at": AT}

def line(bundle, slot, qty, component, default=True):
    return {"store": S, "bundle_handle": bundle, "slot": slot, "qty": qty, "label": component,
            "component_handle": component, "is_default": "true" if default else "false"}

def clean():
    listing = [
        item("jar-a", "30.00", "5430000000111"),
        item("jar-b", "20.00", "5430000000222", vtitle="with chicken"),
        item("jar-b", "20.00", "5430000000223", vtitle="without meat"),
        item("jar-c", "10.00", "5430000000333"),
        item("bundle-ab", "40.00", compare="50.00"),                  # 30 + 20
        item("bundle-2a-b-or-c", "55.00", compare="70.00"),           # 2x30 + (20 or 10): the "or 10" total is 70
        # listings that must be left out, each one would fake a finding if counted
        item("free-sample-jar-a", "0.00", "5430000000111"),
        item("surprise-geschenk", "4.80", "5430000000111"),
        item("jar-a-hidden", "25.00", "5430000000111", ptype="Hidden"),
        item("b2b-jar-a", "29.00", "5430000000111"),
        item("jar-a-offer", "27.00", "5430000000111"),
        item("jar-c-marketplace", "9.00", "05430000000333", tags="zooplus_import"),   # leading zero, same SKU
        item("build-your-own", "0.00", vtitle="Pack of 2"),
        item("do-not-delete-this", "5.00", compare="5.00"),
    ]
    lines = [line("bundle-ab", 1, 1, "jar-a"), line("bundle-ab", 2, 1, "jar-b"),
             line("bundle-2a-b-or-c", 1, 2, "jar-a"), line("bundle-2a-b-or-c", 2, 1, "jar-b"),
             line("bundle-2a-b-or-c", 2, 1, "jar-c", default=False)]
    return {"listing": listing, "bundle_line": lines, "store": [{"store": S, "currency": "EUR", "currency_source": "test", "read_at": AT}]}

def edit(t, handle, **kw):
    for r in t["listing"]:
        if r["handle"] == handle and (not kw.get("vtitle") or r["variant_title"] == kw["vtitle"]):
            r.update({k: v for k, v in kw.items() if k != "vtitle"})
    return t

def trap(name):
    t = copy.deepcopy(clean())
    if name == "stale_compare":       edit(t, "bundle-ab", compare_at_price="45.00")
    elif name == "off_by_ten_cents":  edit(t, "bundle-ab", compare_at_price="50.10")
    elif name == "compare_at_equal":  edit(t, "bundle-ab", price="50.00")
    elif name == "unparsed_bundle":   t["listing"].append(item("bundle-mystery", "60.00", compare="80.00"))
    elif name == "unknown_component": t["bundle_line"].append(line("bundle-ab", 3, 1, "jar-gone"))
    elif name == "flavours_disagree": edit(t, "jar-c", price="10.00"); t["listing"].append(item("jar-c", "11.00", "5430000000334", vtitle="with salmon"))
    elif name == "same_sku_two_prices": t["listing"].append(item("jar-a-large-page", "31.00", "5430000000111"))
    elif name == "same_sku_leading_zero": t["listing"].append(item("jar-c-page", "12.00", "05430000000333"))
    return t

EXPECTED = {   # trap -> (check_name, severity, key, delta)
    "stale_compare":       ("bundle_compare_at", "mismatch", "bundle-ab", -5),
    "off_by_ten_cents":    ("bundle_compare_at", "mismatch", "bundle-ab", 0.10),
    "compare_at_equal":    ("compare_at_not_above_price", "mismatch", "bundle-ab / Default Title", 0),
    "unparsed_bundle":     ("bundle_unparsed", "not_checked", "bundle-mystery", None),
    "unknown_component":   ("bundle_compare_at", "not_checked", "bundle-ab", None),
    "flavours_disagree":   ("bundle_compare_at", "not_checked", "bundle-2a-b-or-c", None),
    "same_sku_two_prices": ("same_sku_two_prices", "mismatch", "5430000000111", 1),
    "same_sku_leading_zero": ("same_sku_two_prices", "mismatch", "05430000000333", 2),
}

def run_case(tables, sql_text=None):
    return checks.rows(checks.connect(tables, sql_text), "checks_all")

def suite(sql_text=None):
    """Returns (passed, failures). Each failure is a one-line description."""
    fails, passed = [], 0
    got = run_case(clean(), sql_text)
    if got: fails.append(f"clean catalogue returned {len(got)} rows: {[(r['check_name'], r['key']) for r in got]}")
    else: passed += 1
    for name, (check, sev, key, delta) in EXPECTED.items():
        got = run_case(trap(name), sql_text)
        ok = (len(got) == 1 and got[0]["check_name"] == check and got[0]["severity"] == sev and got[0]["key"] == key
              and (delta is None and got[0]["delta"] is None or delta is not None and got[0]["delta"] is not None
                   and abs(float(got[0]["delta"]) - delta) < 1e-9))
        if ok: passed += 1
        else: fails.append(f"trap {name}: expected one {check}/{sev} row on {key}, got {[(r['check_name'], r['severity'], r['key'], r['delta']) for r in got]}")
    return passed, fails
