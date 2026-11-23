import csv, json, pathlib, sys
import pytest
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "tests"))
import checks, suite, flatten

def test_clean_catalogue_returns_no_row():
    assert suite.run_case(suite.clean()) == []

@pytest.mark.parametrize("name", list(suite.EXPECTED))
def test_each_trap_returns_its_one_row(name):
    check, sev, key, delta = suite.EXPECTED[name]
    got = suite.run_case(suite.trap(name))
    assert [(r["check_name"], r["severity"], r["key"]) for r in got] == [(check, sev, key)]
    assert (got[0]["delta"] is None) if delta is None else float(got[0]["delta"]) == pytest.approx(delta)

def test_exclusion_reasons():
    con = checks.connect(suite.clean())
    reasons = dict(con.execute("SELECT handle, excluded_reason FROM listing_clean").fetchall())
    assert reasons["free-sample-jar-a"] == "zero price (gift, bundle builder or supply)"
    assert reasons["surprise-geschenk"] == "gift"
    assert reasons["jar-a-hidden"] == "hidden"
    assert reasons["b2b-jar-a"] == "b2b listing"
    assert reasons["jar-a-offer"] == "landing-page copy of a listed product"
    assert reasons["jar-c-marketplace"] == "marketplace-import copy of a listed product"
    assert reasons["build-your-own"].startswith("zero price")
    assert reasons["do-not-delete-this"] == "placeholder"
    assert reasons["jar-a"] is None and reasons["bundle-ab"] is None

def test_offer_handle_without_a_sibling_is_kept():
    t = suite.clean(); t["listing"].append(suite.item("jar-d-offer", "12.00", "5430000000444"))
    con = checks.connect(t)
    assert con.execute("SELECT excluded_reason FROM listing_clean WHERE handle = 'jar-d-offer'").fetchone()[0] is None

def test_sku_keeps_its_leading_zero():
    con = checks.connect(suite.clean())
    assert con.execute("SELECT sku FROM listing_clean WHERE handle = 'jar-c-marketplace'").fetchone()[0] == "05430000000333"

# --- the parser that reads the composition out of the bundle description ---
def test_composition_dutch_with_alternative():
    body = "<p>Deze voordeelbundel bevat:</p><ul><li>1x Anti-Anaalklieren (60 snoepjes)</li><li>1x Dental Bright (60 schepjes) of Dental Liquid (250ml)</li></ul>"
    assert flatten.composition(body) == [(1, ["Anti-Anaalklieren"]), (1, ["Dental Bright", "Dental Liquid"])]

def test_composition_italian_ignores_inner_parentheses():
    body = "Questo Bundle Risparmio contiene: 2x Sollievo Prurito (con o senza carne, 2x 60 integratori ) 2x Stress & Ansia (con o senza carne, 2x 60 integratori )"
    assert flatten.composition(body) == [(2, ["Sollievo Prurito"]), (2, ["Stress & Ansia"])]

def test_no_composition_means_no_lines():
    assert flatten.composition("<p>De slimme keuze voor je hond.</p>") == []

# --- the frozen snapshot of 23 November 2026 ---
TABLES = ROOT / "data" / "tables"

@pytest.fixture(scope="module")
def snap():
    return checks.connect(checks.load_csv(TABLES))

def test_snapshot_finds_exactly_the_four_italian_bundles(snap):
    got = checks.rows(snap, "checks_all")
    assert [(r["store"], r["key"], float(r["expected"]), float(r["actual"])) for r in got] == [
        ("dogsuppy.it", "bun-denti-e-stress", 67.80, 59.80),
        ("dogsuppy.it", "bun-denti-prurito", 135.60, 119.60),
        ("dogsuppy.it", "bun-denti-totale", 103.50, 95.50),
        ("dogsuppy.it", "bun-prurito-stress", 135.60, 119.60)]

def test_snapshot_all_nineteen_bundles_parsed_and_mapped():
    lines = list(csv.DictReader(open(TABLES / "bundle_line.csv", encoding="utf-8")))
    assert len({(l["store"], l["bundle_handle"]) for l in lines}) == 19
    assert all(l["component_handle"] for l in lines)

def test_snapshot_sku_text_kept():
    assert any(r["sku"] == "05430003031827" for r in csv.DictReader(open(TABLES / "listing.csv", encoding="utf-8")))

def test_hand_mappings_point_at_kept_listings(snap):
    kept = set(snap.execute("SELECT store, handle FROM listing_clean WHERE excluded_reason IS NULL").fetchall())
    for f, col in (("bundle_components.csv", "component_handle"), ("families.csv", "handle")):
        for r in csv.DictReader(open(ROOT / "mapping" / f, encoding="utf-8")):
            assert (r["store"], r[col]) in kept, (f, r)

def test_bigquery_rendering_parses():
    import sqlglot, bq_render
    for name, text in bq_render.render("my-project.dogsuppy").items():
        statements = [s for s in sqlglot.parse(text, read="bigquery") if s is not None]
        assert statements, name
    assert "FROM `my-project.dogsuppy.listing`" in bq_render.render("my-project.dogsuppy")["01_listing_clean.sql"]
    with pytest.raises(ValueError):
        bq_render.render("no-dataset")

def test_suite_and_mutants_agree():
    passed, fails = suite.suite()
    assert fails == [] and passed == 1 + len(suite.EXPECTED)

# --- the web archive's copy of 18 Apr 2026 (data/archive) ---
def test_archived_prices_add_up_to_each_italian_struck_price(snap):
    arch = json.loads((ROOT / "data" / "archive" / "dogsuppy.it.20260418.json").read_text())
    price = {i["handle"]: float(i["price"]) for i in arch["items"]}
    lines = [l for l in csv.DictReader(open(TABLES / "bundle_line.csv", encoding="utf-8"))
             if l["store"] == "dogsuppy.it" and l["is_default"] == "true"]
    flagged = {r["key"]: float(r["actual"]) for r in checks.rows(snap, "checks_all") if r["store"] == "dogsuppy.it"}
    assert len(flagged) == 4
    for key, struck in flagged.items():
        assert sum(int(l["qty"]) * price[l["component_handle"]] for l in lines if l["bundle_handle"] == key) == pytest.approx(struck), key
    assert arch["snapshot"].startswith("https://web.archive.org/web/20260418")

# --- the Apps Script query: what BigQuery's REST API hands to Sheets ---
def test_apps_script_query_formats_amounts_times_and_keeps_keys_as_text():
    import shutil, subprocess, sqlglot
    gs = ROOT / "apps_script" / "Exceptions.gs"
    if not shutil.which("node"):
        pytest.skip("node is needed to evaluate the Apps Script constants")
    query = subprocess.run(["node", "-e", "const fs = require('fs'); eval(fs.readFileSync(process.argv[1], 'utf8') + '; process.stdout.write(QUERY)')", str(gs)],
                           capture_output=True, text=True, check=True).stdout
    tree = sqlglot.parse_one(query, read="bigquery")
    assert [e.alias_or_name for e in tree.expressions] == ["check_name", "severity", "store", "key", "expected", "actual", "delta", "evidence_url", "read_at"]
    assert "FORMAT_TIMESTAMP('%F %R', read_at, 'Europe/Brussels')" in query
    assert query.count("FORMAT('%.2f',") == 3
    src = gs.read_text()
    body = src[src.index("function refreshExceptions"):src.index("function queryView_")]
    assert body.index("setNumberFormat('@')") < body.index("setValues(rows)")
