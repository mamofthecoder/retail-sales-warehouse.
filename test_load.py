from unittest.mock import MagicMock, patch

import pytest

from load import load_sales_batch


def mock_connection():
    context = MagicMock()
    conn = context.__enter__.return_value
    cur = conn.cursor.return_value.__enter__.return_value
    context.__exit__.return_value = False
    return context, cur


def test_empty_batch_stops_before_upserts():
    start_context, start_cur = mock_connection()
    load_context, load_cur = mock_connection()
    failure_context, failure_cur = mock_connection()

    start_cur.fetchone.return_value = (7,)
    load_cur.fetchone.return_value = (0,)

    with patch(
        "load.psycopg.connect",
        side_effect=[start_context, load_context, failure_context],
    ):
        with pytest.raises(ValueError, match="No staged rows found"):
            load_sales_batch(9999, {})

    assert load_cur.execute.call_count == 1

    start_context.__exit__.assert_called_once_with(None, None, None)
    assert load_context.__exit__.call_args.args[0] is ValueError
    failure_context.__exit__.assert_called_once_with(None, None, None)

    failure_sql, failure_params = failure_cur.execute.call_args.args
    assert "status = 'failed'" in failure_sql
    assert failure_params == (
        "No staged rows found for batch 9999",
        7,
    )


def test_unchanged_batch_returns_summary():
    start_context, start_cur = mock_connection()
    load_context, load_cur = mock_connection()

    start_cur.fetchone.return_value = (7,)
    load_cur.fetchone.return_value = (3,)
    load_cur.fetchall.side_effect = [[], []]
    load_cur.rowcount = 0

    with patch(
        "load.psycopg.connect",
        side_effect=[start_context, load_context],
    ):
        result = load_sales_batch(1, {})

    assert result == {
        "run_id": 7,
        "batch_id": 1,
        "staged_line_count": 3,
        "fact_rows_changed": 0,
        "rejection_rows_changed": 0,
        "rejections_resolved": 0,
    }

    start_context.__exit__.assert_called_once_with(None, None, None)
    load_context.__exit__.assert_called_once_with(None, None, None)

    success_sql, success_params = load_cur.execute.call_args.args
    assert "status = 'succeeded'" in success_sql
    assert success_params == (3, 0, 0, 0, 7)


@pytest.mark.parametrize(
    "audit_results, expected_message",
    [
        ([[(602,)]], "Reconciliation failed"),
        ([[], [(1, 602)]], "Rejection reconciliation failed"),
    ],
)
def test_audit_failure_rolls_back_and_records_failure(
    audit_results, expected_message
):
    start_context, start_cur = mock_connection()
    load_context, load_cur = mock_connection()
    failure_context, failure_cur = mock_connection()

    start_cur.fetchone.return_value = (7,)
    load_cur.fetchone.return_value = (3,)
    load_cur.fetchall.side_effect = audit_results
    load_cur.rowcount = 0

    with patch(
        "load.psycopg.connect",
        side_effect=[start_context, load_context, failure_context],
    ):
        with pytest.raises(ValueError, match=expected_message):
            load_sales_batch(1, {})

    assert load_context.__exit__.call_args.args[0] is ValueError
    failure_context.__exit__.assert_called_once_with(None, None, None)

    failure_sql, failure_params = failure_cur.execute.call_args.args
    assert "status = 'failed'" in failure_sql
    assert expected_message in failure_params[0]
    assert failure_params[1] == 7

    assert not any(
        "status = 'succeeded'" in call.args[0]
        for call in load_cur.execute.call_args_list
    )
