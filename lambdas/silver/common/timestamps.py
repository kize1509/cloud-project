import datetime as dt


def epoch_to_iso8601(epoch_seconds):
    if epoch_seconds is None:
        return None
    return dt.datetime.fromtimestamp(int(epoch_seconds), tz=dt.timezone.utc).isoformat()


def parse_naive_datetime_to_iso8601(value):
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        parsed = value
    else:
        text = str(value).strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = dt.datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"unsupported datetime format: {value}")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc).isoformat()


def partition_keys_from_iso8601(iso8601_value):
    parsed = dt.datetime.fromisoformat(iso8601_value.replace("Z", "+00:00"))
    parsed = parsed.astimezone(dt.timezone.utc)
    return {
        "year": f"{parsed.year:04d}",
        "month": f"{parsed.month:02d}",
        "day": f"{parsed.day:02d}",
    }
