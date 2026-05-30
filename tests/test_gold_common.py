import importlib.util
import sys
import unittest
from pathlib import Path


COMMON_DIR = Path(__file__).resolve().parents[1] / "lambdas" / "gold" / "common"
sys.path.insert(0, str(COMMON_DIR))

paths_spec = importlib.util.spec_from_file_location("gold_paths", COMMON_DIR / "paths.py")
paths = importlib.util.module_from_spec(paths_spec)
paths_spec.loader.exec_module(paths)


class GoldPathsTests(unittest.TestCase):
    def test_parse_silver_posts_key(self):
        parsed = paths.parse_silver_posts_key(
            "silver/posts/year=2026/month=05/day=28/c859dd70106047b1980cbabbbfcf488f.snappy.parquet"
        )
        self.assertEqual(parsed["date"], "2026-05-28")
        self.assertEqual(parsed["year"], "2026")
        self.assertEqual(parsed["month"], "05")
        self.assertEqual(parsed["day"], "28")

    def test_parse_silver_posts_key_rejects_invalid(self):
        with self.assertRaises(ValueError):
            paths.parse_silver_posts_key("silver/users/platform=X/data.parquet")

    def test_silver_posts_partition_prefix(self):
        self.assertEqual(
            paths.silver_posts_partition_prefix("2026", "05", "28"),
            "silver/posts/year=2026/month=05/day=28/",
        )

    def test_gold_table_path(self):
        path = paths.gold_table_path(
            "my-bucket",
            "gold",
            "daily_users_metric",
            {"platform": "HackerNews", "date": "2026-05-28"},
        )
        self.assertEqual(
            path,
            "s3://my-bucket/gold/daily_users_metric/platform=HackerNews/date=2026-05-28/",
        )


if __name__ == "__main__":
    unittest.main()
