-- Within one store, the same SKU sold under two listings should carry one price.
CREATE OR REPLACE VIEW checks_same_sku_two_prices AS
SELECT
  'same_sku_two_prices' AS check_name, 'mismatch' AS severity,
  store, MIN(sku) AS key,
  MIN(price) AS expected, MAX(price) AS actual, MAX(price) - MIN(price) AS delta,
  MIN(url) AS evidence_url, MIN(read_at) AS read_at
FROM listing_clean
WHERE excluded_reason IS NULL AND sku_key <> ''
GROUP BY store, sku_key
HAVING MIN(price) <> MAX(price);
