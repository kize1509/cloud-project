PLATFORM_HACKER_NEWS = "Hacker News"
PLATFORM_X = "X"

USER_PARTITION_HACKER_NEWS = "HackerNews"
USER_PARTITION_X = "X"

USER_COLUMNS = [
    "user_id",
    "username",
    "platform",
    "karma_score",
    "follower_count",
    "is_verified",
    "created_at",
]

POST_COLUMNS = [
    "post_id",
    "author_username",
    "platform",
    "content_text",
    "created_at",
    "post_type",
    "score",
    "parent_id",
    "source_dataset",
]

SUPPORTED_X_DATASETS = frozenset({"bitcoin-tweets", "covid-tweets"})
