"""Metadata and pure SQL helpers for loading gold Parquet tables into PostgreSQL.

Every gold table carries a ``date`` column, so idempotency is achieved by deleting the
rows for the target date and re-inserting them (mirroring the gold layer's
``overwrite_partitions`` write mode).
"""


class GoldTable:
    def __init__(self, name, columns, column_types):
        self.name = name
        self.columns = columns
        self.column_types = column_types


# Column order and PostgreSQL types match the gold schema in lambdas/gold/common/gold_schema.py.
GOLD_TABLES = [
    GoldTable(
        "daily_users_metric",
        ["date", "platform", "total_users", "new_users"],
        {"date": "DATE", "platform": "TEXT", "total_users": "INTEGER", "new_users": "INTEGER"},
    ),
    GoldTable(
        "daily_hn_post_counts",
        ["date", "post_type", "count"],
        {"date": "DATE", "post_type": "TEXT", "count": "INTEGER"},
    ),
    GoldTable(
        "top_hn_users_by_karma",
        ["date", "rank", "username", "karma_score"],
        {"date": "DATE", "rank": "INTEGER", "username": "TEXT", "karma_score": "INTEGER"},
    ),
    GoldTable(
        "bottom_hn_users_by_karma",
        ["date", "rank", "username", "karma_score"],
        {"date": "DATE", "rank": "INTEGER", "username": "TEXT", "karma_score": "INTEGER"},
    ),
    GoldTable(
        "top_hn_posts_by_score",
        ["date", "rank", "post_id", "post_type", "score"],
        {"date": "DATE", "rank": "INTEGER", "post_id": "TEXT", "post_type": "TEXT", "score": "INTEGER"},
    ),
    GoldTable(
        "top_hn_jobs_by_score",
        ["date", "rank", "post_id", "score"],
        {"date": "DATE", "rank": "INTEGER", "post_id": "TEXT", "score": "INTEGER"},
    ),
    GoldTable(
        "top_x_users_by_followers",
        ["date", "rank", "username", "follower_count"],
        {"date": "DATE", "rank": "INTEGER", "username": "TEXT", "follower_count": "BIGINT"},
    ),
    GoldTable(
        "data_quality_score",
        ["date", "table_name", "platform", "non_null_pct"],
        {"date": "DATE", "table_name": "TEXT", "platform": "TEXT", "non_null_pct": "DOUBLE PRECISION"},
    ),
]


def _quote_ident(name):
    # Wrap identifiers in double quotes so reserved words (rank, count) are safe.
    return '"' + name.replace('"', '""') + '"'


def create_table_sql(table):
    cols = ", ".join(f"{_quote_ident(col)} {table.column_types[col]}" for col in table.columns)
    return f"CREATE TABLE IF NOT EXISTS {_quote_ident(table.name)} ({cols})"


def delete_for_date_sql(table):
    return f"DELETE FROM {_quote_ident(table.name)} WHERE {_quote_ident('date')} = %s"


def insert_sql(table):
    cols = ", ".join(_quote_ident(col) for col in table.columns)
    return f"INSERT INTO {_quote_ident(table.name)} ({cols}) VALUES %s"


def _to_native(value):
    # psycopg2 cannot adapt numpy scalar types; coerce them to plain Python values.
    if value is None:
        return None
    item = getattr(value, "item", None)
    return item() if callable(item) else value


def dataframe_to_rows(table, dataframe):
    """Return a list of value tuples in this table's column order, with NaN/NaT -> None.

    numpy scalar types are coerced to native Python so psycopg2 can bind them.
    """
    if dataframe is None or dataframe.empty:
        return []

    frame = dataframe.reindex(columns=table.columns)
    frame = frame.astype(object).where(frame.notnull(), None)
    return [tuple(_to_native(value) for value in row) for row in frame.itertuples(index=False, name=None)]
