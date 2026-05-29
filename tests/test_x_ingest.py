import importlib.util
from pathlib import Path
import unittest


APP_PATH = Path(__file__).resolve().parents[1] / "lambdas" / "bronze" / "x_ingest" / "app.py"
SPEC = importlib.util.spec_from_file_location("x_ingest_app", APP_PATH)
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)


class XIngestTests(unittest.TestCase):
    def test_bitcoin_upload_maps_to_raw_bronze_key(self):
        key = app.x_bronze_key("incoming/x/bitcoin-tweets/batch-001/tweets.csv", "bronze")

        self.assertEqual(key, "bronze/x/bitcoin-tweets/raw/batch-001/tweets.csv")

    def test_covid_upload_maps_to_raw_bronze_key(self):
        key = app.x_bronze_key("incoming/x/covid-tweets/covid.csv", "bronze/")

        self.assertEqual(key, "bronze/x/covid-tweets/raw/covid.csv")

    def test_unknown_dataset_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported X dataset category"):
            app.x_bronze_key("incoming/x/other-dataset/file.csv", "bronze")

    def test_eventbridge_s3_event_extracts_bucket_and_decoded_key(self):
        event = {
            "source": "aws.s3",
            "detail-type": "Object Created",
            "detail": {
                "bucket": {"name": "lake"},
                "object": {"key": "incoming/x/bitcoin-tweets/sample%20file.csv"},
            },
        }

        self.assertEqual(
            app.extract_s3_objects(event),
            [("lake", "incoming/x/bitcoin-tweets/sample file.csv")],
        )


if __name__ == "__main__":
    unittest.main()
