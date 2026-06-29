import os
import sys

COMMON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "common")
if os.path.isdir(COMMON_DIR) and COMMON_DIR not in sys.path:
    sys.path.insert(0, COMMON_DIR)

from gold_tables import GOLD_TABLES  # noqa: E402


def _default_target_date():
    from datetime import datetime, timedelta, timezone

    return (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")


def lambda_handler(event, context):
    from db import connect, load_table  # noqa: E402
    from gold_read import read_gold_table_for_date  # noqa: E402
    from notify import notify_failure  # noqa: E402

    current_table = None
    target_date = None
    try:
        bucket = os.environ["DATA_LAKE_BUCKET"]
        target_date = (event or {}).get("date") or _default_target_date()

        connection = connect()
        try:
            results = []
            for table in GOLD_TABLES:
                current_table = table.name
                dataframe = read_gold_table_for_date(bucket, table.name, target_date)
                row_count = load_table(connection, table, target_date, dataframe)
                results.append({"table": table.name, "rows": row_count})
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        return {"date": target_date, "results": results}
    except Exception as exc:
        try:
            notify_failure(
                "visualization",
                "gold-to-postgres",
                exc,
                {"table": current_table, "date": target_date},
            )
        except Exception as notify_exc:
            print(f"failed to send Discord notification: {notify_exc}")
        raise
