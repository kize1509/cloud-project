import datetime as dt
import importlib.util
import json
from pathlib import Path
import unittest


APP_PATH = Path(__file__).resolve().parents[1] / "lambdas" / "bronze" / "hackernews_ingest" / "app.py"
SPEC = importlib.util.spec_from_file_location("hackernews_ingest_app", APP_PATH)
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)


class HackerNewsIngestTests(unittest.TestCase):
    def test_resolve_target_date_uses_previous_utc_day_by_default(self):
        now = dt.datetime(2026, 5, 29, 12, 30, tzinfo=dt.timezone.utc)

        self.assertEqual(app.resolve_target_date({}, now=now), dt.date(2026, 5, 28))

    def test_target_day_window_is_utc_midnight_to_midnight(self):
        start, end = app.target_day_window(dt.date(2026, 5, 28))

        self.assertEqual(start, 1779926400)
        self.assertEqual(end, 1780012800)

    def test_hackernews_bronze_key_matches_partition_layout(self):
        key = app.hackernews_bronze_key(dt.date(2026, 5, 8), "bronze/")

        self.assertEqual(key, "bronze/hackernews/year=2026/month=05/day=08/items.json")

    def test_collect_items_preserves_raw_item_payloads(self):
        start, end = app.target_day_window(dt.date(2026, 5, 28))
        raw_story = {"id": 3, "type": "story", "time": start + 10, "title": "<b>Raw</b>", "kids": [4]}
        raw_comment = {"id": 2, "type": "comment", "time": start + 20, "text": "<p>unchanged</p>"}
        old_item = {"id": 1, "type": "story", "time": start - 10, "title": "old"}
        fixtures = {1: old_item, 2: raw_comment, 3: raw_story}

        items = app.collect_items_for_window(
            3,
            start,
            end,
            fetch_item_fn=lambda item_id: fixtures[item_id],
            labels={"story", "comment"},
            batch_size=3,
            max_workers=1,
        )

        self.assertEqual(items, [raw_comment, raw_story])
        self.assertEqual(json.loads(json.dumps(items, ensure_ascii=False)), [raw_comment, raw_story])

    def test_collect_raw_items_by_ids_preserves_firebase_payloads(self):
        raw_story = {"id": 10, "type": "story", "time": 1, "title": "<b>Raw</b>"}
        raw_comment = {"id": 11, "type": "comment", "time": 1, "text": "<p>unchanged</p>"}
        fixtures = {10: raw_story, 11: raw_comment, 12: {"id": 12, "type": "pollopt", "time": 1}}

        items = app.collect_raw_items_by_ids(
            [12, 11, 10],
            fetch_item_fn=lambda item_id: fixtures[item_id],
            labels={"story", "comment"},
            max_workers=1,
        )

        self.assertEqual(items, [raw_story, raw_comment])

    def test_official_api_item_id_discovery_uses_target_time_window(self):
        fixtures = {
            1: {"id": 1, "time": 10},
            2: {"id": 2, "time": 20},
            3: {"id": 3, "time": 30},
            4: {"id": 4, "time": 40},
            5: {"id": 5, "time": 50},
        }

        item_ids = app.discover_item_ids_for_window_official(
            20,
            50,
            max_item_id=5,
            fetch_item_fn=lambda item_id: fixtures[item_id],
        )

        self.assertEqual(item_ids, [2, 3, 4])


if __name__ == "__main__":
    unittest.main()
