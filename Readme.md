# Smart Assembly Line

<p align="center">
  <strong>Industrial computer vision for carton tracking, orientation analytics, MQTT telemetry, and live production monitoring.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8%2B-3776AB?style=flat&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/OpenCV-4.x-5C3EE8?style=flat&logo=opencv&logoColor=white" alt="OpenCV">
  <img src="https://img.shields.io/badge/YOLOv8-Ultralytics-111827?style=flat" alt="YOLOv8">
  <img src="https://img.shields.io/badge/MQTT-Mosquitto-3C5280?style=flat" alt="MQTT">
  <img src="https://img.shields.io/badge/FastAPI-Live_Dashboard-009688?style=flat&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Plotly-Analytics-3F4F75?style=flat&logo=plotly&logoColor=white" alt="Plotly">
</p>

---

## Overview

Smart Assembly Line is a modular edge-to-analytics system built for packing-line monitoring.
It detects cartons with YOLOv8, tracks them with persistent IDs, measures carton orientation, publishes production events over MQTT, stores shift-based CSV logs, and streams live telemetry into a browser dashboard.

The project is designed around separation of concerns:

- The vision node handles detection, ROI filtering, tracking, timing, and event generation.
- MQTT decouples the edge pipeline from downstream logging and dashboards.
- The logger writes structured shift files for historical analysis.
- The FastAPI dashboard bridges MQTT into WebSocket updates for live KPI monitoring.

## What It Does

- Tracks cartons on a conveyor with persistent IDs using YOLOv8 + BotSort.
- Filters detections using a polygon ROI so only the conveyor region is processed.
- Estimates carton rotation angle from the detected crop using OpenCV geometry.
- Triggers exactly one completion event per carton after it crosses the finish line.
- Generates structured payloads with UUID, timestamp, shift, count, transit time, and angle.
- Streams live events to `factory/assembly/boxes` over MQTT.
- Appends daily shift-specific CSV logs under `data/logs/`.
- Displays live KPIs and charts in a web dashboard using WebSockets and Plotly.

## System Flow

```text
Video / Camera Frame
        |
        v
YOLOv8 Detection + BotSort Tracking
        |
        v
ROI Filter + Size Filter + Finish-Line Trigger
        |
        v
Orientation + Transit Time + Shift Analytics
        |
        v
MQTT Publish  --->  CSV Logger
        |
        +------->  FastAPI MQTT Bridge ---> WebSocket ---> Live Dashboard
```

## Features

| Module | Description |
|--------|-------------|
| Vision Tracking | YOLOv8 detection with persistent carton IDs |
| ROI Filtering | Polygon fence to ignore background factory noise |
| Orientation Analytics | OpenCV-based carton angle extraction |
| Event Triggering | One-time payload generation after finish-line crossing |
| Shift Analytics | Auto shift detection and per-shift counters |
| MQTT Streaming | Non-blocking telemetry publishing |
| CSV Logging | Daily, shift-aware structured event logs |
| Live Dashboard | Browser KPI cards, event table, and Plotly charts |

## Project Structure

```text
SmartAssemblyLine/
├── config/
│   ├── botsort.yaml
│   ├── bytetrack.yaml
│   └── tracker_params.yaml
├── data/
│   ├── logs/
│   ├── test_tmp/
│   └── videos/
├── models/
├── scripts/
│   ├── run_calibration.py
│   ├── run_pipeline.py
│   └── train_model.py
├── src/
│   ├── comms/
│   │   └── streamer.py
│   ├── core/
│   │   ├── orientation.py
│   │   └── tracking.py
│   ├── dashboard/
│   │   ├── index.html
│   │   └── main.py
│   └── utils/
│       ├── analytics.py
│       ├── geometry.py
│       └── logger.py
├── tests/
├── requirements.txt
└── Readme.md
```

## Tech Stack

- Python
- OpenCV
- Ultralytics YOLOv8
- NumPy
- Paho MQTT
- FastAPI
- Uvicorn
- Plotly.js
- Mosquitto MQTT Broker

