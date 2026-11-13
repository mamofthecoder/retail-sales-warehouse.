CREATE OR REPLACE VIEW daily_sales_summary
 AS
 SELECT d.full_date,
    count(f.order_item_id) AS sales_line_count,
    count(DISTINCT f.order_id) AS unique_order_count,
    round(sum(f.line_revenue) / NULLIF(count(DISTINCT f.order_id), 0)::numeric, 2) AS average_order_value,
    round(avg(f.line_revenue), 2) AS average_revenue_per_sales_line,
    round(sum(f.line_revenue) / NULLIF(sum(f.quantity), 0)::numeric, 2) AS revenue_per_unit,
    COALESCE(sum(f.line_revenue), 0::numeric) AS total_revenue,
    COALESCE(sum(f.quantity), 0::bigint) AS units_sold
   FROM dim_date d
     LEFT JOIN fact_sales f ON d.date_key = f.order_date_key
  GROUP BY d.full_date;
