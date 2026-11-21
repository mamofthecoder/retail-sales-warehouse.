import psycopg
import logging
import argparse

fact_upsert_sql = """INSERT INTO fact_sales (
    order_item_id, order_id, order_date_key,
    product_id, quantity, line_revenue
)
SELECT
    order_item_id, order_id, order_date_key,
    product_id, quantity, line_revenue
FROM validated_sales
WHERE batch_id = %s
  AND validation_status = 'Valid'
ON CONFLICT (order_item_id) DO UPDATE
SET line_revenue = EXCLUDED.line_revenue,
order_id = EXCLUDED.order_id,
order_date_key = EXCLUDED.order_date_key,
product_id = EXCLUDED.product_id,
quantity = EXCLUDED.quantity
WHERE EXCLUDED.order_id IS DISTINCT FROM fact_sales.order_id
   OR EXCLUDED.order_date_key IS DISTINCT FROM fact_sales.order_date_key
   OR EXCLUDED.product_id IS DISTINCT FROM fact_sales.product_id
   OR EXCLUDED.quantity IS DISTINCT FROM fact_sales.quantity
   OR EXCLUDED.line_revenue IS DISTINCT FROM fact_sales.line_revenue;"""

rejection_audit_sql = """
SELECT * FROM validated_sales v
LEFT JOIN sales_load_rejections r
ON v.batch_id = r.batch_id AND v.order_item_id =  r.order_item_id
WHERE  v.validation_status <> 'Valid' AND (r.batch_id IS NULL OR r.rejection_reason IS DISTINCT FROM v.validation_status 
OR r.resolved_at IS NOT NULL) AND v.batch_id = %s;"""

reject_upsert_sql = """

INSERT INTO sales_load_rejections (batch_id,order_item_id,rejection_reason)
SELECT batch_id,order_item_id,validation_status
FROM validated_sales
WHERE validation_status <> 'Valid' AND batch_id = %s
ON CONFLICT (batch_id,order_item_id) DO UPDATE
SET rejection_reason = EXCLUDED.rejection_reason,
rejected_at = CURRENT_TIMESTAMP,
resolved_at = NULL
WHERE EXCLUDED.rejection_reason IS DISTINCT FROM sales_load_rejections.rejection_reason
OR sales_load_rejections.resolved_at IS NOT NULL;"""

resolve_rejections_sql = """
UPDATE sales_load_rejections AS r
SET resolved_at = CURRENT_TIMESTAMP
FROM validated_sales AS v
WHERE v.validation_status = 'Valid'
  AND v.batch_id = r.batch_id
  AND v.order_item_id = r.order_item_id
  AND r.resolved_at IS NULL
  AND v.batch_id = %s;"""


audit_sql = """
SELECT v.order_item_id
FROM validated_sales AS v
LEFT JOIN fact_sales AS f
    ON v.order_item_id = f.order_item_id
WHERE v.validation_status = 'Valid'
  AND (
      f.order_item_id IS NULL
      OR v.quantity IS DISTINCT FROM f.quantity
      OR v.line_revenue IS DISTINCT FROM f.line_revenue
	  OR v.product_id IS DISTINCT FROM f.product_id
	  OR v.order_id IS DISTINCT FROM f.order_id
	  OR v.order_date_key IS DISTINCT FROM f.order_date_key
  ) AND v.batch_id = %s;"""

def load_sales_batch(batch_id, connection_settings):
  
    try:
        with psycopg.connect(**connection_settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM stg_sales WHERE batch_id = %s",
                    (batch_id,),
                )
                stg_lines_count = cur.fetchone()[0]

                if stg_lines_count == 0:
                    raise ValueError(
                        f"No staged rows found for batch {batch_id}"
                    )

                cur.execute(fact_upsert_sql, (batch_id,))
                fact_rows_changed = cur.rowcount

                cur.execute(reject_upsert_sql, (batch_id,))
                rejection_rows_changed = cur.rowcount

                cur.execute(resolve_rejections_sql, (batch_id,))
                rejections_resolved = cur.rowcount

                cur.execute(audit_sql, (batch_id,))
                mismatches = cur.fetchall()

                if mismatches:
                    raise ValueError(
                        f"Reconciliation failed for batch {batch_id}: "
                        f"{mismatches}"
                    )

                cur.execute(rejection_audit_sql, (batch_id,))
                rejection_mismatches = cur.fetchall()

                
                if rejection_mismatches:
                    raise ValueError(
                        f"Rejection reconciliation failed for batch {batch_id}: "
                        f"{rejection_mismatches}"
                    )
 

        logging.info(
            "Batch %s committed: %s fact rows changed",
            batch_id,
            fact_rows_changed,
        )

        return {
            "batch_id": batch_id,
            "staged_line_count": stg_lines_count,
            "fact_rows_changed": fact_rows_changed,
            "rejection_rows_changed": rejection_rows_changed,
            "rejections_resolved": rejections_resolved,
        }

    except Exception:
        logging.exception("Batch %s failed", batch_id)
        raise
    
def main():
    parser = argparse.ArgumentParser(
    description="Load and reconcile a retail sales batch."
    )

    parser.add_argument("--batch-id",type=int,required=True)

    args = parser.parse_args()
    print(load_sales_batch(args.batch_id,{
    "host": "localhost",
    "dbname": "retail_warehouse",
    "user": "postgres",
    }))

if __name__ == "__main__":
    main()


