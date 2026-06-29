import concurrent.futures
import datetime as dt
import json
import os
import urllib.request


HN_API_BASE_URL = os.environ.get("HN_API_BASE_URL", "https://hacker-news.firebaseio.com/v0")
DEFAULT_ITEM_LABELS = {"story", "ask", "comment", "job", "poll"}


def parse_item_labels(value=None):
    raw_value = value if value is not None else os.environ.get("HN_ITEM_TYPES", "")
    if not raw_value:
        return set(DEFAULT_ITEM_LABELS)
    return {label.strip().lower() for label in raw_value.split(",") if label.strip()}


def resolve_target_date(event=None, offset=None, now=None):
    event = event or {}
    explicit_date = event.get("target_date") or event.get("date")
    if explicit_date:
        return dt.date.fromisoformat(explicit_date)

    if now is None:
        now = dt.datetime.now(dt.timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)

    if offset is None:
        offset = int(os.environ.get("HN_TARGET_DAY_OFFSET", "1"))
    return (now.astimezone(dt.timezone.utc).date() - dt.timedelta(days=int(offset)))


def target_day_window(target_date):
    start = dt.datetime.combine(target_date, dt.time.min, tzinfo=dt.timezone.utc)
    end = start + dt.timedelta(days=1)
    return int(start.timestamp()), int(end.timestamp())


def normalized_prefix(prefix):
    return prefix.strip("/")


def hackernews_bronze_key(target_date, bronze_prefix=None):
    prefix = normalized_prefix(bronze_prefix or os.environ.get("BRONZE_PREFIX", "bronze"))
    return (
        f"{prefix}/hackernews/"
        f"year={target_date:%Y}/month={target_date:%m}/day={target_date:%d}/items.json"
    )


def http_get_json(url, timeout=10):
    request = urllib.request.Request(url, headers={"User-Agent": "cloud-computing-prj-bronze/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body)


def fetch_max_item_id():
    return int(http_get_json(f"{HN_API_BASE_URL}/maxitem.json"))


def fetch_item(item_id):
    return http_get_json(f"{HN_API_BASE_URL}/item/{item_id}.json")


def item_matches_labels(item, labels):
    if not isinstance(item, dict):
        return False

    item_type = item.get("type")
    if item_type in labels:
        return True

    if "ask" in labels and item_type == "story":
        title = str(item.get("title", "")).lower()
        return title.startswith("ask hn:")

    return False


def collect_items_for_window(max_item_id, start_epoch, end_epoch, fetch_item_fn=fetch_item,
                             labels=None, batch_size=250, max_workers=16):
    labels = labels or parse_item_labels()
    items = []
    current_id = int(max_item_id)

    while current_id > 0:
        batch_ids = range(current_id, max(current_id - int(batch_size), 0), -1)
        batch_items = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=int(max_workers)) as executor:
            future_to_id = {executor.submit(fetch_item_fn, item_id): item_id for item_id in batch_ids}
            for future in concurrent.futures.as_completed(future_to_id):
                try:
                    item = future.result()
                except Exception as exc:
                    print(f"failed to fetch HN item {future_to_id[future]}: {exc}")
                    continue
                if isinstance(item, dict) and isinstance(item.get("time"), int):
                    batch_items.append(item)

        for item in batch_items:
            item_time = item["time"]
            if start_epoch <= item_time < end_epoch and item_matches_labels(item, labels):
                items.append(item)

        if batch_items and min(item["time"] for item in batch_items) < start_epoch:
            break

        current_id -= int(batch_size)

    return sorted(items, key=lambda item: item.get("id", 0))


def item_time_or_none(item_id, fetch_item_fn=fetch_item):
    item = fetch_item_fn(item_id)
    if isinstance(item, dict) and isinstance(item.get("time"), int):
        return item["time"]
    return None


def find_first_item_id_at_or_after(target_epoch, max_item_id, fetch_item_fn=fetch_item):
    low = 1
    high = int(max_item_id)
    result = high + 1

    while low <= high:
        mid = (low + high) // 2
        item_time = item_time_or_none(mid, fetch_item_fn)

        if item_time is None:
            low = mid + 1
        elif item_time >= target_epoch:
            result = mid
            high = mid - 1
        else:
            low = mid + 1

    return result


def discover_item_ids_for_window_official(start_epoch, end_epoch, max_item_id=None, fetch_item_fn=fetch_item):
    max_id = int(max_item_id if max_item_id is not None else fetch_max_item_id())
    first_id = find_first_item_id_at_or_after(start_epoch, max_id, fetch_item_fn=fetch_item_fn)
    after_end_id = find_first_item_id_at_or_after(end_epoch, max_id, fetch_item_fn=fetch_item_fn)

    if first_id > max_id:
        return []

    last_id = min(after_end_id - 1, max_id)
    if last_id < first_id:
        return []

    return list(range(first_id, last_id + 1))


def collect_raw_items_by_ids(item_ids, fetch_item_fn=fetch_item, labels=None, max_workers=24):
    labels = labels or parse_item_labels()
    items = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=int(max_workers)) as executor:
        future_to_id = {executor.submit(fetch_item_fn, item_id): item_id for item_id in item_ids}
        for future in concurrent.futures.as_completed(future_to_id):
            try:
                item = future.result()
            except Exception as exc:
                print(f"failed to fetch HN item {future_to_id[future]}: {exc}")
                continue
            if item_matches_labels(item, labels):
                items.append(item)

    return sorted(items, key=lambda item: item.get("id", 0))


