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
