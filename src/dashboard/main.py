from contextlib import suppress

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import asyncio
import os
from typing import List, Optional

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

try:
    from src.db.repositories import (
        get_chart_overview,
        get_current_kpis,
        get_latest_box_event,
        get_shift_summary,
        list_recent_box_events,
    )
except Exception:
    get_chart_overview = None
    get_current_kpis = None
    get_latest_box_event = None
    get_shift_summary = None
    list_recent_box_events = None

try:
    from sqlalchemy import text

    from src.db.session import engine
except Exception:
    engine = None
    text = None

from src.comms.mqtt_config import configure_mqtt_client, load_mqtt_settings

app = FastAPI(title="Smart Assembly Line Dashboard")
MQTT_SETTINGS = load_mqtt_settings()
MQTT_ENABLED = os.getenv("MQTT_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}

# Allow the frontend to connect from anywhere during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. The Connection Manager (Handles active web browsers)
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[WS] Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"[WS] Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        """Pushes the JSON string to all open browser tabs."""
        stale_connections = []
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                stale_connections.append(connection)

        for connection in stale_connections:
            self.disconnect(connection)

    async def shutdown(self):
        connections = list(self.active_connections)
        self.active_connections.clear()
        for connection in connections:
            with suppress(Exception):
                await connection.close(code=1001, reason="Server shutdown")

manager = ConnectionManager()
mqtt_loop_ref: Optional[asyncio.AbstractEventLoop] = None  # Will hold our main asyncio loop


def _parse_limit(limit_raw, default=50, maximum=5000):
    if limit_raw is None:
        return default

    limit_text = str(limit_raw).strip().lower()
    if not limit_text:
        return default
    if limit_text == "all":
        return None

    limit_value = int(limit_text)
    if maximum is None:
        return max(1, limit_value)
    return max(1, min(limit_value, maximum))


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _resolve_shift_window(current_shift_only=False, shift=None, shift_date=None):
    if shift and shift_date:
        return shift, shift_date

    if current_shift_only and get_current_kpis is not None:
        kpis = get_current_kpis()
        if kpis:
            return kpis.get("current_shift"), kpis.get("shift_date")

    return shift, shift_date


def _drain_broadcast_result(future):
    try:
        future.result()
    except Exception as exc:
        if not getattr(app.state, "is_shutting_down", False):
            print(f"[WARNING] Broadcast task failed: {exc}")

# 2. The MQTT Callback (Runs in a background thread)
def on_message(client, userdata, msg):
    """Triggered by Mosquitto when a box finishes."""
    try:
        payload = msg.payload.decode('utf-8')

        loop = mqtt_loop_ref
        if (
            loop is None
            or loop.is_closed()
            or not loop.is_running()
            or getattr(app.state, "is_shutting_down", False)
        ):
            return

        # We must securely cross from the MQTT thread into the FastAPI async loop.
        future = asyncio.run_coroutine_threadsafe(manager.broadcast(payload), loop)
        future.add_done_callback(_drain_broadcast_result)
    except Exception as e:
        if not getattr(app.state, "is_shutting_down", False):
            print(f"[ERROR] Broadcasting failed: {e}")

@app.get("/")
async def get_dashboard():
    """Serves the frontend HTML page."""
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r") as f:
        return HTMLResponse(f.read())


@app.get("/api/events")
async def get_recent_events(
    limit: str = "50",
    current_shift_only: str = "false",
    shift: Optional[str] = None,
    shift_date: Optional[str] = None,
):
    if list_recent_box_events is None:
        return {"events": [], "source": "unavailable"}

    resolved_shift, resolved_shift_date = _resolve_shift_window(
        current_shift_only=_parse_bool(current_shift_only),
        shift=shift,
        shift_date=shift_date,
    )
    events = list_recent_box_events(
        limit=_parse_limit(limit),
        shift=resolved_shift,
        shift_date=resolved_shift_date,
    )
    events.reverse()
    return {"events": events, "source": "database"}


@app.get("/api/events/latest")
async def get_latest_event():
    if get_latest_box_event is None:
        return {"event": None, "source": "unavailable"}

    return {"event": get_latest_box_event(), "source": "database"}


@app.get("/api/kpis/current")
async def get_current_dashboard_kpis():
    if get_current_kpis is None:
        return {"kpis": None, "source": "unavailable"}

    return {"kpis": get_current_kpis(), "source": "database"}


@app.get("/api/stats/shifts")
async def get_shift_stats(limit: int = 10):
    if get_shift_summary is None:
        return {"shifts": [], "source": "unavailable"}

    return {"shifts": get_shift_summary(limit=max(1, min(limit, 100))), "source": "database"}


@app.get("/api/charts/overview")
async def get_chart_data(
    limit: str = "50",
    current_shift_only: str = "false",
    shift: Optional[str] = None,
    shift_date: Optional[str] = None,
):
    if get_chart_overview is None:
        return {
            "orientation": [],
            "transit": [],
            "volume": [],
            "source": "unavailable",
        }

    resolved_shift, resolved_shift_date = _resolve_shift_window(
        current_shift_only=_parse_bool(current_shift_only),
        shift=shift,
        shift_date=shift_date,
    )
    return {
        **get_chart_overview(
            limit=_parse_limit(limit),
            shift=resolved_shift,
            shift_date=resolved_shift_date,
        ),
        "source": "database",
    }


@app.get("/api/health")
async def get_health():
    database_status = "unavailable"
    status = "degraded"
    details = None

    if engine is not None and text is not None:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            database_status = "connected"
            status = "ok"
        except Exception as exc:
            database_status = "error"
            details = str(exc)

    mqtt_client = getattr(app.state, "mqtt_client", None)
    mqtt_connected = False
    if mqtt_client is not None and hasattr(mqtt_client, "is_connected"):
        with suppress(Exception):
            mqtt_connected = bool(mqtt_client.is_connected())

    response = {
        "status": status,
        "database": database_status,
        "mqtt_enabled": mqtt is not None,
        "mqtt_topic": MQTT_SETTINGS["topic"],
        "mqtt_connected": mqtt_connected,
    }
    if details and database_status == "error":
        response["details"] = details
    return response


# 3. Server Lifecycle (Starts/Stops MQTT safely)
@app.on_event("startup")
async def startup_event():
    global mqtt_loop_ref
    app.state.is_shutting_down = False
    mqtt_loop_ref = asyncio.get_running_loop()  # Capture the async loop

    if mqtt is None:
        print("[WARNING] paho-mqtt is not installed. Dashboard will run without live MQTT data.")
        app.state.mqtt_client = None
        return

    if not MQTT_ENABLED:
        print("[INFO] MQTT is disabled by configuration. Dashboard will use database history only.")
        app.state.mqtt_client = None
        return
    
    # Initialize MQTT
    app.state.mqtt_client = mqtt.Client()
    app.state.mqtt_client.on_message = on_message
    
    try:
        configure_mqtt_client(app.state.mqtt_client, MQTT_SETTINGS)
        app.state.mqtt_client.connect(
            MQTT_SETTINGS["host"],
            MQTT_SETTINGS["port"],
            MQTT_SETTINGS["keepalive"],
        )
        app.state.mqtt_client.subscribe(MQTT_SETTINGS["topic"])
        app.state.mqtt_client.loop_start() # Starts the MQTT background thread
        print(
            "[MQTT] Connected to "
            f"{MQTT_SETTINGS['host']}:{MQTT_SETTINGS['port']} and listening on "
            f"{MQTT_SETTINGS['topic']}..."
        )
    except Exception as e:
        print(f"[WARNING] Could not connect to MQTT Broker: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    global mqtt_loop_ref
    app.state.is_shutting_down = True
    mqtt_loop_ref = None
    await manager.shutdown()

    client = getattr(app.state, "mqtt_client", None)
    if client is not None:
        with suppress(Exception):
            client.loop_stop()
        with suppress(Exception):
            client.disconnect()

# 4. The WebSocket Endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except RuntimeError as exc:
        if not getattr(app.state, "is_shutting_down", False):
            print(f"[WARNING] WebSocket runtime error: {exc}")
    finally:
        manager.disconnect(websocket)
