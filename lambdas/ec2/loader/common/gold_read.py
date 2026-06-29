"""Read a gold Parquet table for a single date via awswrangler.

Every gold table is partitioned by ``date`` (some additionally by platform / table_name),
so we read the dataset with a partition filter on the date and let the partition columns
come back as regular columns.
"""

import os


def _gold_prefix():
    return os.environ.get("GOLD_PREFIX", "gold").strip("/")


def gold_table_root(bucket, table_name):
    return f"s3://{bucket}/{_gold_prefix()}/{table_name}/"


def read_gold_table_for_date(bucket, table_name, target_date):
    import awswrangler as wr

    path = gold_table_root(bucket, table_name)
    try:
        return wr.s3.read_parquet(
            path=path,
            dataset=True,
            partition_filter=lambda partitions: partitions.get("date") == target_date,
        )
    except wr.exceptions.NoFilesFound:
        import pandas as pd

        return pd.DataFrame()
