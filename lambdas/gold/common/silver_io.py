import os

from gold_schema import PLATFORM_HACKER_NEWS, PLATFORM_X, USER_PARTITION_HACKER_NEWS, USER_PARTITION_X


def read_posts_partition(bucket, year, month, day, silver_prefix="silver"):
    import awswrangler as wr

    prefix = silver_prefix.strip("/")
    path = f"s3://{bucket}/{prefix}/posts/year={year}/month={month}/day={day}/"
    try:
        return wr.s3.read_parquet(path=path, dataset=True)
    except wr.exceptions.NoFilesFound:
        import pandas as pd

        return pd.DataFrame()


def read_users_snapshot(bucket, platform_partition, silver_prefix="silver"):
    import awswrangler as wr

    prefix = silver_prefix.strip("/")
    path = f"s3://{bucket}/{prefix}/users/platform={platform_partition}/"
    try:
        dataframe = wr.s3.read_parquet(path=path, dataset=True)
    except wr.exceptions.NoFilesFound:
        import pandas as pd

        return pd.DataFrame()
    if platform_partition == USER_PARTITION_HACKER_NEWS:
        dataframe["platform"] = PLATFORM_HACKER_NEWS
    elif platform_partition == USER_PARTITION_X:
        dataframe["platform"] = PLATFORM_X
    return dataframe


def read_silver_for_date(bucket, year, month, day):
    silver_prefix = os.environ.get("SILVER_PREFIX", "silver")
    posts_df = read_posts_partition(bucket, year, month, day, silver_prefix=silver_prefix)
    hn_users_df = read_users_snapshot(bucket, USER_PARTITION_HACKER_NEWS, silver_prefix=silver_prefix)
    x_users_df = read_users_snapshot(bucket, USER_PARTITION_X, silver_prefix=silver_prefix)
    return posts_df, hn_users_df, x_users_df
