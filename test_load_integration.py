import os
import uuid
from pathlib import Path

import psycopg
from psycopg import sql
import pytest

from load import load_sales_batch
from unittest.mock import patch

@pytest.fixture
def warehouse_context():
    base_settings = {
        "host": os.getenv("PGHOST", "localhost"),
        "port": int(os.getenv("PGPORT", "5432")),
        "dbname": "retail_warehouse_test",
        "user": os.getenv("PGUSER", "postgres"),
    }

    schema = "warehouse_it_" + uuid.uuid4().hex
    settings = {
        **base_settings,
        "options": f"-c search_path={schema}",
    }

    ddl = (
        Path(__file__).resolve().parent
        / "sql"
        / "001_create_tables.sql"
    ).read_text()

    validation_view_ddl = (
    Path(__file__).resolve().parent
    / "sql"
    / "004_validated_sales_view.sql"
).read_text()
    

    created = False
    try:
        with psycopg.connect(**base_settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("CREATE SCHEMA {}").format(
                        sql.Identifier(schema)
                    )
                )
                cur.execute(
                    sql.SQL("SET LOCAL search_path TO {}").format(
                        sql.Identifier(schema)
                    )
                )
                cur.execute(ddl)
                cur.execute(validation_view_ddl)
        created = True

        yield settings

    finally:
        if created:
            with psycopg.connect(**base_settings) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        sql.SQL("DROP SCHEMA {} CASCADE").format(
                            sql.Identifier(schema)
                        )
                    )

def test_loads_valid_line_and_records_rejection(warehouse_context):
    settings = warehouse_context

    with psycopg.connect(**settings) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO dim_date
                    (date_key, full_date, year, month_number)
                VALUES (20260108, DATE '2026-01-08', 2026, 1);

                INSERT INTO dim_product
                    (product_id, product_name, product_category)
                VALUES (7, 'Keyboard', 'Accessories');

                INSERT INTO stg_sales (
                    batch_id, order_item_id, order_id, product_id,
                    quantity, sale_date, line_revenue
                )
                VALUES
                    (1, 601, 201, 7, 2, DATE '2026-01-08', 700),
                    (1, 602, 201, 7, -2, DATE '2026-01-08', 150);
            """)

    result = load_sales_batch(1, settings)

    assert result["staged_line_count"] == 2
    assert result["fact_rows_changed"] == 1
    assert result["rejection_rows_changed"] == 1
    assert result["rejections_resolved"] == 0

    # A new connection verifies that the loader committed its writes.
    with psycopg.connect(**settings) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT order_item_id, quantity, line_revenue
                FROM fact_sales
                ORDER BY order_item_id
            """)
            assert cur.fetchall() == [(601, 2, 700)]

            cur.execute("""
                SELECT order_item_id, rejection_reason,
                       resolved_at IS NULL
                FROM sales_load_rejections
                ORDER BY order_item_id
            """)
            assert cur.fetchall() == [(602, "Invalid Quantity", True)]
 
    rerun = load_sales_batch(1, settings)

    assert rerun["staged_line_count"] == 2
    assert rerun["fact_rows_changed"] == 0
    assert rerun["rejection_rows_changed"] == 0
    assert rerun["rejections_resolved"] == 0


    with psycopg.connect(**settings) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE stg_sales
                SET quantity = 2
                WHERE batch_id = 1 AND order_item_id = 602
            """)
    result = load_sales_batch(1, settings)

    assert result["staged_line_count"] == 2
    assert result["fact_rows_changed"] == 1
    assert result["rejection_rows_changed"] == 0
    assert result["rejections_resolved"] == 1

    with psycopg.connect(**settings) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT f.order_item_id, f.quantity, f.line_revenue,r.resolved_at IS NOT NULL
                FROM fact_sales f
                JOIN sales_load_rejections r ON f.order_item_id = r.order_item_id
                AND r.batch_id = 1
                WHERE f.order_item_id = 602
                ORDER BY order_item_id
            """)
            assert cur.fetchall() == [(602, 2, 150,True)]

    with psycopg.connect(**settings) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE stg_sales
                SET quantity = -2
                WHERE batch_id = 1 AND order_item_id = 602
            """)
    result = load_sales_batch(1, settings)

    assert result["staged_line_count"] == 2
    assert result["fact_rows_changed"] == 0
    assert result["rejection_rows_changed"] == 1
    assert result["rejections_resolved"] == 0

    with psycopg.connect(**settings) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT f.order_item_id, f.quantity, f.line_revenue,r.resolved_at IS NULL
                FROM fact_sales f
                JOIN sales_load_rejections r ON f.order_item_id = r.order_item_id
                AND r.batch_id = 1
                WHERE f.order_item_id = 602
                ORDER BY order_item_id
            """)
            assert cur.fetchall() == [(602, 2, 150,True)]

