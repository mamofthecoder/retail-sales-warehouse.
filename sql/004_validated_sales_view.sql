CREATE VIEW validated_sales AS (SELECT ss.order_item_id,CASE WHEN ss.quantity <= 0 OR ss.quantity IS NULL THEN 'Invalid Quantity'
WHEN p.product_id IS NULL THEN 'Unknown Product'
WHEN d.full_date IS NULL THEN 'Missing date dimension'
WHEN ss.order_id IS NULL THEN 'Missing order ID'
WHEN ss.line_revenue IS NULL OR ss.line_revenue < 0 THEN 'Invalid revenue'
ELSE 'Valid'
END AS validation_status,ss.order_id,ss.product_id,ss.quantity,ss.line_revenue,
d.date_key AS order_date_key,ss.batch_id
FROM stg_sales ss
LEFT JOIN dim_product p ON ss.product_id = p.product_id
LEFT JOIN dim_date d ON d.full_date = ss.sale_date)
