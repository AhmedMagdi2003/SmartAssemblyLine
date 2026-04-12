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


if __name__ == "__main__":
    unittest.main()
