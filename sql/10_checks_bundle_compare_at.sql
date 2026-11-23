-- A bundle's struck price (compare_at_price) must equal the sum of today's prices of the jars
-- its own description lists. When the description offers "X or Y", either total passes.
-- Contract: 0 rows = PASS. A bundle whose jars cannot all be priced is returned as not_checked, never passed.
CREATE OR REPLACE VIEW checks_bundle_compare_at AS
WITH bundle AS (
  SELECT store, handle, url, compare_at_price, read_at
  FROM listing_clean
  WHERE compare_at_price IS NOT NULL AND excluded_reason IS NULL
),
unit AS (            -- one price per jar; NULL when its flavours disagree
  SELECT store, handle, CASE WHEN MIN(price) = MAX(price) THEN MIN(price) END AS unit_price
  FROM listing_clean
  WHERE excluded_reason IS NULL
  GROUP BY store, handle
),
line AS (
  SELECT b.store, b.bundle_handle, b.slot, b.qty, b.is_default, u.unit_price
  FROM bundle_line b
  LEFT JOIN unit u ON u.store = b.store AND u.handle = b.component_handle
),
listed AS (          -- the composition as written first in the description
  SELECT store, bundle_handle,
         SUM(CASE WHEN is_default THEN qty * unit_price END) AS total,
         SUM(CASE WHEN unit_price IS NULL THEN 1 ELSE 0 END) AS unpriced   -- counts "or" alternatives too
  FROM line
  GROUP BY store, bundle_handle
),
possible AS (        -- that total, plus one total per "or" alternative swapped into its slot
  SELECT store, bundle_handle, total FROM listed
  UNION ALL
  SELECT a.store, a.bundle_handle, l.total - d.qty * d.unit_price + a.qty * a.unit_price
  FROM line a
  JOIN line d ON d.store = a.store AND d.bundle_handle = a.bundle_handle AND d.slot = a.slot AND d.is_default
  JOIN listed l ON l.store = a.store AND l.bundle_handle = a.bundle_handle
  WHERE NOT a.is_default
),
closest AS (
  SELECT p.store, p.bundle_handle, MIN(ABS(p.total - b.compare_at_price)) AS gap
  FROM possible p
  JOIN bundle b ON b.store = p.store AND b.handle = p.bundle_handle
  GROUP BY p.store, p.bundle_handle
)
SELECT
  'bundle_compare_at' AS check_name,
  CASE WHEN l.unpriced > 0 THEN 'not_checked' ELSE 'mismatch' END AS severity,
  b.store, b.handle AS key,
  CASE WHEN l.unpriced = 0 THEN l.total END AS expected,
  b.compare_at_price AS actual,
  CASE WHEN l.unpriced = 0 THEN b.compare_at_price - l.total END AS delta,
  b.url AS evidence_url, b.read_at
FROM bundle b
JOIN listed l ON l.store = b.store AND l.bundle_handle = b.handle
JOIN closest c ON c.store = b.store AND c.bundle_handle = b.handle
WHERE l.unpriced > 0 OR c.gap > 0.005;
