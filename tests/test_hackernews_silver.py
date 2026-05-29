import importlib.util
import sys
import unittest
from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "lambdas" / "silver" / "hackernews_silver" / "app.py"
COMMON_DIR = Path(__file__).resolve().parents[1] / "lambdas" / "silver" / "common"
sys.path.insert(0, str(COMMON_DIR))

SPEC = importlib.util.spec_from_file_location("hackernews_silver_app", APP_PATH)
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)


class HackerNewsSilverTests(unittest.TestCase):
    def test_resolve_post_type_for_ask(self):
        item = {"type": "story", "title": "Ask HN: Example?"}
        self.assertEqual(app.resolve_post_type(item), "ask")

    def test_should_skip_deleted_items(self):
        self.assertTrue(app.should_skip_item({"deleted": True, "by": "pg"}))
        self.assertTrue(app.should_skip_item({"by": None}))

    def test_item_to_post_row(self):
        item = {
            "id": 42,
            "type": "comment",
            "by": "pg",
            "time": 1736978058,
            "text": "<p>hello</p>",
            "parent": 10,
            "score": 5,
        }
        row = app.item_to_post_row(item)
        self.assertEqual(row["post_id"], "42")
        self.assertEqual(row["post_type"], "comment")
        self.assertEqual(row["parent_id"], "10")
        self.assertEqual(row["content_text"], "hello")
        self.assertEqual(row["year"], "2025")

    def test_normalize_hackernews_items(self):
        items = [
            {"id": 1, "type": "story", "by": "alice", "time": 1736978058, "title": "Hello"},
            {"id": 2, "type": "comment", "by": "bob", "time": 1736978059, "text": "Nice", "parent": 1},
            {"deleted": True, "by": "ghost", "id": 3, "time": 1736978060},
        ]
        posts, users = app.normalize_hackernews_items(
            items,
            fetch_user_fn=lambda username: {"karma": 123, "created": 1000},
        )
        self.assertEqual(len(posts), 2)
        self.assertEqual({user["username"] for user in users}, {"alice", "bob"})
        self.assertEqual(users[0]["karma_score"], 123)


if __name__ == "__main__":
    unittest.main()
