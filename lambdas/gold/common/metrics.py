import pandas as pd

from gold_schema import (
    DATA_QUALITY_SCORE_COLUMNS,
    DAILY_HN_POST_COUNTS_COLUMNS,
    DAILY_USERS_METRIC_COLUMNS,
    HN_POST_TYPES,
    PLATFORM_HACKER_NEWS,
    PLATFORM_X,
    TOP_HN_JOBS_COLUMNS,
    TOP_HN_POSTS_COLUMNS,
    TOP_HN_USERS_COLUMNS,
    TOP_X_USERS_COLUMNS,
)


def _empty_frame(columns):
    return pd.DataFrame(columns=columns)


def _normalize_date(value):
    return pd.to_datetime(value).date()


def _filter_posts_on_date(posts_df, date):
    if posts_df.empty:
        return posts_df
    dates = pd.to_datetime(posts_df["created_at"], utc=True).dt.date
    return posts_df.loc[dates == _normalize_date(date)].copy()


def _filter_users_on_or_before_date(users_df, date):
    if users_df.empty:
        return users_df
    created = pd.to_datetime(users_df["created_at"], utc=True, errors="coerce")
    return users_df.loc[created.dt.date <= _normalize_date(date)].copy()


def _filter_users_created_on_date(users_df, date):
    if users_df.empty:
        return users_df
    created = pd.to_datetime(users_df["created_at"], utc=True, errors="coerce")
    return users_df.loc[created.dt.date == _normalize_date(date)].copy()


def compute_daily_hn_post_counts(posts_df, date):
    hn_posts = _filter_posts_on_date(
        posts_df.loc[posts_df["platform"] == PLATFORM_HACKER_NEWS],
        date,
    )
    if hn_posts.empty:
        return _empty_frame(DAILY_HN_POST_COUNTS_COLUMNS)

    counts = (
        hn_posts.groupby("post_type", as_index=False)
        .size()
        .rename(columns={"size": "count"})
    )
    counts = counts.loc[counts["post_type"].isin(HN_POST_TYPES)]
    counts["date"] = _normalize_date(date)
    return counts[DAILY_HN_POST_COUNTS_COLUMNS]


def compute_daily_users_metric(users_df, platform, date):
    platform_users = users_df.loc[users_df["platform"] == platform].copy()
    metric_date = _normalize_date(date)
    total_users = len(_filter_users_on_or_before_date(platform_users, metric_date))
    new_users = len(_filter_users_created_on_date(platform_users, metric_date))
    return pd.DataFrame(
        [
            {
                "date": metric_date,
                "platform": platform,
                "total_users": total_users,
                "new_users": new_users,
            }
        ]
    )


def _rank_hn_users_by_karma(posts_df, users_df, date, n=10, ascending=False):
    hn_posts = _filter_posts_on_date(
        posts_df.loc[posts_df["platform"] == PLATFORM_HACKER_NEWS],
        date,
    )
    if hn_posts.empty:
        return _empty_frame(TOP_HN_USERS_COLUMNS)

    authors = hn_posts[["author_username"]].drop_duplicates()
    hn_users = users_df.loc[users_df["platform"] == PLATFORM_HACKER_NEWS].copy()
    joined = authors.merge(
        hn_users,
        left_on="author_username",
        right_on="username",
        how="left",
    )
    joined = joined.dropna(subset=["karma_score"])
    if joined.empty:
        return _empty_frame(TOP_HN_USERS_COLUMNS)

    joined = joined.sort_values(
        ["karma_score", "username"],
        ascending=[ascending, True],
    ).head(n)
    joined["rank"] = range(1, len(joined) + 1)
    joined["date"] = _normalize_date(date)
    return joined[TOP_HN_USERS_COLUMNS]


def compute_top_hn_users_by_karma(posts_df, users_df, date, n=10):
    return _rank_hn_users_by_karma(posts_df, users_df, date, n=n, ascending=False)


