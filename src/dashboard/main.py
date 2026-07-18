from contextlib import suppress
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import asyncio
import os
import subprocess
import sys
import time
from typing import List, Optional

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

try:
    import serial
except ImportError:
    serial = None

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

from src.comms.mqtt_config import (
    configure_mqtt_client,
    load_mqtt_control_settings,
    load_mqtt_settings,
)

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if load_dotenv is not None:
    load_dotenv(PROJECT_ROOT / ".env")

RUNTIME_DIR = PROJECT_ROOT / "data" / "runtime"
LOG_DIR = RUNTIME_DIR / "logs"
PID_DIR = RUNTIME_DIR / "pids"
PIPELINE_LOG = LOG_DIR / "pipeline.log"
PIPELINE_ERR_LOG = LOG_DIR / "pipeline.err.log"
PIPELINE_PID_FILE = PID_DIR / "pipeline.pid"

app = FastAPI(title="Smart Assembly Line Dashboard")
MQTT_SETTINGS = load_mqtt_settings()
MQTT_CONTROL_SETTINGS = load_mqtt_control_settings()
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


def _database_error_response(default_payload, exc):
    print(f"[WARNING] Dashboard database query failed: {exc}")
    return {**default_payload, "source": "database_error", "error": str(exc)}


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


def _env_flag(name, default=False):
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _get_pipeline_process():
    process = getattr(app.state, "pipeline_process", None)
    if process is not None and process.poll() is None:
        return process
    return None


def _clear_pipeline_pid():
    with suppress(FileNotFoundError):
        PIPELINE_PID_FILE.unlink()


def _pipeline_status():
    process = _get_pipeline_process()
    running = process is not None
    return {
        "running": running,
        "pid": process.pid if process is not None else None,
        "logs": {
            "stdout": str(PIPELINE_LOG),
            "stderr": str(PIPELINE_ERR_LOG),
        },
        "serial": {
            "configured": bool(
                os.getenv("MECHANICAL_SERIAL_PORT")
                or os.getenv("RASPBERRY_PI_SERIAL_PORT")
            ),
            "available": serial is not None,
            "port": os.getenv("MECHANICAL_SERIAL_PORT")
            or os.getenv("RASPBERRY_PI_SERIAL_PORT")
            or None,
        },
        "mqtt_control": {
            "configured": bool(MQTT_CONTROL_SETTINGS["topic"]),
            "available": mqtt is not None,
            "host": MQTT_CONTROL_SETTINGS["host"],
            "port": MQTT_CONTROL_SETTINGS["port"],
            "topic": MQTT_CONTROL_SETTINGS["topic"],
        },
    }


def _send_serial_command(command):
    """
    Send a simple control string to the Raspberry Pi over serial.
    Configure MECHANICAL_SERIAL_PORT, for example COM3 on Windows or /dev/ttyUSB0 on Linux.
    """
    port = os.getenv("MECHANICAL_SERIAL_PORT") or os.getenv("RASPBERRY_PI_SERIAL_PORT")
    if not port:
        return {"status": "skipped", "reason": "serial_port_not_configured"}

    if serial is None:
        return {"status": "skipped", "reason": "pyserial_not_installed"}

    baudrate = int(os.getenv("MECHANICAL_SERIAL_BAUDRATE", "115200"))
    timeout = float(os.getenv("MECHANICAL_SERIAL_TIMEOUT_SEC", "2"))
    encoded = f"{command}\n".encode("utf-8")

    try:
        with serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=timeout,
            write_timeout=timeout,
        ) as connection:
            connection.write(encoded)
            connection.flush()
        return {"status": "sent", "command": command, "port": port}
    except Exception as exc:
        return {"status": "error", "command": command, "port": port, "error": str(exc)}


def _send_mqtt_control_command(command):
    """Publish a simple on/off control string to the Raspberry Pi over MQTT."""
    topic = str(MQTT_CONTROL_SETTINGS.get("topic") or "").strip()
    if not topic:
        return {"status": "skipped", "reason": "mqtt_control_topic_not_configured"}

    if mqtt is None:
        return {"status": "skipped", "reason": "paho_mqtt_not_installed"}

    client = mqtt.Client()

    try:
        configure_mqtt_client(client, MQTT_CONTROL_SETTINGS)
        client.connect(
            MQTT_CONTROL_SETTINGS["host"],
            MQTT_CONTROL_SETTINGS["port"],
            MQTT_CONTROL_SETTINGS["keepalive"],
        )
        client.loop_start()
        publish_result = client.publish(topic, payload=command)
        with suppress(Exception):
            publish_result.wait_for_publish()
        return {
            "status": "sent",
            "command": command,
            "host": MQTT_CONTROL_SETTINGS["host"],
            "port": MQTT_CONTROL_SETTINGS["port"],
            "topic": topic,
        }
    except Exception as exc:
        return {
            "status": "error",
            "command": command,
            "host": MQTT_CONTROL_SETTINGS["host"],
            "port": MQTT_CONTROL_SETTINGS["port"],
            "topic": topic,
            "error": str(exc),
        }
    finally:
        with suppress(Exception):
            client.loop_stop()
        with suppress(Exception):
            client.disconnect()