def collect_items_for_window_fast(start_epoch, end_epoch, labels=None):
    labels = labels or parse_item_labels()
    item_ids = discover_item_ids_for_window_official(start_epoch, end_epoch)
    print(f"discovered {len(item_ids)} Hacker News item IDs for target window")
    return collect_raw_items_by_ids(item_ids, labels=labels)


def get_s3_client():
    import boto3

    return boto3.client("s3")


def get_ssm_client():
    import boto3

    return boto3.client("ssm")


def format_failure_message(stage, job, error, context=None):
    project = os.environ.get("PROJECT_NAME", "cloud-computing-prj")
    environment = os.environ.get("ENVIRONMENT", "dev")
    lines = [f"[{project}][{environment}][{stage}] {job} failed", f"Error: {error}"]

    clean_context = {key: value for key, value in (context or {}).items() if value not in (None, "", [], {})}
    if clean_context:
        context_text = " ".join(f"{key}={value}" for key, value in sorted(clean_context.items()))
        lines.append(f"Context: {context_text}")
    return "\n".join(lines)


def notify_failure(stage, job, error, context=None):
    parameter_name = os.environ.get("DISCORD_WEBHOOK_PARAMETER_NAME", "")
    if not parameter_name:
        return

    ssm = get_ssm_client()
    webhook_url = ssm.get_parameter(Name=parameter_name, WithDecryption=True)["Parameter"]["Value"]
    payload = json.dumps({"content": format_failure_message(stage, job, error, context)}).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "cloud-computing-prj-bronze/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        response.read()


def lambda_handler(event, context):
    target_date = None
    key = None
    try:
        bucket = os.environ["DATA_LAKE_BUCKET"]
        target_date = resolve_target_date(event)
        start_epoch, end_epoch = target_day_window(target_date)
        items = collect_items_for_window_fast(start_epoch, end_epoch)
        key = hackernews_bronze_key(target_date)

        body = json.dumps(items, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        get_s3_client().put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
        )

        return {
            "bucket": bucket,
            "key": key,
            "target_date": target_date.isoformat(),
            "item_count": len(items),
        }
    except Exception as exc:
        try:
            notify_failure(
                "bronze",
                "hackernews-ingest",
                exc,
                {"target_date": target_date.isoformat() if target_date else None, "s3_key": key},
            )
        except Exception as notify_exc:
            print(f"failed to send Discord notification: {notify_exc}")
        raise
