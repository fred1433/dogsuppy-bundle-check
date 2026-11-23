-- A struck price at or below the selling price is not a discount.
CREATE OR REPLACE VIEW checks_compare_at_not_above_price AS
SELECT
  'compare_at_not_above_price' AS check_name, 'mismatch' AS severity,
  store, CONCAT(handle, ' / ', variant_title) AS key,
  price AS expected, compare_at_price AS actual, compare_at_price - price AS delta,
  url AS evidence_url, read_at
FROM listing_clean
WHERE excluded_reason IS NULL AND compare_at_price IS NOT NULL AND compare_at_price <= price;
