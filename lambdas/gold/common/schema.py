PLATFORM_HACKER_NEWS = "Hacker News"
PLATFORM_X = "X"

USER_PARTITION_HACKER_NEWS = "HackerNews"
USER_PARTITION_X = "X"

HN_POST_TYPES = frozenset({"story", "ask", "comment", "job", "poll"})

DAILY_USERS_METRIC_COLUMNS = ["date", "platform", "total_users", "new_users"]
DAILY_HN_POST_COUNTS_COLUMNS = ["date", "post_type", "count"]
TOP_HN_USERS_COLUMNS = ["date", "rank", "username", "karma_score"]
TOP_HN_POSTS_COLUMNS = ["date", "rank", "post_id", "post_type", "score"]
TOP_HN_JOBS_COLUMNS = ["date", "rank", "post_id", "score"]
TOP_X_USERS_COLUMNS = ["date", "rank", "username", "follower_count"]
DATA_QUALITY_SCORE_COLUMNS = ["date", "table_name", "platform", "non_null_pct"]
