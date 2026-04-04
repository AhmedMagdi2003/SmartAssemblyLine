# Live Dashboard: Execution Guide

The Smart Assembly Dashboard uses FastAPI to bridge the backend MQTT broker with a frontend WebSocket. This allows the browser UI to update in real-time without page reloads.

## Prerequisites
Ensure the Mosquitto MQTT broker is active on your host machine:
`​`​`bash
# For Ubuntu/Debian/Raspberry Pi OS
sudo systemctl status mosquitto
# If not running, start it: sudo systemctl start mosquitto
`​`​`

## Execution Steps

To run the full visual pipeline, you must launch the services in separate terminal windows to avoid blocking the event loops.

### Step 1: Start the Dashboard Backend
This starts the ASGI server that serves the HTML page and listens to the MQTT stream.
`​`​`bash
cd SmartAssemblyLine
uvicorn src.dashboard.main:app --host 0.0.0.0 --port 8000
`​`​`
*Wait for the `[MQTT] Connected and listening...` confirmation in the console.*

### Step 2: Start the Vision Node (Data Generator)
In a new terminal window, start the camera pipeline.
`​`​`bash
cd SmartAssemblyLine
python scripts/run_pipeline.py
`​`​`

### Step 3: View the Interface
Open any modern web browser (Chrome, Firefox, Safari) and navigate to:
* **Localhost:** `http://localhost:8000`
* **Network:** `http://<YOUR_DEVICE_IP>:8000` (if accessing the Raspberry Pi from another laptop).

The dashboard will display a green `CONNECTED (LIVE)` badge. As the video processes and boxes cross the finish line, the UI cards and tables will update instantly.