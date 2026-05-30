import os
import sys

COMMON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "common")
if os.path.isdir(COMMON_DIR) and COMMON_DIR not in sys.path:
    sys.path.insert(0, COMMON_DIR)

from metrics import compute_all_metrics  # noqa: E402
from paths import parse_silver_posts_key  # noqa: E402


def lambda_handler(event, context):
    from gold_io import write_all_metrics  # noqa: E402
    from notify import notify_failure  # noqa: E402
    from s3_events import extract_s3_objects  # noqa: E402
    from silver_io import read_silver_for_date  # noqa: E402

    try:
        bucket = os.environ["DATA_LAKE_BUCKET"]
        objects = extract_s3_objects(event or {})
        if not objects:
            raise ValueError("event did not contain any S3 object create records")

        results = []
        seen_dates = set()
        for source_bucket, key in objects:
            if source_bucket != bucket:
                raise ValueError(f"unexpected bucket {source_bucket}; expected {bucket}")

            partition = parse_silver_posts_key(key)
            date_key = partition["date"]
            if date_key in seen_dates:
                continue
            seen_dates.add(date_key)

            posts_df, hn_users_df, x_users_df = read_silver_for_date(
                bucket,
                partition["year"],
                partition["month"],
                partition["day"],
            )
            metrics = compute_all_metrics(posts_df, hn_users_df, x_users_df, date_key)
            paths = write_all_metrics(bucket, metrics)
            results.append(
                {
                    "source_key": key,
                    "date": date_key,
                    "post_count": len(posts_df),
                    "output_paths": paths,
                }
            )

        return {"results": results}
    except Exception as exc:
        try:
            notify_failure(f"Gold transformation failed: {exc}")
        except Exception as notify_exc:
            print(f"failed to send Discord notification: {notify_exc}")
        raise