def compute_bottom_hn_users_by_karma(posts_df, users_df, date, n=10):
    return _rank_hn_users_by_karma(posts_df, users_df, date, n=n, ascending=True)


def _rank_hn_posts(posts_df, date, post_types, columns, n=10):
    hn_posts = _filter_posts_on_date(
        posts_df.loc[posts_df["platform"] == PLATFORM_HACKER_NEWS],
        date,
    )
    if hn_posts.empty:
        return _empty_frame(columns)

    filtered = hn_posts.loc[hn_posts["post_type"].isin(post_types)].copy()
    filtered = filtered.dropna(subset=["score"])
    if filtered.empty:
        return _empty_frame(columns)

    filtered = filtered.sort_values(["score", "post_id"], ascending=[False, True]).head(n)
    filtered["rank"] = range(1, len(filtered) + 1)
    filtered["date"] = _normalize_date(date)
    return filtered[columns]


def compute_top_hn_posts_by_score(posts_df, date, n=10):
    return _rank_hn_posts(
        posts_df,
        date,
        post_types=HN_POST_TYPES - {"job"},
        columns=TOP_HN_POSTS_COLUMNS,
        n=n,
    )


def compute_top_hn_jobs_by_score(posts_df, date, n=10):
    return _rank_hn_posts(
        posts_df,
        date,
        post_types={"job"},
        columns=TOP_HN_JOBS_COLUMNS,
        n=n,
    )


def compute_top_x_users_by_followers(users_df, date, n=10):
    x_users = users_df.loc[users_df["platform"] == PLATFORM_X].copy()
    x_users = x_users.dropna(subset=["follower_count"])
    if x_users.empty:
        return _empty_frame(TOP_X_USERS_COLUMNS)

    ranked = x_users.sort_values(["follower_count", "username"], ascending=[False, True]).head(n)
    ranked["rank"] = range(1, len(ranked) + 1)
    ranked["date"] = _normalize_date(date)
    return ranked[TOP_X_USERS_COLUMNS]


def compute_data_quality_score(df, table_name, date, platform="all"):
    metric_date = _normalize_date(date)
    if df.empty:
        return pd.DataFrame(
            [
                {
                    "date": metric_date,
                    "table_name": table_name,
                    "platform": platform,
                    "non_null_pct": 0.0,
                }
            ]
        )

    total_cells = df.size
    non_null_cells = int(df.notna().sum().sum())
    non_null_pct = round((non_null_cells / total_cells) * 100.0, 2)
    return pd.DataFrame(
        [
            {
                "date": metric_date,
                "table_name": table_name,
                "platform": platform,
                "non_null_pct": non_null_pct,
            }
        ]
    )


def compute_all_metrics(posts_df, hn_users_df, x_users_df, date):
    users_df = pd.concat([hn_users_df, x_users_df], ignore_index=True)
    posts_quality = compute_data_quality_score(posts_df, "posts", date, platform="all")
    users_quality = compute_data_quality_score(users_df, "users", date, platform="all")

    return {
        "daily_users_metric_hn": compute_daily_users_metric(users_df, PLATFORM_HACKER_NEWS, date),
        "daily_users_metric_x": compute_daily_users_metric(users_df, PLATFORM_X, date),
        "daily_hn_post_counts": compute_daily_hn_post_counts(posts_df, date),
        "top_hn_users_by_karma": compute_top_hn_users_by_karma(posts_df, users_df, date),
        "bottom_hn_users_by_karma": compute_bottom_hn_users_by_karma(posts_df, users_df, date),
        "top_hn_posts_by_score": compute_top_hn_posts_by_score(posts_df, date),
        "top_hn_jobs_by_score": compute_top_hn_jobs_by_score(posts_df, date),
        "top_x_users_by_followers": compute_top_x_users_by_followers(users_df, date),
        "data_quality_posts": posts_quality,
        "data_quality_users": users_quality,
    }
