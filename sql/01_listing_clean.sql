-- Every variant, with the reason it is left out of the checks (NULL = kept).
-- Gifts at 0.00, bundle builders at 0.00, supplies, Hidden listings, B2B listings and
-- landing-page or marketplace copies of a listing that is already there would all fake a finding.
CREATE OR REPLACE VIEW listing_clean AS
WITH tagged AS (
  SELECT
    store, currency, handle, title, product_type, tags, variant_id, variant_title, sku,
    price, compare_at_price, available, url, read_at,
    LTRIM(sku, '0') AS sku_key,                 -- 05430003031827 and 5430003031827 are one SKU; sku itself stays text
    (handle LIKE '%-offer' OR handle LIKE '%-noffer' OR handle LIKE '%-upsell') AS landing_copy,
    (tags LIKE '%,zooplus_import,%') AS marketplace_import,
    CASE
      WHEN handle = 'do-not-delete-this' THEN 'placeholder'
      WHEN product_type = 'Hidden' THEN 'hidden'
      WHEN handle LIKE 'b2b-%' THEN 'b2b listing'
      WHEN price = 0 THEN 'zero price (gift, bundle builder or supply)'
      WHEN handle LIKE '%geschenk%' OR title LIKE '🎁%' THEN 'gift'
    END AS first_reason
  FROM listing
),
siblings AS (
  SELECT t.*,
    SUM(CASE WHEN first_reason IS NULL AND NOT landing_copy THEN 1 ELSE 0 END)
      OVER (PARTITION BY store, sku_key) AS kept_peers,
    SUM(CASE WHEN first_reason IS NULL AND NOT landing_copy AND NOT marketplace_import THEN 1 ELSE 0 END)
      OVER (PARTITION BY store, sku_key) AS kept_native_peers
  FROM tagged t
)
SELECT
  store, currency, handle, title, product_type, tags, variant_id, variant_title, sku, sku_key,
  price, compare_at_price, available, url, read_at,
  COALESCE(first_reason,
    CASE
      WHEN landing_copy AND sku_key <> '' AND kept_peers > 0 THEN 'landing-page copy of a listed product'
      WHEN marketplace_import AND sku_key <> '' AND kept_native_peers > 0 THEN 'marketplace-import copy of a listed product'
    END) AS excluded_reason
FROM siblings;
