import importlib.util
import sys
import unittest
from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "lambdas" / "silver" / "x_silver" / "app.py"
COMMON_DIR = Path(__file__).resolve().parents[1] / "lambdas" / "silver" / "common"
sys.path.insert(0, str(COMMON_DIR))

SPEC = importlib.util.spec_from_file_location("x_silver_app", APP_PATH)
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)


SAMPLE_ROW = {
    "user_name": "alice",
    "user_location": "NYC",
    "user_description": "bio",
    "user_created": "2017-05-26 05:46:42",
    "user_followers": "624",
    "user_friends": "950",
    "user_favourites": "18775",
    "user_verified": "False",
    "date": "2020-07-25 12:27:21",
    "text": "hello covid",
    "hashtags": "['COVID19']",
    "source": "Twitter for iPhone",
    "is_retweet": "False",
}


class XSilverTests(unittest.TestCase):
    def test_parse_bronze_key(self):
        key = "bronze/x/covid-tweets/raw/covid_19_tweets.csv"
        self.assertEqual(app.parse_bronze_key(key), "covid-tweets")

    def test_csv_row_to_post_row(self):
        row = dict(SAMPLE_ROW)
        post = app.csv_row_to_post_row(row, "covid-tweets")
        self.assertEqual(post["post_type"], "tweet")
        self.assertEqual(post["source_dataset"], "covid-tweets")
        self.assertEqual(post["year"], "2020")
        self.assertTrue(post["post_id"])

    def test_csv_row_to_user_row(self):
        user = app.csv_row_to_user_row(SAMPLE_ROW)
        self.assertEqual(user["username"], "alice")
        self.assertEqual(user["follower_count"], 624)
        self.assertFalse(user["is_verified"])

    def test_retweet_post_type(self):
        row = dict(SAMPLE_ROW)
        row["is_retweet"] = "True"
        post = app.csv_row_to_post_row(row, "bitcoin-tweets")
        self.assertEqual(post["post_type"], "retweet")

    def test_row_hash_is_stable_for_post_id(self):
        row = dict(SAMPLE_ROW)
        first = app.csv_row_to_post_row(row, "covid-tweets")["post_id"]
        second = app.csv_row_to_post_row(row, "covid-tweets")["post_id"]
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
