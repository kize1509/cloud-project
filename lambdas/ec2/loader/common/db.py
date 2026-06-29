"""PostgreSQL connection and idempotent per-table load helpers (psycopg2)."""

import os

from gold_tables import (
    create_table_sql,
    dataframe_to_rows,
    delete_for_date_sql,
    insert_sql,
)


def connect():
    import psycopg2

    return psycopg2.connect(
        host=os.environ["EC2_HOST"],
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=os.environ.get("DB_NAME", "metrics"),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        connect_timeout=10,
    )


def load_table(connection, table, target_date, dataframe):
    """Create the table if needed, delete the target date's rows, then insert fresh rows.

    Returns the number of rows inserted. Idempotent for re-runs of the same date.
    """
    from psycopg2.extras import execute_values

    rows = dataframe_to_rows(table, dataframe)
    with connection.cursor() as cursor:
        cursor.execute(create_table_sql(table))
        cursor.execute(delete_for_date_sql(table), (target_date,))
        if rows:
            execute_values(cursor, insert_sql(table), rows)
    return len(rows)
