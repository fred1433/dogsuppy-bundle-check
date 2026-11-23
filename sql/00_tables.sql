-- The three tables loaded each morning from the snapshot (scripts/flatten.py writes them as CSV).
-- Types are written so the same DDL runs in DuckDB and BigQuery (STRING, BIGINT, NUMERIC(10,2), BOOL, TIMESTAMP).
CREATE TABLE IF NOT EXISTS listing (
  store STRING, currency STRING, handle STRING, title STRING, product_type STRING, tags STRING,
  variant_id BIGINT, variant_title STRING, sku STRING,
  price NUMERIC(10,2), compare_at_price NUMERIC(10,2), available BOOL, url STRING, read_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS bundle_line (
  store STRING, bundle_handle STRING, slot BIGINT, qty BIGINT, label STRING,
  component_handle STRING, is_default BOOL
);
CREATE TABLE IF NOT EXISTS store (
  store STRING, currency STRING, currency_source STRING, read_at TIMESTAMP
);
