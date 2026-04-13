from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import asyncio
import os
from typing import List

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

app = FastAPI(title="Smart Assembly Line Dashboard")

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
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                stale_connections.append(connection)

        for connection in stale_connections:
            self.disconnect(connection)

manager = ConnectionManager()
mqtt_loop_ref = None  # Will hold our main asyncio loop

# 2. The MQTT Callback (Runs in a background thread)
def on_message(client, userdata, msg):
    """Triggered by Mosquitto when a box finishes."""
    try:
        payload = msg.payload.decode('utf-8')
        
        # We must securely cross from the MQTT thread into the FastAPI Async Loop
        if mqtt_loop_ref and mqtt_loop_ref.is_running():
            asyncio.run_coroutine_threadsafe(manager.broadcast(payload), mqtt_loop_ref)
            
    except Exception as e:
        print(f"[ERROR] Broadcasting failed: {e}")

@app.get("/")
async def get_dashboard():
    """Serves the frontend HTML page."""
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r") as f:
        return HTMLResponse(f.read())


@app.get("/api/events")
async def get_recent_events(limit: int = 50):
    if list_recent_box_events is None:
        return {"events": [], "source": "unavailable"}

    events = list_recent_box_events(limit=max(1, min(limit, 500)))
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
async def get_chart_data(limit: int = 50):
    if get_chart_overview is None:
        return {
            "orientation": [],
            "transit": [],
            "volume": [],
            "source": "unavailable",
        }

    return {
        **get_chart_overview(limit=max(1, min(limit, 500))),
        "source": "database",
    }
# 3. Server Lifecycle (Starts/Stops MQTT safely)
@app.on_event("startup")
async def startup_event():
    global mqtt_loop_ref
    mqtt_loop_ref = asyncio.get_running_loop() # Capture the async loop

    if mqtt is None:
        print("[WARNING] paho-mqtt is not installed. Dashboard will run without live MQTT data.")
        app.state.mqtt_client = None
        return
    
    # Initialize MQTT
    app.state.mqtt_client = mqtt.Client()
    app.state.mqtt_client.on_message = on_message
    
    try:
        app.state.mqtt_client.connect("localhost", 1883, 60)
        app.state.mqtt_client.subscribe("factory/assembly/boxes")
        app.state.mqtt_client.loop_start() # Starts the MQTT background thread
        print("[MQTT] Connected and listening to broker...")
    except Exception as e:
        print(f"[WARNING] Could not connect to MQTT Broker: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    client = getattr(app.state, "mqtt_client", None)
    if client is not None:
        client.loop_stop()
        client.disconnect()

# 4. The WebSocket Endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
