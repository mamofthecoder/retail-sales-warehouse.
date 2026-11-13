# Retail Sales Warehouse

A PostgreSQL retail warehouse with a Python batch loader, input validation,
rejection tracking, and reconciliation checks.

Built as a learning and portfolio project using synthetic retail data.

## Features

- Date and product dimensions with an order-line sales fact table.
- Daily reporting that preserves dates without sales.
- Batch validation before loading facts.
- Upserts that apply corrections and skip unchanged rows.
- Rejection records that can be resolved and reopened.
- Fact and rejection reconciliation before commit.
- Transaction rollback when loading or reconciliation fails.
- Command-line batch selection.
- Four unit tests and four PostgreSQL integration tests.

## Data model

| Table | Grain |
|---|---|
| dim_date | One row per calendar date |
| dim_product | One row per product |
| fact_sales | One row per order line |
| stg_sales | One row per order line per incoming batch |
| sales_load_rejections | One rejection record per batch and order line |

`fact_sales` references the date and product dimensions.
Its constraints require positive quantities and non-negative revenue.

Staging permits missing and invalid business values so they can be reviewed.
It uses typed columns, so malformed values such as text in an integer field
must be handled before insertion.

## Project files

- `load.py`: command-line loader and parameterized SQL.
- `sql/001_create_tables.sql`: warehouse table definitions.
- `sql/002_seed_dimensions.sql`: 2026 calendar and three sample products.
- `sql/003_reporting_views.sql`: daily sales summary view.
- `test_load.py`: unit tests using mocked connections.
- `test_load_integration.py`: tests against PostgreSQL.
- `requirements.txt`: direct dependencies.
- `requirements-lock.txt`: pinned dependencies from the tested environment.

## Requirements

Tested locally with Python 3.8.19 and PostgreSQL 16.

Psycopg requires the PostgreSQL client library, `libpq`, on the host.

Python 3.8 is the existing tested environment; compatibility with newer
Python versions has not yet been verified.

## Python setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python -m pip check
```

Configure PostgreSQL authentication locally using a password file.
Do not store database passwords in source code or Git.

On Linux, restrict the password file's permissions:

```bash
chmod 600 ~/.pgpass
```

## Create the warehouse

Create an empty PostgreSQL database named `retail_warehouse`, then run
these commands from the project root:

```bash
psql -h localhost -U postgres -d retail_warehouse \
  -v ON_ERROR_STOP=1 --single-transaction \
  -f sql/001_create_tables.sql \
  -f sql/002_seed_dimensions.sql \
  -f sql/003_reporting_views.sql
```

Run the table-creation script only against an empty database.
The seed and view scripts can be rerun.

Initial setup creates 365 dates, three products, and no sales facts.

## Load a sample batch

Insert these synthetic rows using pgAdmin or psql:

```sql
INSERT INTO stg_sales (
    batch_id, order_item_id, order_id, product_id,
    quantity, sale_date, line_revenue
)
VALUES
    (1, 601, 201, 7,  2, DATE '2026-01-08', 700.00),
    (1, 602, 201, 8, -2, DATE '2026-01-08', 150.00),
    (1, 603, 202, 999, 1, DATE '2026-01-08', 250.00);
```

Run the loader:

```bash
python load.py --batch-id 1
```

The current command-line connection settings use `localhost`,
database `retail_warehouse`, and user `postgres`. Authentication is
provided outside the source code.

For this fresh sample, line 601 loads successfully, line 602 is rejected
for invalid quantity, and line 603 is rejected for an unknown product.

The summary reports staged lines, fact rows changed, rejection rows
changed, and rejections resolved. Fact rows changed includes both
inserts and updates.

## Validation and transactions

Validation checks:

1. Missing or non-positive quantity.
2. Unknown product.
3. Missing date-dimension match.
4. Missing order ID.
5. Missing or negative revenue.

Each row receives its first matching validation failure.

Valid rows are upserted into facts. Invalid rows are recorded as
unresolved rejections. Invalid corrections preserve existing accepted facts.

Corrected valid lines can be loaded and their rejections marked resolved.
If they become invalid again, their rejection records reopen.

The loader audits valid facts and invalid-line rejection records before
committing. Any write failure or audit mismatch rolls back the transaction.
An empty batch raises an error.

## Reporting

```sql
SELECT *
FROM daily_sales_summary
ORDER BY full_date;
```

The view includes daily revenue, units, sales-line counts, distinct-order
counts, average order value, average line revenue, and revenue per unit.

Days without sales show zero counts and totals, with NULL averages.

For monthly revenue per unit, divide summed revenue by summed units.
Do not average daily rates.

Distinct-order counts cannot be summed across groups that share orders.
Return to the fact table when the required grouping changes.

## Tests

Create a separate database named `retail_warehouse_test` and configure
authentication for it.

```bash
python -m pytest -q test_load.py test_load_integration.py
```

Verified result: **8 passed**.

Integration tests create a unique schema per test, load the shared table
definitions, and remove the schema afterward. They do not use public
warehouse tables.

Coverage includes:

- Empty-batch handling.
- Successful summary generation.
- Fact and rejection audit failures.
- Loading valid rows and recording invalid rows.
- Unchanged reruns.
- Rejection resolution and reopening.
- Actual PostgreSQL rollback after either audit fails.
- Zero-sales dates in the daily reporting view.

## Limitations

- Synthetic sample data; no live business deployment.
- Rejection tracking retains the latest state per batch and line, rather
  than a complete event history.
- Concurrent loaders and conflicting corrections across batches are not
  yet coordinated.
- SQL validation logic is repeated across loader statements.
- The reporting calendar is initially seeded for 2026 only.