def test_fact_audit_failure_rolls_back(warehouse_context):
    settings = warehouse_context

    with psycopg.connect(**settings) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO dim_date
                    (date_key, full_date, year, month_number)
                VALUES (20260108, DATE '2026-01-08', 2026, 1);

                INSERT INTO dim_product
                    (product_id, product_name, product_category)
                VALUES (7, 'Keyboard', 'Accessories');

                INSERT INTO stg_sales (
                    batch_id, order_item_id, order_id, product_id,
                    quantity, sale_date, line_revenue
                )
                VALUES
                    (1, 601, 201, 7, 2, DATE '2026-01-08', 700),
                    (1, 602, 201, 7, -2, DATE '2026-01-08', 150);
            """)
    with patch("load.audit_sql", "SELECT %s::integer AS forced_mismatch"):
        with pytest.raises(ValueError, match="Reconciliation failed"):
            load_sales_batch(1, settings)

    with psycopg.connect(**settings) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM stg_sales")
            assert cur.fetchone()[0] == 2

            cur.execute("SELECT COUNT(*) FROM fact_sales")
            assert cur.fetchone()[0] == 0

            cur.execute("SELECT COUNT(*) FROM sales_load_rejections")
            assert cur.fetchone()[0] == 0

def test_rejection_audit_failure_rolls_back(warehouse_context):
    settings = warehouse_context

    with psycopg.connect(**settings) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO dim_date
                    (date_key, full_date, year, month_number)
                VALUES (20260108, DATE '2026-01-08', 2026, 1);

                INSERT INTO dim_product
                    (product_id, product_name, product_category)
                VALUES (7, 'Keyboard', 'Accessories');

                INSERT INTO stg_sales (
                    batch_id, order_item_id, order_id, product_id,
                    quantity, sale_date, line_revenue
                )
                VALUES
                    (1, 601, 201, 7, 2, DATE '2026-01-08', 700),
                    (1, 602, 201, 7, -2, DATE '2026-01-08', 150);
            """)
    with patch(
    "load.rejection_audit_sql",
    "SELECT %s::integer AS forced_mismatch",
    ):
        with pytest.raises(ValueError, match="Rejection reconciliation failed"):
            load_sales_batch(1, settings)

    with psycopg.connect(**settings) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM stg_sales")
            assert cur.fetchone()[0] == 2

            cur.execute("SELECT COUNT(*) FROM fact_sales")
            assert cur.fetchone()[0] == 0

            cur.execute("SELECT COUNT(*) FROM sales_load_rejections")
            assert cur.fetchone()[0] == 0

def test_daily_summary_preserves_zero_sales_dates(warehouse_context):
    settings = warehouse_context
    ddl2 = (
        Path(__file__).resolve().parent
        / "sql"
        / "002_seed_dimensions.sql"
    ).read_text()

    ddl3 = (
        Path(__file__).resolve().parent
        / "sql"
        / "003_reporting_views.sql"
    ).read_text()

    with psycopg.connect(**settings) as conn:
        with conn.cursor() as cur:
            cur.execute(ddl2)
            cur.execute(ddl3)

            cur.execute("SELECT COUNT(*) FROM daily_sales_summary")
            assert cur.fetchone()[0] == 365

            cur.execute("""SELECT sales_line_count,unique_order_count,average_order_value,average_revenue_per_sales_line,revenue_per_unit,
total_revenue,units_sold
     FROM daily_sales_summary WHERE sales_line_count IS DISTINCT FROM 0
   OR unique_order_count IS DISTINCT FROM 0
   OR total_revenue IS DISTINCT FROM 0
   OR units_sold IS DISTINCT FROM 0
   OR average_order_value IS NOT NULL
   OR average_revenue_per_sales_line IS NOT NULL
   OR revenue_per_unit IS NOT NULL""")
            assert cur.rowcount == 0
