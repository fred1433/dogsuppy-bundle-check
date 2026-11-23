# DogSuppy bundle check

Every fixed bundle in DogSuppy's Shopify stores, added up: the struck price (`compare_at_price`) against the
price, on the day of the snapshot, of the products that the bundle's own description lists. Two of the eight
stores list fixed bundles (dogsuppy.com and dogsuppy.it); the other six list none. On the snapshot of
23 November 2026 (15:54 UTC) the 15 bundles on dogsuppy.com add up to the cent and the 4 on dogsuppy.it do not;
all four were marked unavailable in that catalogue read.

Page: https://theaipipe.com/demos/dogsuppy-bundle-check/

## What is in here

| Path | What it is |
|---|---|
| `data/raw/` | The frozen snapshot: one `products.json` per store, each store's currency from `/cart.js`, the read log, and what dogsuppy.nl, .be and .es answered. |
| `data/archive/dogsuppy.it.20260418.json` | The prices kept from one web.archive.org copy of a dogsuppy.it product page (18 Apr 2026), read once by hand. |
| `data/ecb/eurofxref-daily.xml` | ECB reference rates read with the snapshot (used only to line prices up, never to invoice). |
| `mapping/bundle_components.csv` | Hand-written: the jar name a bundle description uses, and the product it means, per store. |
| `mapping/families.csv` | Hand-written: one product family across the stores (Dental Bright carries 6 SKUs, so SKU and handle cannot do it). |
| `scripts/flatten.py` | Snapshot to the three tables the checks read (`listing`, `bundle_line`, `store`). This is the daily load. |
| `sql/` | The tables and the check views. Contract: 0 rows = PASS; a row that cannot be checked comes back as `not_checked`. |
| `scripts/checks.py` | Runs the views on DuckDB, locally. |
| `scripts/bq_render.py` | Writes the BigQuery copy of `sql/` for one dataset (names prefixed, nothing else changes). |
| `apps_script/Exceptions.gs` | Provided to install, not executed: fills an Exceptions tab in Google Sheets from `checks_all` each morning (times in Europe/Brussels, amounts to two decimals, SKU keys kept as text). |
| `tests/` | Clean and trapped catalogues, the snapshot assertions, the SQL mutation test, and the page in a browser (`test_page.py`). |

The views:

- `listing_clean`: every variant with the reason it is left out (gift or builder at 0.00, Hidden, B2B, landing-page or marketplace copy of a listed product, placeholder).
- `checks_bundle_compare_at`: struck price against the sum of the listed products at their snapshot price; an "X or Y" in the description passes on either total.
- `checks_compare_at_not_above_price`: a struck price at or below the selling price.
- `checks_bundle_unparsed`: a struck price with no readable composition.
- `checks_same_sku_two_prices`: one SKU, two prices, in one store.
- `checks_all`: the union, one schema: `check_name, severity, store, key, expected, actual, delta, evidence_url, read_at`.

On the snapshot: `checks_bundle_compare_at` 4 rows, `checks_compare_at_not_above_price` 0, `checks_bundle_unparsed` 0,
`checks_same_sku_two_prices` 0, so `checks_all` 4 rows.

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install duckdb pytest sqlglot playwright
.venv/bin/python -m playwright install chromium  # for tests/test_page.py only
.venv/bin/python scripts/flatten.py              # data/raw -> data/tables
.venv/bin/python scripts/checks.py               # prints the 4 rows of checks_all
.venv/bin/python tests/mutants.py                # 14 deliberate breaks of the SQL, each must be caught
.venv/bin/python scripts/build_site.py           # site/data.json and site/index.html
.venv/bin/python -m pytest -q tests              # 27 tests (the page tests skip without Playwright; the Apps Script one without node)
.venv/bin/python scripts/bq_render.py my-project.reporting   # bigquery/*.sql for that dataset
```

`scripts/fetch_snapshot.py` takes a new snapshot (one `products.json` request per store, one `/cart.js`
per store, the ECB file). It overwrites `data/raw`, so the numbers above will move with the stores.

## What was not run

Tested locally with DuckDB; BigQuery and Google Sheets were not executed for this demo, and no Google account
was used. The BigQuery files are the DuckDB SQL with dataset-qualified names; the tests parse them with sqlglot
in BigQuery's dialect, which checks syntax only. The Apps Script is provided to install: it needs your project,
the BigQuery advanced service and your own authorisation. Its query formats the amounts (`FORMAT('%.2f')`) and
`read_at` (`FORMAT_TIMESTAMP`, Europe/Brussels) in SQL, because the REST API returns a TIMESTAMP as float seconds
and a NUMERIC without trailing zeros, and it sets the key column to text before writing, so a SKU keeps its
leading zero; the test parses that query, it does not run it.

## Assumptions

- Currency per store is read from `/cart.js`; prices are assumed to include local VAT.
- The €29.90 jar price: it is the one jar price that makes all four Italian struck prices add up, and the
  web archive's copy of dogsuppy.it's Sollievo Prurito page, captured 18 Apr 2026 at 07:47 UTC, shows it:
  https://web.archive.org/web/20260418074716/https://dogsuppy.it/products/sollievo-prurito-100-naturale-60-integratori-1
  That page lists Sollievo Prurito, Ansia & Stress and Dental Bright at €29.90 (same SKUs as in the snapshot) and
  Dental Sticks Clean Bite at €7.14 (same name, another SKU). With those prices each Italian struck price adds up
  to the cent (`test_archived_prices_add_up_to_each_italian_struck_price`). One archive page was read, once.
- `updated_at` is not used: on dogsuppy.it it moves with stock, not with prices.
- Subscriptions (`#sub` tags) carry no plan in `products.json`; nothing is said about them.

Frederic de Lavenne de Choulot, The AI Pipe.
