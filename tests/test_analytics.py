import datetime
import unittest

from src.utils.analytics import ProductionAnalytics


class SequenceClock:
    def __init__(self, *moments):
        self._moments = iter(moments)

    def __call__(self):
        return next(self._moments)


class ProductionAnalyticsTests(unittest.TestCase):
    def test_payload_counts_reset_when_shift_changes(self):
        shifts = [
            {"name": "Morning_Shift", "start_hour": 6, "end_hour": 14},
            {"name": "Evening_Shift", "start_hour": 14, "end_hour": 22},
            {"name": "Night_Shift", "start_hour": 22, "end_hour": 6},
        ]
        clock = SequenceClock(
            datetime.datetime(2026, 4, 4, 7, 0, 0),
            datetime.datetime(2026, 4, 4, 7, 5, 0),
            datetime.datetime(2026, 4, 4, 14, 0, 0),
        )
        analytics = ProductionAnalytics(shifts, clock=clock)

        first = analytics.generate_dashboard_payload(7, 1.25, 12.5)
        second = analytics.generate_dashboard_payload(8, 1.50, -3.0)
        third = analytics.generate_dashboard_payload(9, 2.00, 5.0)

        self.assertEqual(first["shift"], "Morning_Shift")
        self.assertEqual(first["shift_count"], 1)
        self.assertEqual(first["uuid"], "BOX-20260404-Morning_Shift-0001")

        self.assertEqual(second["shift_count"], 2)
        self.assertEqual(second["uuid"], "BOX-20260404-Morning_Shift-0002")

        self.assertEqual(third["shift"], "Evening_Shift")
        self.assertEqual(third["shift_count"], 1)
        self.assertEqual(third["uuid"], "BOX-20260404-Evening_Shift-0001")

    def test_payload_resumes_shift_count_from_persisted_storage(self):
        shifts = [
            {"name": "Morning_Shift", "start_hour": 6, "end_hour": 14},
        ]
        analytics = ProductionAnalytics(
            shifts,
            clock=lambda: datetime.datetime(2026, 4, 4, 7, 15, 0),
            shift_count_loader=lambda shift_name, shift_date: 50,
        )

        payload = analytics.generate_dashboard_payload(51, 1.2, 6.0)

        self.assertEqual(payload["shift_count"], 51)
        self.assertEqual(payload["uuid"], "BOX-20260404-Morning_Shift-0051")
        self.assertEqual(payload["shift_date"], "2026-04-04")

    def test_night_shift_keeps_same_shift_date_after_midnight(self):
        shifts = [
            {"name": "Night_Shift", "start_hour": 22, "end_hour": 6},
        ]
        clock = SequenceClock(
            datetime.datetime(2026, 4, 4, 23, 55, 0),
            datetime.datetime(2026, 4, 5, 0, 5, 0),
        )
        analytics = ProductionAnalytics(shifts, clock=clock)

        first = analytics.generate_dashboard_payload(7, 1.25, 12.5)
        second = analytics.generate_dashboard_payload(8, 1.50, -3.0)

        self.assertEqual(first["shift_date"], "2026-04-04")
        self.assertEqual(second["shift_date"], "2026-04-04")
        self.assertEqual(second["shift_count"], 2)
        self.assertEqual(second["uuid"], "BOX-20260404-Night_Shift-0002")


if __name__ == "__main__":
    unittest.main()