def _send_project_control_command(command):
    mqtt_result = _send_mqtt_control_command(command)
    serial_result = _send_serial_command(f"turn {command}")

    if mqtt_result["status"] == "sent" or serial_result["status"] == "sent":
        status = "sent"
    elif mqtt_result["status"] == "error" and serial_result["status"] == "error":
        status = "error"
    else:
        status = "skipped"

    return {
        "status": status,
        "command": command,
        "mqtt": mqtt_result,
        "serial": serial_result,
    }


def _start_pipeline_process():
    existing = _get_pipeline_process()
    if existing is not None:
        return {"status": "already_running", **_pipeline_status()}

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PID_DIR.mkdir(parents=True, exist_ok=True)

    stdout_log = PIPELINE_LOG.open("a", encoding="utf-8")
    stderr_log = PIPELINE_ERR_LOG.open("a", encoding="utf-8")
    stdout_log.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting pipeline\n")
    stdout_log.flush()

    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    process = subprocess.Popen(
        [sys.executable, "-u", "scripts/run_pipeline.py"],
        cwd=PROJECT_ROOT,
        stdout=stdout_log,
        stderr=stderr_log,
        creationflags=creationflags,
    )
    stdout_log.close()
    stderr_log.close()

    app.state.pipeline_process = process
    PIPELINE_PID_FILE.write_text(str(process.pid), encoding="utf-8")
    return {"status": "started", **_pipeline_status()}


def _stop_pipeline_process():
    process = _get_pipeline_process()
    if process is None:
        _clear_pipeline_pid()
        return {"status": "not_running", **_pipeline_status()}

    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)

    _clear_pipeline_pid()
    return {"status": "stopped", **_pipeline_status()}

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
    try:
        events = list_recent_box_events(
            limit=_parse_limit(limit),
            shift=resolved_shift,
            shift_date=resolved_shift_date,
        )
    except Exception as exc:
        return _database_error_response({"events": []}, exc)
    events.reverse()
    return {"events": events, "source": "database"}


@app.get("/api/events/latest")
async def get_latest_event():
    if get_latest_box_event is None:
        return {"event": None, "source": "unavailable"}

    try:
        return {"event": get_latest_box_event(), "source": "database"}
    except Exception as exc:
        return _database_error_response({"event": None}, exc)


@app.get("/api/kpis/current")
async def get_current_dashboard_kpis():
    if get_current_kpis is None:
        return {"kpis": None, "source": "unavailable"}

    try:
        return {"kpis": get_current_kpis(), "source": "database"}
    except Exception as exc:
        return _database_error_response({"kpis": None}, exc)


@app.get("/api/stats/shifts")
async def get_shift_stats(limit: int = 10):
    if get_shift_summary is None:
        return {"shifts": [], "source": "unavailable"}

    try:
        return {"shifts": get_shift_summary(limit=max(1, min(limit, 100))), "source": "database"}
    except Exception as exc:
        return _database_error_response({"shifts": []}, exc)


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
    try:
        return {
            **get_chart_overview(
                limit=_parse_limit(limit),
                shift=resolved_shift,
                shift_date=resolved_shift_date,
            ),
            "source": "database",
        }
    except Exception as exc:
        return _database_error_response(
            {
                "orientation": [],
                "transit": [],
                "volume": [],
            },
            exc,
        )


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


@app.get("/api/project/status")
async def get_project_status():
    return _pipeline_status()


@app.post("/api/project/start")
async def start_project():
    pipeline = _start_pipeline_process()
    mechanical = _send_project_control_command("on")
    return {"pipeline": pipeline, "mechanical": mechanical}


@app.post("/api/project/stop")
async def stop_project():
    pipeline = _stop_pipeline_process()
    mechanical = _send_project_control_command("off")
    return {"pipeline": pipeline, "mechanical": mechanical}


# 3. Server Lifecycle (Starts/Stops MQTT safely)
@app.on_event("startup")
async def startup_event():
    global mqtt_loop_ref
    app.state.is_shutting_down = False
    app.state.pipeline_process = None
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

    with suppress(Exception):
        _stop_pipeline_process()

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
