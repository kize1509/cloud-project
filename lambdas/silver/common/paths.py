def normalized_prefix(prefix):
    return prefix.strip("/")


def posts_partition_prefix(silver_prefix, year, month, day):
    base = normalized_prefix(silver_prefix)
    return f"{base}/posts/year={year}/month={month}/day={day}/"


def users_partition_prefix(silver_prefix, platform_partition):
    base = normalized_prefix(silver_prefix)
    return f"{base}/users/platform={platform_partition}/"