## Setup

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd SmartAssemblyLine
```

### 2. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

If you plan to use the live dashboard and MQTT pipeline, make sure these packages are installed successfully:

- `fastapi`
- `uvicorn`
- `paho-mqtt`

### 4. Prepare required assets

Before running the project, confirm that these files exist:

- YOLO weights: `models/best.pt`
- Tracking config: `config/botsort.yaml`
- Main tracker config: `config/tracker_params.yaml`
- Test video: `data/videos/conveyor.mp4`

## Configuration

The main runtime settings are stored in `config/tracker_params.yaml`.

You can change:

- model weights path
- tracker config file
- confidence threshold
- ROI polygon points
- finish-line position
- minimum box area
- minimum lifespan
- shift schedule

## How To Run

This section shows the exact order to run the full project from the `SmartAssemblyLine` directory in the VS Code terminal.

### Terminal 1. Open the project directory

If you are not already inside the project folder:

```bash
cd /mnt/d/Machine_Learning/Vision/SmartAssemblyLine
```

If you are using a Python environment, activate it first.

Example:

```bash
conda activate torch
```

### Terminal 2. Install dependencies

Run this once if the environment is not prepared yet:

```bash
pip install -r requirements.txt
```

If needed, install the live-system packages explicitly:

```bash
pip install fastapi uvicorn paho-mqtt
```

### Terminal 3. Check required files

Make sure these files exist before starting:

```text
models/best.pt
data/videos/conveyor.mp4
config/tracker_params.yaml
config/botsort.yaml
```

### Terminal 4. Start the MQTT broker

Run:

```bash
mosquitto
```

If you see:

```text
Error: Address already in use
```

that usually means Mosquitto is already running on port `1883`. In that case, do not start another broker. Just leave it and continue to the next step.

### Terminal 5. Start the CSV logger

Open a new VS Code terminal in the same project directory and run:

```bash
cd /mnt/d/Machine_Learning/Vision/SmartAssemblyLine
python src/utils/logger.py
```

The logger waits for incoming MQTT payloads and writes shift CSV files into `data/logs/`.

### Terminal 6. Start the dashboard server

Open another new terminal and run:

```bash
cd /mnt/d/Machine_Learning/Vision/SmartAssemblyLine
uvicorn src.dashboard.main:app --reload
```

Then open this address in your browser:

```text
http://127.0.0.1:8000
```

### Terminal 7. Start the vision pipeline

Open one more terminal and run:

```bash
cd /mnt/d/Machine_Learning/Vision/SmartAssemblyLine
python scripts/run_pipeline.py
```

This starts the YOLO tracking pipeline on the sample conveyor video.

## Expected Run Order

For the full system, always use this order:

1. Open the `SmartAssemblyLine` directory.
2. Activate your Python environment.
3. Install dependencies if needed.
4. Start Mosquitto, or confirm it is already running on port `1883`.
5. Start `python src/utils/logger.py`.
6. Start `uvicorn src.dashboard.main:app --reload`.
7. Open `http://127.0.0.1:8000`.
8. Start `python scripts/run_pipeline.py`.

## What You Should See

### In the pipeline terminal

- a window named `Production Tracker`
- ROI polygon drawn on the video
- finish line drawn across the frame
- tracked carton IDs and angles
- messages like `[STREAM] Dispatched: BOX-...`

### In the logger terminal

- messages like `[SAVED] Box 7 -> data/logs/shift_Morning_Shift_YYYY-MM-DD.csv`

### In the browser dashboard

- dashboard status changes to connected
- KPI cards update in real time
- orientation scatter plot updates
- transit-time histogram grows
- cumulative volume line chart updates
- event table fills with recent cartons

## Quick Run Modes

### Run only the vision pipeline

Use this if you only want to test tracking and display:

```bash
python scripts/run_pipeline.py
```

### Run pipeline plus logger

Use this if you want CSV export without the dashboard:

```bash
python src/utils/logger.py
python scripts/run_pipeline.py
```

Run them in separate terminals.

## Output Files

### CSV Logs

Completed carton events are stored in:

```text
data/logs/shift_<ShiftName>_<YYYY-MM-DD>.csv
```

Example:

```text
data/logs/shift_Morning_Shift_2026-04-04.csv
```

### Payload Example

```json
{
  "uuid": "BOX-20260404-Morning_Shift-0001",
  "yolo_session_id": 7,
  "timestamp_iso": "2026-04-04T08:15:00",
  "shift": "Morning_Shift",
  "shift_count": 1,
  "transit_time_sec": 1.5,
  "orientation_deg": 12.5,
  "status": "COMPLETED"
}
```

## Dashboard Metrics

The dashboard currently shows:

- current active shift
- cumulative shift volume
- average transit time
- last recorded angle
- orientation drift scatter plot
- transit time histogram
- cumulative shift volume line chart
- recent raw event log
- client-side CSV export

## Testing

Automated validation tests are available under `tests/`.

Run them with:

```bash
python -m unittest discover -s tests -v
```

The tests cover:

- payload generation and shift reset logic
- orientation estimation behavior
- CSV logging
- tracker filtering and one-shot counting behavior
- dashboard template presence checks

## Troubleshooting

### MQTT data is not flowing

- make sure Mosquitto is running on `localhost:1883`
- make sure `paho-mqtt` is installed
- confirm the topic is `factory/assembly/boxes`

### Dashboard does not start

- install `fastapi` and `uvicorn`
- run `uvicorn src.dashboard.main:app --reload`

### Pipeline does not detect anything

- check that `models/best.pt` exists
- verify `data/videos/conveyor.mp4` exists
- confirm ROI points in `config/tracker_params.yaml` match your video
- lower the confidence threshold if needed

### No CSV files are created

- confirm the logger is running
- confirm the broker is running before starting the logger
- check whether cartons are actually crossing the finish line

## Notes

- The project is built around modular communication, so each layer can be tested independently.
- The vision node can run without the dashboard.
- The logger and dashboard depend on MQTT if you want live telemetry.
- The current implementation is focused on analytics and monitoring, not actuator control.

## License

This project is intended for educational, industrial prototyping, and analytics workflow development.
Add your preferred license here if you plan to publish the repository publicly.
