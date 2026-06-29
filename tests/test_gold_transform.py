import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


APP_PATH = Path(__file__).resolve().parents[1] / "lambdas" / "gold" / "gold_transform" / "app.py"
COMMON_DIR = Path(__file__).resolve().parents[1] / "lambdas" / "gold" / "common"
sys.path.insert(0, str(COMMON_DIR))

SPEC = importlib.util.spec_from_file_location("gold_transform_app", APP_PATH)
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)

silver_io_spec = importlib.util.spec_from_file_location("gold_silver_io", COMMON_DIR / "silver_io.py")
silver_io = importlib.util.module_from_spec(silver_io_spec)
silver_io_spec.loader.exec_module(silver_io)


POSTS = pd.DataFrame(
    [
        {
            "post_id": "1",
            "author_username": "alice",
            "platform": "Hacker News",
            "content_text": "story",
            "created_at": "2026-05-28T10:00:00+00:00",
            "post_type": "story",
            "score": 10,
            "parent_id": None,
            "source_dataset": None,
        }
    ]
)
HN_USERS = pd.DataFrame(
    [
        {
            "user_id": "u1",
            "username": "alice",
            "platform": "Hacker News",
            "karma_score": 100,
            "follower_count": None,
            "is_verified": None,
            "created_at": "2026-05-28T08:00:00+00:00",
        }
    ]
)
X_USERS = pd.DataFrame(
    columns=[
        "user_id",
        "username",
        "platform",
        "karma_score",
        "follower_count",
        "is_verified",
        "created_at",
    ]
)


class GoldTransformTests(unittest.TestCase):
    @patch.dict(
        os.environ,
        {"DATA_LAKE_BUCKET": "test-bucket", "SILVER_PREFIX": "silver", "GOLD_PREFIX": "gold"},
    )
    @patch("gold_io.write_all_metrics")
    @patch("silver_io.read_silver_for_date")
    def test_lambda_handler(self, read_silver_mock, write_metrics_mock):
        read_silver_mock.return_value = (POSTS, HN_USERS, X_USERS)
        write_metrics_mock.return_value = {"daily_users_metric": "s3://test-bucket/gold/daily_users_metric/"}

        event = {
            "source": "aws.s3",
            "detail-type": "Object Created",
            "detail": {
                "bucket": {"name": "test-bucket"},
                "object": {"key": "silver/posts/year=2026/month=05/day=28/part.parquet"},
            },
        }
        result = app.lambda_handler(event, None)

        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["date"], "2026-05-28")
        read_silver_mock.assert_called_once_with("test-bucket", "2026", "05", "28")
        write_metrics_mock.assert_called_once()

    def test_read_users_snapshot_maps_hn_partition_to_platform_value(self):
        dataframe = pd.DataFrame(
            [
                {
                    "username": "alice",
                    "platform": "HackerNews",
                    "karma_score": 100,
                    "created_at": "2026-05-28T08:00:00+00:00",
                }
            ]
        )

        fake_wr = types.SimpleNamespace(
            s3=types.SimpleNamespace(read_parquet=lambda **kwargs: dataframe.copy()),
            exceptions=types.SimpleNamespace(NoFilesFound=Exception),
        )

        with patch.dict(sys.modules, {"awswrangler": fake_wr}):
            result = silver_io.read_users_snapshot("bucket", "HackerNews")

        self.assertEqual(result.iloc[0]["platform"], "Hacker News")


if __name__ == "__main__":
    unittest.main()
