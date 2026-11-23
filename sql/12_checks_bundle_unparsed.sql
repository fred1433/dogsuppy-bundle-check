-- A listing with a struck price but no composition read from its description cannot be checked:
-- it is reported as not_checked rather than silently counted as a pass.
CREATE OR REPLACE VIEW checks_bundle_unparsed AS
SELECT
  'bundle_unparsed' AS check_name, 'not_checked' AS severity,
  l.store, l.handle AS key,
  CAST(NULL AS NUMERIC(10,2)) AS expected, l.compare_at_price AS actual, CAST(NULL AS NUMERIC(10,2)) AS delta,
  l.url AS evidence_url, l.read_at
FROM listing_clean l
LEFT JOIN (SELECT DISTINCT store, bundle_handle FROM bundle_line) b
  ON b.store = l.store AND b.bundle_handle = l.handle
WHERE l.excluded_reason IS NULL AND l.compare_at_price IS NOT NULL AND b.bundle_handle IS NULL;
