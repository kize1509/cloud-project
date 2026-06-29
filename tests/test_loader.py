import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd


APP_PATH = Path(__file__).resolve().parents[1] / "lambdas" / "ec2" / "loader" / "app.py"
COMMON_DIR = Path(__file__).resolve().parents[1] / "lambdas" / "ec2" / "loader" / "common"
sys.path.insert(0, str(COMMON_DIR))

SPEC = importlib.util.spec_from_file_location("loader_app", APP_PATH)
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)

import gold_tables  # noqa: E402


class GoldTablesSqlTests(unittest.TestCase):
    def setUp(self):
        self.table = gold_tables.GoldTable(
            "daily_users_metric",
            ["date", "platform", "total_users", "new_users"],
            {"date": "DATE", "platform": "TEXT", "total_users": "INTEGER", "new_users": "INTEGER"},
        )

    def test_create_table_sql_quotes_identifiers(self):
        sql = gold_tables.create_table_sql(self.table)
        self.assertIn('CREATE TABLE IF NOT EXISTS "daily_users_metric"', sql)
        self.assertIn('"date" DATE', sql)
        self.assertIn('"new_users" INTEGER', sql)

    def test_delete_for_date_sql_filters_on_date(self):
        self.assertEqual(
            gold_tables.delete_for_date_sql(self.table),
            'DELETE FROM "daily_users_metric" WHERE "date" = %s',
        )

    def test_insert_sql_lists_columns_in_order(self):
        self.assertEqual(
            gold_tables.insert_sql(self.table),
            'INSERT INTO "daily_users_metric" ("date", "platform", "total_users", "new_users") VALUES %s',
        )

    def test_reserved_word_columns_are_quoted(self):
        counts = next(t for t in gold_tables.GOLD_TABLES if t.name == "daily_hn_post_counts")
        self.assertIn('"count" INTEGER', gold_tables.create_table_sql(counts))

    def test_dataframe_to_rows_orders_columns_and_nulls_nan(self):
        frame = pd.DataFrame(
            [
                {"new_users": 5, "platform": "X", "date": "2026-05-28", "total_users": None},
            ]
        )
        rows = gold_tables.dataframe_to_rows(self.table, frame)
        # Column order is [date, platform, total_users, new_users]; total_users was null.
        self.assertEqual(rows, [("2026-05-28", "X", None, 5)])

    def test_dataframe_to_rows_empty_returns_empty_list(self):
        self.assertEqual(gold_tables.dataframe_to_rows(self.table, pd.DataFrame()), [])


class LoaderHandlerTests(unittest.TestCase):
    @patch.dict(os.environ, {"DATA_LAKE_BUCKET": "test-bucket"})
    @patch("notify.notify_failure")
    @patch("db.load_table")
    @patch("db.connect")
    @patch("gold_read.read_gold_table_for_date")
    def test_handler_loads_all_tables_for_date(self, read_mock, connect_mock, load_mock, notify_mock):
        read_mock.return_value = pd.DataFrame([{"date": "2026-05-28"}])
        connection = MagicMock()
        connect_mock.return_value = connection
        load_mock.return_value = 3

        result = app.lambda_handler({"date": "2026-05-28"}, None)

        self.assertEqual(result["date"], "2026-05-28")
        self.assertEqual(len(result["results"]), len(gold_tables.GOLD_TABLES))
        self.assertEqual(read_mock.call_count, len(gold_tables.GOLD_TABLES))
        self.assertEqual(load_mock.call_count, len(gold_tables.GOLD_TABLES))
        connection.commit.assert_called_once()
        connection.close.assert_called_once()
        notify_mock.assert_not_called()

    @patch.dict(os.environ, {"DATA_LAKE_BUCKET": "test-bucket"})
    @patch("notify.notify_failure")
    @patch("db.load_table")
    @patch("db.connect")
    @patch("gold_read.read_gold_table_for_date")
    def test_handler_defaults_to_yesterday(self, read_mock, connect_mock, load_mock, notify_mock):
        read_mock.return_value = pd.DataFrame()
        connect_mock.return_value = MagicMock()
        load_mock.return_value = 0

        with patch.object(app, "_default_target_date", return_value="2026-01-01"):
            result = app.lambda_handler({}, None)

        self.assertEqual(result["date"], "2026-01-01")

    @patch.dict(os.environ, {"DATA_LAKE_BUCKET": "test-bucket"})
    @patch("notify.notify_failure")
    @patch("db.connect")
    def test_handler_notifies_and_reraises_on_failure(self, connect_mock, notify_mock):
        connect_mock.side_effect = RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            app.lambda_handler({"date": "2026-05-28"}, None)

        notify_mock.assert_called_once()
        args = notify_mock.call_args[0]
        self.assertEqual(args[0], "visualization")
        self.assertEqual(args[1], "gold-to-postgres")

    @patch.dict(os.environ, {"DATA_LAKE_BUCKET": "test-bucket"})
    @patch("notify.notify_failure")
    @patch("db.load_table")
    @patch("db.connect")
    @patch("gold_read.read_gold_table_for_date")
    def test_handler_rolls_back_when_a_table_fails(self, read_mock, connect_mock, load_mock, notify_mock):
        read_mock.return_value = pd.DataFrame([{"date": "2026-05-28"}])
        connection = MagicMock()
        connect_mock.return_value = connection
        load_mock.side_effect = RuntimeError("insert failed")

        with self.assertRaises(RuntimeError):
            app.lambda_handler({"date": "2026-05-28"}, None)

        connection.rollback.assert_called_once()
        connection.close.assert_called_once()
        connection.commit.assert_not_called()


class LoadTableTests(unittest.TestCase):
    @patch.dict(
        os.environ,
        {"EC2_HOST": "10.0.0.1", "DB_USER": "u", "DB_PASSWORD": "p", "DB_NAME": "metrics"},
    )
    def test_load_table_creates_deletes_then_inserts(self):
        import db

        table = next(t for t in gold_tables.GOLD_TABLES if t.name == "daily_hn_post_counts")
        frame = pd.DataFrame([{"date": "2026-05-28", "post_type": "story", "count": 7}])

        cursor = MagicMock()
        cursor.__enter__ = MagicMock(return_value=cursor)
        cursor.__exit__ = MagicMock(return_value=False)
        connection = MagicMock()
        connection.cursor.return_value = cursor

        fake_execute_values = MagicMock()
        fake_extras = type(sys)("psycopg2.extras")
        fake_extras.execute_values = fake_execute_values
        fake_psycopg2 = type(sys)("psycopg2")
        fake_psycopg2.extras = fake_extras

        with patch.dict(sys.modules, {"psycopg2": fake_psycopg2, "psycopg2.extras": fake_extras}):
            inserted = db.load_table(connection, table, "2026-05-28", frame)

        self.assertEqual(inserted, 1)
        # First execute = CREATE TABLE, second = DELETE for the date.
        create_sql = cursor.execute.call_args_list[0][0][0]
        delete_call = cursor.execute.call_args_list[1]
        self.assertIn("CREATE TABLE IF NOT EXISTS", create_sql)
        self.assertEqual(delete_call[0][1], ("2026-05-28",))
        fake_execute_values.assert_called_once()


if __name__ == "__main__":
    unittest.main()
