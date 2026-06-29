import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

COMMON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "common")
if os.path.isdir(COMMON_DIR) and COMMON_DIR not in sys.path:
    sys.path.insert(0, COMMON_DIR)

from html_clean import strip_html  # noqa: E402
from ids import user_id_for  # noqa: E402
from schema import PLATFORM_HACKER_NEWS, POST_COLUMNS, USER_COLUMNS, USER_PARTITION_HACKER_NEWS  # noqa: E402
from timestamps import epoch_to_iso8601, partition_keys_from_iso8601  # noqa: E402


HN_API_BASE_URL = os.environ.get("HN_API_BASE_URL", "https://hacker-news.firebaseio.com/v0")
DEFAULT_HN_USER_FETCH_WORKERS = 32
DEFAULT_HN_USER_FETCH_TIMEOUT_SECONDS = 3


def should_skip_item(item):
    if not isinstance(item, dict):
        return True
    if item.get("deleted") or item.get("dead"):
        return True
    if not item.get("by"):
        return True
    return False


def resolve_post_type(item):
    item_type = item.get("type")
    if item_type == "story":
        title = str(item.get("title", "")).lower()
        if title.startswith("ask hn:"):
            return "ask"
    return item_type


def build_content_text(item):
    parts = []
    title = strip_html(item.get("title"))
    text = strip_html(item.get("text"))
    if title:
        parts.append(title)
    if text:
        parts.append(text)
    return "\n".join(parts).strip()


def item_to_post_row(item):
    created_at = epoch_to_iso8601(item.get("time"))
    partition = partition_keys_from_iso8601(created_at)
    parent_id = item.get("parent")
    return {
        "post_id": str(item["id"]),
        "author_username": item["by"],
        "platform": PLATFORM_HACKER_NEWS,
        "content_text": build_content_text(item),
        "created_at": created_at,
        "post_type": resolve_post_type(item),
        "score": item.get("score"),
        "parent_id": str(parent_id) if parent_id is not None else None,
        "source_dataset": None,
        "year": partition["year"],
        "month": partition["month"],
        "day": partition["day"],
    }


def http_get_json(url, timeout=DEFAULT_HN_USER_FETCH_TIMEOUT_SECONDS):
    request = urllib.request.Request(url, headers={"User-Agent": "cloud-computing-prj-silver/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body)


def fetch_hn_user(username, fetch_fn=None):
    fetch_fn = fetch_fn or (lambda name: http_get_json(f"{HN_API_BASE_URL}/user/{name}.json"))
    try:
        payload = fetch_fn(username)
    except Exception:
        return {"karma_score": None, "created_at": None}
    if not isinstance(payload, dict):
        return {"karma_score": None, "created_at": None}
    return {
        "karma_score": payload.get("karma"),
        "created_at": epoch_to_iso8601(payload.get("created")),
    }


def _positive_int_from_env(name, default):
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def fetch_hn_users(usernames, fetch_user_fn=None, max_workers=None):
    usernames = sorted(set(usernames))
    if not usernames:
        return {}

    max_workers = max_workers or _positive_int_from_env("HN_USER_FETCH_WORKERS", DEFAULT_HN_USER_FETCH_WORKERS)
    max_workers = min(max_workers, len(usernames))

    profiles = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_username = {
            executor.submit(fetch_hn_user, username, fetch_user_fn): username for username in usernames
        }
        for future in as_completed(future_to_username):
            username = future_to_username[future]
            try:
                profiles[username] = future.result()
            except Exception:
                profiles[username] = {"karma_score": None, "created_at": None}
    return profiles


def build_user_row(username, profile):
    return {
        "user_id": user_id_for(PLATFORM_HACKER_NEWS, username),
        "username": username,
        "platform": PLATFORM_HACKER_NEWS,
        "karma_score": profile.get("karma_score"),
        "follower_count": None,
        "is_verified": None,
        "created_at": profile.get("created_at"),
    }


def normalize_hackernews_items(items, fetch_user_fn=None):
    posts = []
    usernames = set()

    for item in items:
        if should_skip_item(item):
            continue
        posts.append(item_to_post_row(item))
        usernames.add(item["by"])

    profiles = fetch_hn_users(usernames, fetch_user_fn=fetch_user_fn)
    users = [build_user_row(username, profiles[username]) for username in sorted(usernames)]

    return posts, users


def posts_and_users_to_frames(posts, users):
    import pandas as pd

    posts_df = pd.DataFrame(posts)
    users_df = pd.DataFrame(users)
    if not posts_df.empty:
        posts_df = posts_df[POST_COLUMNS + ["year", "month", "day"]]
    if not users_df.empty:
        users_df = users_df[USER_COLUMNS]
    return posts_df, users_df


def parse_bronze_key(key):
    parts = key.strip("/").split("/")
    if len(parts) < 6 or parts[0] != "bronze" or parts[1] != "hackernews":
        raise ValueError(f"unsupported Hacker News bronze key: {key}")
    if parts[-1] != "items.json":
        raise ValueError(f"expected items.json, got: {key}")
    return key


def lambda_handler(event, context):
    from notify import notify_failure  # noqa: E402
    from parquet_io import read_json_from_s3, write_posts_dataset, write_users_partition  # noqa: E402
    from s3_events import extract_s3_objects  # noqa: E402

    current_key = None
    try:
        bucket = os.environ["DATA_LAKE_BUCKET"]
        objects = extract_s3_objects(event or {})
        if not objects:
            raise ValueError("event did not contain any S3 object create records")

        results = []
        for source_bucket, key in objects:
            current_key = key
            if source_bucket != bucket:
                raise ValueError(f"unexpected bucket {source_bucket}; expected {bucket}")
            parse_bronze_key(key)
            payload = json.loads(read_json_from_s3(bucket, key).decode("utf-8"))
            if not isinstance(payload, list):
                raise ValueError(f"expected JSON array in {key}")

            posts, users = normalize_hackernews_items(payload)
            posts_df, users_df = posts_and_users_to_frames(posts, users)
            write_posts_dataset(bucket, posts_df)
            users_path = write_users_partition(bucket, USER_PARTITION_HACKER_NEWS, users_df)
            results.append(
                {
                    "source_key": key,
                    "post_count": len(posts),
                    "user_count": len(users),
                    "users_path": users_path,
                }
            )

        return {"results": results}
    except Exception as exc:
        try:
            notify_failure("silver", "hackernews-normalize", exc, {"source_key": current_key})
        except Exception as notify_exc:
            print(f"failed to send Discord notification: {notify_exc}")
        raise
