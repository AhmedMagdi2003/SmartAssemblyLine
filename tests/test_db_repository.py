import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.base import Base
from src.db.repositories import normalize_box_event_payload, save_box_event


class DatabaseRepositoryTests(unittest.TestCase):
    def test_payload_normalization_converts_types(self):
        payload = normalize_box_event_payload(
            {
                "uuid": "BOX-1",
                "yolo_session_id": "7",
                "timestamp_iso": "2026-04-13T00:10:00",
                "shift": "Morning_Shift",
                "shift_count": "3",
                "transit_time_sec": "1.25",
                "orientation_deg": "12.5",
                "status": "COMPLETED",
            }
        )
        self.assertEqual(payload["yolo_session_id"], 7)
        self.assertEqual(payload["shift_count"], 3)
        self.assertEqual(payload["transit_time_sec"], 1.25)
        self.assertEqual(payload["orientation_deg"], 12.5)

    def test_save_box_event_ignores_duplicate_uuid(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "data" / "test_tmp") as temp_dir:
            db_path = Path(temp_dir) / "events.db"
            engine = create_engine(f"sqlite:///{db_path}", future=True)
            SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
            Base.metadata.create_all(bind=engine)

            payload = {
                "uuid": "BOX-20260413-Morning_Shift-0001",
                "yolo_session_id": 7,
                "timestamp_iso": "2026-04-13T00:10:00",
                "shift": "Morning_Shift",
                "shift_count": 1,
                "transit_time_sec": 1.5,
                "orientation_deg": 12.5,
                "status": "COMPLETED",
            }

            self.assertTrue(save_box_event(payload, session_factory=SessionLocal))
            self.assertFalse(save_box_event(payload, session_factory=SessionLocal))


if __name__ == "__main__":
    unittest.main()
