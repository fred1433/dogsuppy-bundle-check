"""Write the BigQuery copy of sql/*.sql into bigquery/, for one dataset.

The SQL is the same text that runs in DuckDB; the only change is that every table and view
name after FROM, JOIN, TABLE or VIEW gets the dataset prefix in backticks.
Usage: python scripts/bq_render.py <project.dataset>      e.g. python scripts/bq_render.py my-project.reporting
"""
import pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import checks

NAMES = ["listing_clean", "listing", "bundle_line", "store", "checks_bundle_compare_at",
         "checks_compare_at_not_above_price", "checks_bundle_unparsed", "checks_same_sku_two_prices", "checks_all"]
PATTERN = re.compile(r"\b(FROM|JOIN|TABLE IF NOT EXISTS|TABLE|VIEW)\s+(" + "|".join(NAMES) + r")\b")

def render(dataset):
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_]+", dataset or ""):
        raise ValueError("dataset must look like project.dataset, e.g. my-project.reporting")
    return {p.name: PATTERN.sub(lambda m: f"{m.group(1)} `{dataset}.{m.group(2)}`", p.read_text(encoding="utf-8"))
            for p in checks.sql_files()}

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python scripts/bq_render.py <project.dataset>   (e.g. my-project.reporting)")
    try:
        files = render(sys.argv[1])
    except ValueError as e:
        sys.exit(str(e))
    out = checks.ROOT / "bigquery"
    out.mkdir(exist_ok=True)
    for name, text in files.items():
        (out / name).write_text(text, encoding="utf-8")
    print(f"{len(files)} files written to {out}; run them in order in the BigQuery console or with bq query --use_legacy_sql=false")
