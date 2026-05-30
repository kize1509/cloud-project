import os

from gold_schema import (
    DATA_QUALITY_SCORE_COLUMNS,
    DAILY_HN_POST_COUNTS_COLUMNS,
    DAILY_USERS_METRIC_COLUMNS,
    TOP_HN_JOBS_COLUMNS,
    TOP_HN_POSTS_COLUMNS,
    TOP_HN_USERS_COLUMNS,
    TOP_X_USERS_COLUMNS,
)


def _write_dataset(dataframe, path, partition_cols):
    import awswrangler as wr

    if dataframe.empty:
        return path

    wr.s3.to_parquet(
        df=dataframe,
        path=path,
        dataset=True,
        partition_cols=partition_cols,
        mode="overwrite_partitions",
    )
    return path


def _gold_prefix():
    return os.environ.get("GOLD_PREFIX", "gold").strip("/")


def _gold_root(bucket):
    return f"s3://{bucket}/{_gold_prefix()}"


def write_daily_users_metric(bucket, dataframe):
    path = f"{_gold_root(bucket)}/daily_users_metric/"
    return _write_dataset(dataframe, path, ["platform", "date"])


def write_daily_hn_post_counts(bucket, dataframe):
    path = f"{_gold_root(bucket)}/daily_hn_post_counts/"
    return _write_dataset(dataframe, path, ["date"])


def write_top_hn_users_by_karma(bucket, dataframe):
    path = f"{_gold_root(bucket)}/top_hn_users_by_karma/"
    return _write_dataset(dataframe, path, ["date"])


def write_bottom_hn_users_by_karma(bucket, dataframe):
    path = f"{_gold_root(bucket)}/bottom_hn_users_by_karma/"
    return _write_dataset(dataframe, path, ["date"])


def write_top_hn_posts_by_score(bucket, dataframe):
    path = f"{_gold_root(bucket)}/top_hn_posts_by_score/"
    return _write_dataset(dataframe, path, ["date"])


def write_top_hn_jobs_by_score(bucket, dataframe):
    path = f"{_gold_root(bucket)}/top_hn_jobs_by_score/"
    return _write_dataset(dataframe, path, ["date"])


def write_top_x_users_by_followers(bucket, dataframe):
    path = f"{_gold_root(bucket)}/top_x_users_by_followers/"
    return _write_dataset(dataframe, path, ["date"])


def write_data_quality_scores(bucket, dataframes):
    import pandas as pd

    combined = pd.concat(dataframes, ignore_index=True)
    if combined.empty:
        return f"{_gold_root(bucket)}/data_quality_score/"
    combined = combined[DATA_QUALITY_SCORE_COLUMNS]
    path = f"{_gold_root(bucket)}/data_quality_score/"
    return _write_dataset(combined, path, ["date", "table_name"])


def write_all_metrics(bucket, metrics):
    paths = {
        "daily_users_metric": write_daily_users_metric(
            bucket,
            _concat_users_metrics(
                metrics["daily_users_metric_hn"],
                metrics["daily_users_metric_x"],
            ),
        ),
        "daily_hn_post_counts": write_daily_hn_post_counts(bucket, metrics["daily_hn_post_counts"]),
        "top_hn_users_by_karma": write_top_hn_users_by_karma(bucket, metrics["top_hn_users_by_karma"]),
        "bottom_hn_users_by_karma": write_bottom_hn_users_by_karma(
            bucket,
            metrics["bottom_hn_users_by_karma"],
        ),
        "top_hn_posts_by_score": write_top_hn_posts_by_score(bucket, metrics["top_hn_posts_by_score"]),
        "top_hn_jobs_by_score": write_top_hn_jobs_by_score(bucket, metrics["top_hn_jobs_by_score"]),
        "top_x_users_by_followers": write_top_x_users_by_followers(bucket, metrics["top_x_users_by_followers"]),
        "data_quality_score": write_data_quality_scores(
            bucket,
            [metrics["data_quality_posts"], metrics["data_quality_users"]],
        ),
    }
    return paths


def _concat_users_metrics(hn_df, x_df):
    import pandas as pd

    frames = [frame for frame in (hn_df, x_df) if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=DAILY_USERS_METRIC_COLUMNS)
    return pd.concat(frames, ignore_index=True)[DAILY_USERS_METRIC_COLUMNS]
