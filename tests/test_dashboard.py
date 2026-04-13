import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


FASTAPI_AVAILABLE = importlib.util.find_spec("fastapi") is not None


class DashboardTemplateTests(unittest.TestCase):
    def test_dashboard_template_contains_live_widgets(self):
        template_path = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "index.html"
        html = template_path.read_text(encoding="utf-8")

        for fragment in (
            "plot-orientation",
            "plot-transit",
            "plot-volume",
            "Export Session CSV",
            "/ws",
            "/api/events?limit=50",
            "/api/kpis/current",
            "/api/charts/overview?limit=50",
        ):
            self.assertIn(fragment, html)


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi is not installed in this environment")
class DashboardConnectionManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_broadcast_removes_stale_connections(self):
        from src.dashboard.main import ConnectionManager

        sent_messages = []

        class HealthySocket:
            async def send_text(self, message):
                sent_messages.append(message)

        class BrokenSocket:
            async def send_text(self, message):
                raise RuntimeError("closed")

        manager = ConnectionManager()
        healthy = HealthySocket()
        broken = BrokenSocket()
        manager.active_connections = [healthy, broken]

        await manager.broadcast('{"status":"ok"}')

        self.assertEqual(sent_messages, ['{"status":"ok"}'])
        self.assertEqual(manager.active_connections, [healthy])


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi is not installed in this environment")
class DashboardApiTests(unittest.TestCase):
    def test_dashboard_api_returns_database_payloads(self):
        from fastapi.testclient import TestClient
        from src.dashboard import main

        with patch.object(
            main,
            "list_recent_box_events",
            return_value=[
                {"uuid": "BOX-2", "timestamp_iso": "2026-04-13T01:00:00", "shift_count": 2},
                {"uuid": "BOX-1", "timestamp_iso": "2026-04-13T00:00:00", "shift_count": 1},
            ],
        ), patch.object(
            main,
            "get_latest_box_event",
            return_value={"uuid": "BOX-2"},
        ), patch.object(
            main,
            "get_current_kpis",
            return_value={
                "current_shift": "Morning_Shift",
                "shift_volume": 2,
                "average_transit_time_sec": 1.25,
                "last_angle_deg": 6.5,
                "last_event_uuid": "BOX-2",
            },
        ), patch.object(
            main,
            "get_shift_summary",
            return_value=[{"shift": "Morning_Shift", "volume": 2, "average_transit_time_sec": 1.25}],
        ), patch.object(
            main,
            "get_chart_overview",
            return_value={
                "orientation": [{"timestamp_iso": "2026-04-13T01:00:00", "orientation_deg": 6.5, "color": "#10b981"}],
                "transit": [1.25],
                "volume": [{"timestamp_iso": "2026-04-13T01:00:00", "shift_count": 2}],
            },
        ):
            client = TestClient(main.app)

            events_response = client.get("/api/events?limit=10")
            self.assertEqual(events_response.status_code, 200)
            self.assertEqual(events_response.json()["events"][0]["uuid"], "BOX-1")

            latest_response = client.get("/api/events/latest")
            self.assertEqual(latest_response.status_code, 200)
            self.assertEqual(latest_response.json()["event"]["uuid"], "BOX-2")

            kpis_response = client.get("/api/kpis/current")
            self.assertEqual(kpis_response.status_code, 200)
            self.assertEqual(kpis_response.json()["kpis"]["shift_volume"], 2)

            shifts_response = client.get("/api/stats/shifts")
            self.assertEqual(shifts_response.status_code, 200)
            self.assertEqual(shifts_response.json()["shifts"][0]["shift"], "Morning_Shift")

            charts_response = client.get("/api/charts/overview?limit=10")
            self.assertEqual(charts_response.status_code, 200)
            self.assertEqual(charts_response.json()["volume"][0]["shift_count"], 2)


if __name__ == "__main__":
    unittest.main()
