import csv
from pathlib import Path
import unittest
import uuid

from src.utils.logger import FIELDNAMES, get_log_path, handle_csv_logging, persist_payload

TEMP_ROOT = Path(__file__).resolve().parents[1] / "data" / "test_tmp"
TEMP_ROOT.mkdir(parents=True, exist_ok=True)


class CsvLoggerTests(unittest.TestCase):
    def test_csv_logging_uses_repo_safe_daily_shift_path(self):
        payload = {
            "uuid": "BOX-20260404-Morning_Shift-0001",
            "yolo_session_id": 14,
            "timestamp_iso": "2026-04-04T08:15:00",
            "shift": "Morning_Shift",
            "shift_date": "2026-04-04",
            "shift_count": 1,
            "transit_time_sec": 1.75,
            "orientation_deg": 7.5,
            "status": "COMPLETED",
        }

        log_dir = TEMP_ROOT / f"logger_case_{uuid.uuid4().hex}"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = get_log_path(payload, log_dir=log_dir)

        self.assertEqual(log_path, log_dir / "shift_Morning_Shift_2026-04-04.csv")

        handle_csv_logging(payload, log_dir=log_dir)
        handle_csv_logging(
            {**payload, "uuid": "BOX-20260404-Morning_Shift-0002", "shift_count": 2},
            log_dir=log_dir,
        )

        with log_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["uuid"], "BOX-20260404-Morning_Shift-0001")
            self.assertEqual(rows[1]["shift_count"], "2")
            self.assertEqual(rows[1]["orientation_deg"], "7.5")

        with log_path.open(encoding="utf-8") as handle:
            header = handle.readline().strip().split(",")
            self.assertEqual(header, FIELDNAMES)

    def test_persist_payload_writes_csv_after_successful_db_insert(self):
        calls = []

        def fake_db_save(payload):
            calls.append(("db", payload["uuid"]))
            return True

        def fake_csv_save(payload):
            calls.append(("csv", payload["uuid"]))

        result = persist_payload(
            {
                "uuid": "BOX-1",
                "yolo_session_id": 1,
                "timestamp_iso": "2026-04-13T00:10:00",
                "shift": "Morning_Shift",
                "shift_date": "2026-04-13",
                "shift_count": 1,
                "transit_time_sec": 1.1,
                "orientation_deg": 5.0,
                "status": "COMPLETED",
            },
            save_to_db=fake_db_save,
            csv_handler=fake_csv_save,
        )

        self.assertEqual(result, "inserted")
        self.assertEqual(calls, [("db", "BOX-1"), ("csv", "BOX-1")])

    def test_persist_payload_skips_csv_for_duplicate_db_event(self):
        calls = []

        def fake_db_save(payload):
            calls.append(("db", payload["uuid"]))
            return False

        def fake_csv_save(payload):
            calls.append(("csv", payload["uuid"]))

        result = persist_payload(
            {
                "uuid": "BOX-1",
                "yolo_session_id": 1,
                "timestamp_iso": "2026-04-13T00:10:00",
                "shift": "Morning_Shift",
                "shift_date": "2026-04-13",
                "shift_count": 1,
                "transit_time_sec": 1.1,
                "orientation_deg": 5.0,
                "status": "COMPLETED",
            },
            save_to_db=fake_db_save,
            csv_handler=fake_csv_save,
        )

        self.assertEqual(result, "duplicate")
        self.assertEqual(calls, [("db", "BOX-1")])

    def test_csv_logging_uses_shift_date_for_night_shift_resume(self):
        payload = {
            "uuid": "BOX-20260404-Night_Shift-0051",
            "yolo_session_id": 51,
            "timestamp_iso": "2026-04-05T00:10:00",
            "shift": "Night_Shift",
            "shift_date": "2026-04-04",
            "shift_count": 51,
            "transit_time_sec": 1.1,
            "orientation_deg": 5.0,
            "status": "COMPLETED",
        }

        log_path = get_log_path(payload, log_dir=TEMP_ROOT)
        self.assertEqual(log_path, TEMP_ROOT / "shift_Night_Shift_2026-04-04.csv")


if __name__ == "__main__":
    unittest.main()
