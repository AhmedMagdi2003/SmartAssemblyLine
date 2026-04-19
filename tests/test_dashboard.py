import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch


FASTAPI_AVAILABLE = importlib.util.find_spec("fastapi") is not None
SQLALCHEMY_AVAILABLE = importlib.util.find_spec("sqlalchemy") is not None


class DashboardTemplateTests(unittest.TestCase):
    def test_dashboard_template_contains_live_widgets(self):
        template_path = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "index.html"
        html = template_path.read_text(encoding="utf-8")

        for fragment in (
            "plot-a",
            "plot-b",
            "plot-c",
            "Export Session CSV",
            "Current Shift",
            "All History",
            "Period Unit",
            "Full Range",
            "/ws",
            "current_shift_only",
            "/api/kpis/current",
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

    async def test_shutdown_closes_open_connections(self):
        from src.dashboard.main import ConnectionManager

        manager = ConnectionManager()
        socket = AsyncMock()
        manager.active_connections = [socket]

        await manager.shutdown()

        socket.close.assert_awaited_once()
        self.assertEqual(manager.active_connections, [])


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi is not installed in this environment")
class DashboardLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_shutdown_event_clears_loop_and_stops_mqtt_client(self):
        from src.dashboard import main

        previous_loop = main.mqtt_loop_ref
        previous_client = getattr(main.app.state, "mqtt_client", None)
        previous_shutting_down = getattr(main.app.state, "is_shutting_down", False)

        dummy_client = SimpleNamespace(
            loop_stop=lambda: None,
            disconnect=lambda: None,
        )
        main.app.state.mqtt_client = dummy_client
        main.app.state.is_shutting_down = False
        main.mqtt_loop_ref = object()

        with patch.object(main.manager, "shutdown", new=AsyncMock()) as shutdown_mock:
            await main.shutdown_event()

        shutdown_mock.assert_awaited_once()
        self.assertIsNone(main.mqtt_loop_ref)
        self.assertTrue(main.app.state.is_shutting_down)

        main.mqtt_loop_ref = previous_loop
        main.app.state.mqtt_client = previous_client
        main.app.state.is_shutting_down = previous_shutting_down

    async def test_on_message_skips_broadcast_while_shutting_down(self):
        from src.dashboard import main

        previous_loop = main.mqtt_loop_ref
        previous_shutting_down = getattr(main.app.state, "is_shutting_down", False)
        main.app.state.is_shutting_down = True
        main.mqtt_loop_ref = None

        message = SimpleNamespace(payload=b'{"uuid":"BOX-1"}')

        with patch("src.dashboard.main.asyncio.run_coroutine_threadsafe") as run_mock:
            main.on_message(None, None, message)

        run_mock.assert_not_called()

        main.mqtt_loop_ref = previous_loop
        main.app.state.is_shutting_down = previous_shutting_down


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
        ), patch.object(
            main,
            "mqtt",
            None,
        ):
            with TestClient(main.app) as client:
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

                health_response = client.get("/api/health")
                self.assertEqual(health_response.status_code, 200)
                self.assertIn(health_response.json()["database"], {"connected", "error", "unavailable"})

    def test_dashboard_api_can_filter_to_current_shift_window(self):
        from fastapi.testclient import TestClient
        from src.dashboard import main

        with patch.object(
            main,
            "get_current_kpis",
            return_value={
                "current_shift": "Morning_Shift",
                "shift_date": "2026-04-19",
                "shift_volume": 2,
                "average_transit_time_sec": 1.25,
                "last_angle_deg": 6.5,
                "last_event_uuid": "BOX-2",
            },
        ), patch.object(
            main,
            "list_recent_box_events",
            return_value=[{"uuid": "BOX-1", "shift": "Morning_Shift", "shift_date": "2026-04-19", "shift_count": 1}],
        ) as events_mock, patch.object(
            main,
            "get_chart_overview",
            return_value={
                "orientation": [],
                "transit": [],
                "volume": [],
            },
        ) as charts_mock, patch.object(
            main,
            "mqtt",
            None,
        ):
            with TestClient(main.app) as client:
                events_response = client.get("/api/events?limit=all&current_shift_only=true")
                charts_response = client.get("/api/charts/overview?limit=all&current_shift_only=true")

                self.assertEqual(events_response.status_code, 200)
                self.assertEqual(charts_response.status_code, 200)
                events_mock.assert_called_once_with(
                    limit=None,
                    shift="Morning_Shift",
                    shift_date="2026-04-19",
                )
                charts_mock.assert_called_once_with(
                    limit=None,
                    shift="Morning_Shift",
                    shift_date="2026-04-19",
                )


