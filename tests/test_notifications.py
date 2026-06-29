import importlib.util
import json
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hn_bronze = load_module("hn_bronze_notify_app", ROOT / "lambdas" / "bronze" / "hackernews_ingest" / "app.py")
x_bronze = load_module("x_bronze_notify_app", ROOT / "lambdas" / "bronze" / "x_ingest" / "app.py")
silver_notify = load_module("silver_notify_module", ROOT / "lambdas" / "silver" / "common" / "notify.py")
gold_notify = load_module("gold_notify_module", ROOT / "lambdas" / "gold" / "common" / "notify.py")


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return b"ok"


class FakeSsmClient:
    def __init__(self):
        self.calls = []

    def get_parameter(self, **kwargs):
        self.calls.append(kwargs)
        return {"Parameter": {"Value": "https://discord.example/webhook"}}


class NotificationTests(unittest.TestCase):
    def test_format_failure_message_includes_context(self):
        with patch.dict(os.environ, {"PROJECT_NAME": "proj", "ENVIRONMENT": "test"}):
            message = gold_notify.format_failure_message(
                "gold",
                "gold-transform",
                RuntimeError("boom"),
                {"date": "2026-05-29", "empty": ""},
            )

        self.assertIn("[proj][test][gold] gold-transform failed", message)
        self.assertIn("Error: boom", message)
        self.assertIn("Context: date=2026-05-29", message)
        self.assertNotIn("empty=", message)

    def test_notify_failure_is_disabled_without_parameter_name(self):
        with patch.dict(os.environ, {"DISCORD_WEBHOOK_PARAMETER_NAME": ""}, clear=False):
            with patch.object(hn_bronze, "get_ssm_client") as ssm_mock:
                with patch.object(hn_bronze.urllib.request, "urlopen") as urlopen_mock:
                    hn_bronze.notify_failure("bronze", "hackernews-ingest", ValueError("bad input"))

        ssm_mock.assert_not_called()
        urlopen_mock.assert_not_called()

    def test_bronze_notify_fetches_secure_parameter_and_posts_payload(self):
        ssm = FakeSsmClient()
        captured = {}

        def fake_urlopen(request, timeout):
            captured["timeout"] = timeout
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse()

        with patch.dict(
            os.environ,
            {
                "DISCORD_WEBHOOK_PARAMETER_NAME": "/cloud-computing-prj/dev/discord/webhook",
                "PROJECT_NAME": "cloud-computing-prj",
                "ENVIRONMENT": "dev",
            },
        ):
            with patch.object(hn_bronze, "get_ssm_client", return_value=ssm):
                with patch.object(hn_bronze.urllib.request, "urlopen", side_effect=fake_urlopen):
                    hn_bronze.notify_failure(
                        "bronze",
                        "hackernews-ingest",
                        RuntimeError("network failed"),
                        {"target_date": "2026-05-29"},
                    )

        self.assertEqual(
            ssm.calls,
            [{"Name": "/cloud-computing-prj/dev/discord/webhook", "WithDecryption": True}],
        )
        self.assertEqual(captured["timeout"], 5)
        self.assertIn("[cloud-computing-prj][dev][bronze] hackernews-ingest failed", captured["payload"]["content"])
        self.assertIn("target_date=2026-05-29", captured["payload"]["content"])

    def test_silver_notify_uses_boto3_ssm_client(self):
        ssm = FakeSsmClient()
        fake_boto3 = types.SimpleNamespace(client=lambda service: ssm)
        captured = {}

        def fake_urlopen(request, timeout):
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse()

        with patch.dict(sys.modules, {"boto3": fake_boto3}):
            with patch.dict(os.environ, {"DISCORD_WEBHOOK_PARAMETER_NAME": "/webhook"}):
                with patch.object(silver_notify.urllib.request, "urlopen", side_effect=fake_urlopen):
                    silver_notify.notify_failure(
                        "silver",
                        "x-normalize",
                        ValueError("bad csv"),
                        {"source_key": "bronze/x/covid/raw/file.csv"},
                    )

        self.assertEqual(ssm.calls, [{"Name": "/webhook", "WithDecryption": True}])
        self.assertIn("[cloud-computing-prj][dev][silver] x-normalize failed", captured["payload"]["content"])
        self.assertIn("source_key=bronze/x/covid/raw/file.csv", captured["payload"]["content"])

    def test_lambda_preserves_original_error_when_notification_fails(self):
        with patch.dict(os.environ, {"DATA_LAKE_BUCKET": "bucket"}):
            with patch.object(x_bronze, "notify_failure", side_effect=RuntimeError("discord down")):
                with patch.object(x_bronze, "print"):
                    with self.assertRaisesRegex(ValueError, "event did not contain any S3 object"):
                        x_bronze.lambda_handler({}, None)


if __name__ == "__main__":
    unittest.main()
