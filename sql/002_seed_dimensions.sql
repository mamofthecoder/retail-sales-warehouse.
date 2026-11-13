INSERT INTO dim_date (date_key,full_date,year,month_number)
WITH full_years AS (SELECT generate_series(
'2026-01-01' :: date,
'2026-12-31' :: date,
'1 day'      :: interval
) :: date AS full_date)
SELECT TO_CHAR(full_date,'YYYYMMDD') :: INT,full_date,EXTRACT(YEAR FROM full_date):: INT,EXTRACT(MONTH FROM full_date) :: INT FROM full_years
ON CONFLICT (date_key) DO NOTHING;

INSERT INTO dim_product (product_id, product_name, product_category)
VALUES
    (7, 'Keyboard', 'Accessories'),
    (8, 'Mouse', 'Accessories'),
    (9, 'Monitor', 'Electronics')
ON CONFLICT (product_id) DO NOTHING;