@unittest.skipUnless(FASTAPI_AVAILABLE and SQLALCHEMY_AVAILABLE, "fastapi/sqlalchemy is not installed in this environment")
class DashboardApiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from sqlalchemy import text

        from src.db.session import engine

        cls._text = text
        cls._engine = engine
        cls._uuid_prefix = "TEST-DASHBOARD-INTEGRATION-"
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as exc:
            raise unittest.SkipTest(f"Postgres integration not available: {exc}") from exc

    def tearDown(self):
        with self._engine.begin() as connection:
            connection.execute(
                self._text("DELETE FROM box_events WHERE uuid LIKE :prefix"),
                {"prefix": f"{self._uuid_prefix}%"},
            )

    def setUp(self):
        self.tearDown()

    def test_dashboard_api_reads_real_postgres_history(self):
        from fastapi.testclient import TestClient

        from src.dashboard import main
        from src.db.repositories import save_box_event

        events = [
            {
                "uuid": f"{self._uuid_prefix}001",
                "yolo_session_id": 501,
                "timestamp_iso": "2099-01-01T00:00:00",
                "shift": "Integration_Shift_A",
                "shift_count": 1,
                "transit_time_sec": 1.11,
                "orientation_deg": 8.0,
                "status": "COMPLETED",
            },
            {
                "uuid": f"{self._uuid_prefix}002",
                "yolo_session_id": 502,
                "timestamp_iso": "2099-01-01T00:00:01",
                "shift": "Integration_Shift_A",
                "shift_count": 2,
                "transit_time_sec": 1.55,
                "orientation_deg": 18.5,
                "status": "COMPLETED",
            },
        ]
        for event in events:
            self.assertTrue(save_box_event(event))

        with patch.object(main, "mqtt", None):
            with TestClient(main.app) as client:
                events_response = client.get("/api/events?limit=2")
                self.assertEqual(events_response.status_code, 200)
                self.assertEqual(
                    [event["uuid"] for event in events_response.json()["events"]],
                    [f"{self._uuid_prefix}001", f"{self._uuid_prefix}002"],
                )

                latest_response = client.get("/api/events/latest")
                self.assertEqual(latest_response.status_code, 200)
                self.assertEqual(latest_response.json()["event"]["uuid"], f"{self._uuid_prefix}002")

                kpis_response = client.get("/api/kpis/current")
                self.assertEqual(kpis_response.status_code, 200)
                self.assertEqual(kpis_response.json()["kpis"]["current_shift"], "Integration_Shift_A")
                self.assertEqual(kpis_response.json()["kpis"]["shift_volume"], 2)

                charts_response = client.get("/api/charts/overview?limit=2")
                self.assertEqual(charts_response.status_code, 200)
                self.assertEqual(charts_response.json()["orientation"][1]["orientation_deg"], 18.5)
                self.assertEqual(charts_response.json()["volume"][1]["shift_count"], 2)

                health_response = client.get("/api/health")
                self.assertEqual(health_response.status_code, 200)
                self.assertEqual(health_response.json()["database"], "connected")


if __name__ == "__main__":
    unittest.main()
