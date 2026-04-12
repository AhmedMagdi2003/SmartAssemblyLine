import importlib.util
from pathlib import Path
import unittest


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


if __name__ == "__main__":
    unittest.main()
