-- What the Sheets "Exceptions" tab reads each morning: every row of every check, one schema.
CREATE OR REPLACE VIEW checks_all AS
SELECT * FROM checks_bundle_compare_at
UNION ALL SELECT * FROM checks_compare_at_not_above_price
UNION ALL SELECT * FROM checks_bundle_unparsed
UNION ALL SELECT * FROM checks_same_sku_two_prices;
