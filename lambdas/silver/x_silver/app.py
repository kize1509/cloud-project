import csv
import io
import os
import sys

COMMON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "common")
if os.path.isdir(COMMON_DIR) and COMMON_DIR not in sys.path:
    sys.path.insert(0, COMMON_DIR)

from ids import hash_csv_row, user_id_for  # noqa: E402
from schema import (  # noqa: E402
    PLATFORM_X,
    POST_COLUMNS,
    SUPPORTED_X_DATASETS,
    USER_COLUMNS,
    USER_PARTITION_X,
)
from timestamps import parse_naive_datetime_to_iso8601, partition_keys_from_iso8601  # noqa: E402


def parse_bronze_key(key):
    parts = key.strip("/").split("/")
    if len(parts) < 5 or parts[0] != "bronze" or parts[1] != "x" or parts[3] != "raw":
        raise ValueError(f"unsupported X bronze key: {key}")
    dataset = parts[2]
    if dataset not in SUPPORTED_X_DATASETS:
        raise ValueError(f"unsupported X dataset: {dataset}")
    filename = parts[-1]
    if not filename.endswith(".csv"):
        raise ValueError(f"expected csv file, got: {key}")
    return dataset


def parse_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def csv_row_to_post_row(row, dataset):
    created_at = parse_naive_datetime_to_iso8601(row.get("date"))
    partition = partition_keys_from_iso8601(created_at)
    is_retweet = parse_bool(row.get("is_retweet"))
    return {
        "post_id": hash_csv_row(row),
        "author_username": row.get("user_name"),
        "platform": PLATFORM_X,
        "content_text": row.get("text") or "",
        "created_at": created_at,
        "post_type": "retweet" if is_retweet else "tweet",
        "score": None,
        "parent_id": None,
        "source_dataset": dataset,
        "year": partition["year"],
        "month": partition["month"],
        "day": partition["day"],
    }


def csv_row_to_user_row(row):
    username = row.get("user_name")
    return {
        "user_id": user_id_for(PLATFORM_X, username),
        "username": username,
        "platform": PLATFORM_X,
        "karma_score": None,
        "follower_count": _to_int(row.get("user_followers")),
        "is_verified": parse_bool(row.get("user_verified")),
        "created_at": parse_naive_datetime_to_iso8601(row.get("user_created")),
    }


def _to_int(value):
    if value in (None, ""):
        return None
    return int(float(value))


def normalize_csv_rows(rows, dataset):
    posts = []
    users_by_name = {}

    for row in rows:
        if not row.get("user_name"):
            continue
        posts.append(csv_row_to_post_row(row, dataset))
        users_by_name[row["user_name"]] = csv_row_to_user_row(row)

    return posts, list(users_by_name.values())


def posts_and_users_to_frames(posts, users):
    import pandas as pd

    posts_df = pd.DataFrame(posts)
    users_df = pd.DataFrame(users)
    if not posts_df.empty:
        posts_df = posts_df[POST_COLUMNS + ["year", "month", "day"]]
    if not users_df.empty:
        users_df = users_df[USER_COLUMNS]
    return posts_df, users_df


def lambda_handler(event, context):
    from notify import notify_failure  # noqa: E402
    from parquet_io import read_object_bytes, write_posts_dataset, write_users_partition  # noqa: E402
    from s3_events import extract_s3_objects  # noqa: E402

    try:
        bucket = os.environ["DATA_LAKE_BUCKET"]
        objects = extract_s3_objects(event or {})
        if not objects:
            raise ValueError("event did not contain any S3 object create records")

        results = []
        for source_bucket, key in objects:
            if source_bucket != bucket:
                raise ValueError(f"unexpected bucket {source_bucket}; expected {bucket}")
            dataset = parse_bronze_key(key)
            csv_text = read_object_bytes(bucket, key).decode("utf-8")
            rows = list(csv.DictReader(io.StringIO(csv_text)))
            posts, users = normalize_csv_rows(rows, dataset)
            posts_df, users_df = posts_and_users_to_frames(posts, users)
            write_posts_dataset(bucket, posts_df)
            users_path = write_users_partition(bucket, USER_PARTITION_X, users_df)
            results.append(
                {
                    "source_key": key,
                    "dataset": dataset,
                    "post_count": len(posts),
                    "user_count": len(users),
                    "users_path": users_path,
                }
            )

        return {"results": results}
    except Exception as exc:
        try:
            notify_failure(f"X silver normalization failed: {exc}")
        except Exception as notify_exc:
            print(f"failed to send Discord notification: {notify_exc}")
        raise
