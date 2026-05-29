import datetime as dt
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMMON_DIR = ROOT / "lambdas" / "silver" / "common"


def load_module(name, filename):
    path = COMMON_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


schema = load_module("silver_schema", "schema.py")
ids = load_module("silver_ids", "ids.py")
timestamps = load_module("silver_timestamps", "timestamps.py")
html_clean = load_module("silver_html_clean", "html_clean.py")
paths = load_module("silver_paths", "paths.py")


class SilverCommonTests(unittest.TestCase):
    def test_user_id_is_stable(self):
        first = ids.user_id_for(schema.PLATFORM_HACKER_NEWS, "pg")
        second = ids.user_id_for(schema.PLATFORM_HACKER_NEWS, "pg")
        different = ids.user_id_for(schema.PLATFORM_X, "pg")

        self.assertEqual(first, second)
        self.assertNotEqual(first, different)

    def test_row_hash_is_stable(self):
        row = {"user_name": "alice", "date": "2020-07-25 12:27:21", "text": "hello"}
        self.assertEqual(ids.hash_csv_row(row), ids.hash_csv_row(dict(row)))

    def test_epoch_to_iso8601(self):
        self.assertEqual(
            timestamps.epoch_to_iso8601(1736978058),
            "2025-01-15T21:54:18+00:00",
        )

    def test_parse_naive_datetime_to_iso8601(self):
        self.assertEqual(
            timestamps.parse_naive_datetime_to_iso8601("2020-07-25 12:27:21"),
            "2020-07-25T12:27:21+00:00",
        )

    def test_partition_keys_from_iso8601(self):
        keys = timestamps.partition_keys_from_iso8601("2026-05-28T10:15:00+00:00")
        self.assertEqual(keys, {"year": "2026", "month": "05", "day": "28"})

    def test_strip_html(self):
        self.assertEqual(html_clean.strip_html("<p>Hello <i>world</i></p>"), "Hello world")

    def test_posts_partition_prefix(self):
        self.assertEqual(
            paths.posts_partition_prefix("silver", "2026", "05", "28"),
            "silver/posts/year=2026/month=05/day=28/",
        )


if __name__ == "__main__":
    unittest.main()
