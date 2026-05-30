import re


SILVER_POSTS_KEY_PATTERN = re.compile(
    r"^silver/posts/year=(?P<year>\d{4})/month=(?P<month>\d{2})/day=(?P<day>\d{2})/"
)


def parse_silver_posts_key(key):
    normalized = key.strip("/")
    match = SILVER_POSTS_KEY_PATTERN.match(normalized + "/")
    if not match:
        raise ValueError(f"unsupported silver posts key: {key}")

    year = match.group("year")
    month = match.group("month")
    day = match.group("day")
    return {
        "year": year,
        "month": month,
        "day": day,
        "date": f"{year}-{month}-{day}",
    }


def silver_posts_partition_prefix(year, month, day, silver_prefix="silver"):
    prefix = silver_prefix.strip("/")
    return f"{prefix}/posts/year={year}/month={month}/day={day}/"


def gold_table_path(bucket, gold_prefix, table_name, partitions):
    prefix = gold_prefix.strip("/")
    parts = [f"{key}={value}" for key, value in partitions.items()]
    partition_path = "/".join(parts)
    return f"s3://{bucket}/{prefix}/{table_name}/{partition_path}/"
