import datetime
import importlib.util
import tempfile
import unittest
from pathlib import Path

SQLALCHEMY_AVAILABLE = importlib.util.find_spec("sqlalchemy") is not None

if SQLALCHEMY_AVAILABLE:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from src.db.base import Base
    from src.db.models import BoxEvent
    from src.db.repositories import (
        get_current_kpis,
        get_shift_event_count,
        normalize_box_event_payload,
        save_box_event,
    )


@unittest.skipUnless(SQLALCHEMY_AVAILABLE, "sqlalchemy is not installed in this environment")
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

            try:
                self.assertTrue(save_box_event(payload, session_factory=SessionLocal))
                self.assertFalse(save_box_event(payload, session_factory=SessionLocal))
            finally:
                engine.dispose()

    def test_get_shift_event_count_uses_uuid_shift_date_prefix(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "data" / "test_tmp") as temp_dir:
            db_path = Path(temp_dir) / "events.db"
            engine = create_engine(f"sqlite:///{db_path}", future=True)
            SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
            Base.metadata.create_all(bind=engine)

            session = SessionLocal()
            session.add_all(
                [
                    BoxEvent(
                        uuid="BOX-20260404-Night_Shift-0049",
                        yolo_session_id=49,
                        timestamp_iso="2026-04-04T23:55:00",
                        shift="Night_Shift",
                        shift_count=49,
                        transit_time_sec=1.2,
                        orientation_deg=4.0,
                        status="COMPLETED",
                    ),
                    BoxEvent(
                        uuid="BOX-20260404-Night_Shift-0050",
                        yolo_session_id=50,
                        timestamp_iso="2026-04-05T00:05:00",
                        shift="Night_Shift",
                        shift_count=50,
                        transit_time_sec=1.3,
                        orientation_deg=5.0,
                        status="COMPLETED",
                    ),
                ]
            )
            session.commit()
            session.close()

            try:
                count = get_shift_event_count(
                    "Night_Shift",
                    datetime.date(2026, 4, 4),
                    session_factory=SessionLocal,
                )
                self.assertEqual(count, 50)
            finally:
                engine.dispose()

    def test_get_current_kpis_uses_latest_shift_window_only(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "data" / "test_tmp") as temp_dir:
            db_path = Path(temp_dir) / "events.db"
            engine = create_engine(f"sqlite:///{db_path}", future=True)
            SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
            Base.metadata.create_all(bind=engine)

            session = SessionLocal()
            session.add_all(
                [
                    BoxEvent(
                        uuid="BOX-20260403-Morning_Shift-0100",
                        yolo_session_id=100,
                        timestamp_iso="2026-04-03T08:00:00",
                        shift="Morning_Shift",
                        shift_count=100,
                        transit_time_sec=2.0,
                        orientation_deg=2.0,
                        status="COMPLETED",
                    ),
                    BoxEvent(
                        uuid="BOX-20260404-Morning_Shift-0001",
                        yolo_session_id=1,
                        timestamp_iso="2026-04-04T08:00:00",
                        shift="Morning_Shift",
                        shift_count=1,
                        transit_time_sec=1.0,
                        orientation_deg=3.0,
                        status="COMPLETED",
                    ),
                    BoxEvent(
                        uuid="BOX-20260404-Morning_Shift-0002",
                        yolo_session_id=2,
                        timestamp_iso="2026-04-04T08:01:00",
                        shift="Morning_Shift",
                        shift_count=2,
                        transit_time_sec=1.5,
                        orientation_deg=4.0,
                        status="COMPLETED",
                    ),
                ]
            )
            session.commit()
            session.close()

            try:
                kpis = get_current_kpis(session_factory=SessionLocal)
                self.assertEqual(kpis["current_shift"], "Morning_Shift")
                self.assertEqual(kpis["shift_date"], "2026-04-04")
                self.assertEqual(kpis["shift_volume"], 2)
                self.assertEqual(kpis["average_transit_time_sec"], 1.25)
            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
