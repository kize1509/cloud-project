import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


COMMON_DIR = Path(__file__).resolve().parents[1] / "lambdas" / "gold" / "common"
sys.path.insert(0, str(COMMON_DIR))

metrics_spec = importlib.util.spec_from_file_location("gold_metrics", COMMON_DIR / "metrics.py")
metrics = importlib.util.module_from_spec(metrics_spec)
metrics_spec.loader.exec_module(metrics)

schema_spec = importlib.util.spec_from_file_location("gold_schema", COMMON_DIR / "gold_schema.py")
schema = importlib.util.module_from_spec(schema_spec)
schema_spec.loader.exec_module(schema)


POSTS = pd.DataFrame(
    [
        {
            "post_id": "1",
            "author_username": "alice",
            "platform": schema.PLATFORM_HACKER_NEWS,
            "content_text": "story",
            "created_at": "2026-05-28T10:00:00+00:00",
            "post_type": "story",
            "score": 100,
            "parent_id": None,
            "source_dataset": None,
        },
        {
            "post_id": "2",
            "author_username": "bob",
            "platform": schema.PLATFORM_HACKER_NEWS,
            "content_text": "job",
            "created_at": "2026-05-28T11:00:00+00:00",
            "post_type": "job",
            "score": 50,
            "parent_id": None,
            "source_dataset": None,
        },
        {
            "post_id": "3",
            "author_username": "carol",
            "platform": schema.PLATFORM_X,
            "content_text": "tweet",
            "created_at": "2020-07-25T12:27:21+00:00",
            "post_type": "tweet",
            "score": None,
            "parent_id": None,
            "source_dataset": "covid-tweets",
        },
    ]
)

HN_USERS = pd.DataFrame(
    [
        {
            "user_id": "u1",
            "username": "alice",
            "platform": schema.PLATFORM_HACKER_NEWS,
            "karma_score": 500,
            "follower_count": None,
            "is_verified": None,
            "created_at": "2026-05-28T08:00:00+00:00",
        },
        {
            "user_id": "u2",
            "username": "bob",
            "platform": schema.PLATFORM_HACKER_NEWS,
            "karma_score": 20,
            "follower_count": None,
            "is_verified": None,
            "created_at": "2026-05-01T08:00:00+00:00",
        },
    ]
)

X_USERS = pd.DataFrame(
    [
        {
            "user_id": "u3",
            "username": "carol",
            "platform": schema.PLATFORM_X,
            "karma_score": None,
            "follower_count": 900,
            "is_verified": False,
            "created_at": "2017-05-26T05:46:42+00:00",
        }
    ]
)


class GoldMetricsTests(unittest.TestCase):
    def test_daily_hn_post_counts(self):
        result = metrics.compute_daily_hn_post_counts(POSTS, "2026-05-28")
        counts = dict(zip(result["post_type"], result["count"]))
        self.assertEqual(counts["story"], 1)
        self.assertEqual(counts["job"], 1)

    def test_daily_users_metric(self):
        users = pd.concat([HN_USERS, X_USERS], ignore_index=True)
        hn_metric = metrics.compute_daily_users_metric(users, schema.PLATFORM_HACKER_NEWS, "2026-05-28")
        self.assertEqual(hn_metric.iloc[0]["total_users"], 2)
        self.assertEqual(hn_metric.iloc[0]["new_users"], 1)

    def test_top_and_bottom_hn_users_by_karma(self):
        top = metrics.compute_top_hn_users_by_karma(POSTS, HN_USERS, "2026-05-28")
        bottom = metrics.compute_bottom_hn_users_by_karma(POSTS, HN_USERS, "2026-05-28")
        self.assertEqual(top.iloc[0]["username"], "alice")
        self.assertEqual(bottom.iloc[0]["username"], "bob")

    def test_top_hn_posts_and_jobs(self):
        posts = metrics.compute_top_hn_posts_by_score(POSTS, "2026-05-28")
        jobs = metrics.compute_top_hn_jobs_by_score(POSTS, "2026-05-28")
        self.assertEqual(posts.iloc[0]["post_id"], "1")
        self.assertEqual(jobs.iloc[0]["post_id"], "2")

    def test_top_x_users_by_followers(self):
        result = metrics.compute_top_x_users_by_followers(X_USERS, "2020-07-25")
        self.assertEqual(result.iloc[0]["username"], "carol")
        self.assertEqual(result.iloc[0]["follower_count"], 900)

    def test_data_quality_score(self):
        result = metrics.compute_data_quality_score(HN_USERS, "users", "2026-05-28")
        self.assertGreater(result.iloc[0]["non_null_pct"], 0)


if __name__ == "__main__":
    unittest.main()
