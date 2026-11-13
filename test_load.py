from unittest.mock import MagicMock, patch

import pytest

from load import load_sales_batch


def test_empty_batch_stops_before_upserts():
    with patch("load.psycopg.connect") as connect:
        conn = MagicMock()
        cur = MagicMock()
        connect.return_value.__enter__.return_value = conn
        conn.cursor.return_value.__enter__.return_value = cur
        cur.fetchone.return_value = (0,)

        with pytest.raises(ValueError, match="No staged rows found"):
            load_sales_batch(9999, {})
	
        assert cur.execute.call_count == 1
        
def test_unchanged_batch_returns_summary():
    with patch("load.psycopg.connect") as connect:
           conn = MagicMock()
           cur = MagicMock()
           connect.return_value.__enter__.return_value = conn
           conn.cursor.return_value.__enter__.return_value = cur
            
           cur.fetchone.return_value = (3,)
           cur.fetchall.side_effect = [[], []]
           cur.rowcount = 0
           
           result = load_sales_batch(1, {})
           expected = {
                "batch_id": 1,
                "staged_line_count": 3,
                "fact_rows_changed": 0,
                "rejection_rows_changed": 0,
                "rejections_resolved": 0,
            }
            
           assert result == expected
           connect.return_value.__exit__.assert_called_once_with(None, None, None)
           
def test_fact_audit_failure_raises():
    with patch("load.psycopg.connect") as connect:
           conn = MagicMock()
           cur = MagicMock()
           connect.return_value.__enter__.return_value = conn
           conn.cursor.return_value.__enter__.return_value = cur
            
           cur.fetchone.return_value = (3,)
           cur.fetchall.return_value = [(602,)]
           cur.rowcount = 0

           with pytest.raises(ValueError, match="Reconciliation failed"):
                load_sales_batch(1, {})

def test_rejection_audit_failure_raises():
    with patch("load.psycopg.connect") as connect:
           conn = MagicMock()
           cur = MagicMock()
           connect.return_value.__enter__.return_value = conn
           conn.cursor.return_value.__enter__.return_value = cur
            
           cur.fetchone.return_value = (3,)
           cur.fetchall.side_effect = [[], [(1, 602)]]
           cur.rowcount = 0

           with pytest.raises(ValueError, match="Rejection reconciliation failed"):
                load_sales_batch(1, {}) 

           assert connect.return_value.__exit__.call_args.args[0] is ValueError
