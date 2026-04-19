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
It detects cartons with YOLOv8, tracks them with persistent IDs, measures carton orientation, publishes production events over MQTT, stores events in PostgreSQL, keeps CSV files as a backup trail, and streams live telemetry into a browser dashboard.

The project is designed around separation of concerns:

- The vision node handles detection, ROI filtering, tracking, timing, and event generation.
- MQTT decouples the edge pipeline from downstream logging and dashboards.
- The logger persists events into PostgreSQL and mirrors them into CSV as a backup.
- The FastAPI dashboard serves both live WebSocket updates and database-backed history/API endpoints.

## What It Does

- Tracks cartons on a conveyor with persistent IDs using YOLOv8 + BotSort.
- Filters detections using a polygon ROI so only the conveyor region is processed.
- Estimates carton rotation angle from the detected crop using OpenCV geometry.
- Triggers exactly one completion event per carton after it crosses the finish line.
- Generates structured payloads with UUID, timestamp, shift, count, transit time, and angle.
- Streams live events to `factory/assembly/boxes` over MQTT.
- Stores carton events in PostgreSQL using SQLAlchemy and Alembic-managed schema.
- Appends daily shift-specific CSV logs under `data/logs/` as a backup/export path.
- Displays live KPIs and charts in a web dashboard using FastAPI, WebSockets, Plotly, and database-backed API endpoints.

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
MQTT Publish  --->  DB Logger + CSV Backup
        |
        +------->  FastAPI API + MQTT Bridge ---> WebSocket ---> Live Dashboard
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
| PostgreSQL Storage | Persistent carton event history using SQLAlchemy |
| Alembic Migrations | Versioned schema management for local and cloud deployment |
| CSV Backup | Daily, shift-aware structured backup logs |
| Live Dashboard | Browser KPI cards, database-backed history, event table, and Plotly charts |

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
├── deployment/
│   ├── docker-compose.db.yml
│   ├── docker-compose.local.yml
│   └── mosquitto/
│       └── mosquitto.conf
├── models/
├── scripts/
│   ├── fetch_db.py
│   ├── init_db.py
│   ├── run_calibration.py
│   ├── run_pipeline.py
│   ├── start_local_stack.sh
│   ├── start_local_stack.ps1
│   ├── stop_local_stack.sh
│   └── train_model.py
├── src/
│   ├── comms/
│   │   └── streamer.py
│   ├── core/
│   │   ├── orientation.py
│   │   └── tracking.py
│   ├── db/
│   │   ├── base.py
│   │   ├── bootstrap.py
│   │   ├── models.py
│   │   ├── repositories.py
│   │   ├── session.py
│   │   └── settings.py
│   ├── dashboard/
│   │   ├── index.html
│   │   └── main.py
│   └── utils/
│       ├── analytics.py
│       ├── geometry.py
│       └── logger.py
├── alembic/
│   └── versions/
├── alembic.ini
├── .env.example
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
- SQLAlchemy
- Alembic
- PostgreSQL / pgvector
- Mosquitto MQTT Broker

## Setup

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd SmartAssemblyLine
```

### 2. Create and activate a virtual environment

Linux / WSL:

```bash
python -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

This installs the full runtime stack, including:

- FastAPI
- Uvicorn
- Paho MQTT
- SQLAlchemy
- Alembic
- psycopg2-binary
- python-dotenv

### 4. Create the environment file

Copy the example file:

```bash
cp .env.example .env
```

Default `.env` content:

```env
DATABASE_URL=postgresql://smartassembly:smartassembly@localhost:5433/smart_assembly
```

The app auto-loads `.env` from the project root, so you do not need to export the database URL manually in every terminal.

### 5. Prepare required assets

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

## Open And Run The Project

This is the recommended practical flow for VS Code, WSL, or Linux terminals.

### Terminal 1. Open the project

```bash
cd /mnt/d/Machine_Learning/Vision/SmartAssemblyLine
conda activate torch
```

### Terminal 2. Start PostgreSQL in Docker

```bash
docker compose -f deployment/docker-compose.db.yml up -d
```

This starts a local PostgreSQL container with:

```text
host: localhost
port: 5433
database: smart_assembly
user: smartassembly
password: smartassembly
```

### Terminal 3. Apply database migrations

```bash
alembic upgrade head
```

### Terminal 4. Start Mosquitto

```bash
mosquitto
```

If you see `Address already in use`, Mosquitto is already running on port `1883`. That is fine. Leave it and continue.

### Terminal 5. Start the logger

Open a new terminal:

```bash
cd /mnt/d/Machine_Learning/Vision/SmartAssemblyLine
conda activate torch
python src/utils/logger.py
```

What it does:

- subscribes to `factory/assembly/boxes`
- inserts each new event into PostgreSQL
- writes the same event to CSV as a backup
- skips duplicate UUIDs

### Terminal 6. Start the dashboard

Open another terminal:

```bash
cd /mnt/d/Machine_Learning/Vision/SmartAssemblyLine
conda activate torch
uvicorn src.dashboard.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000
```

### Terminal 7. Start the vision pipeline

Open another terminal:

```bash
cd /mnt/d/Machine_Learning/Vision/SmartAssemblyLine
conda activate torch
python scripts/run_pipeline.py
```

### Full startup order

Use this order every time:

1. Open project folder
2. Activate environment
3. Start Docker Postgres
4. Run `alembic upgrade head`
5. Start Mosquitto
6. Start `python src/utils/logger.py`
7. Start `uvicorn src.dashboard.main:app --reload`
8. Open `http://127.0.0.1:8000`
9. Start `python scripts/run_pipeline.py`

## Option 1: Local PC Stack

If the Raspberry Pi 4 handles camera + ROS and the PC runs the rest of the system locally, use:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_local_stack.ps1
```

This mode:

- starts PostgreSQL in Docker on `localhost:5433`
- starts Mosquitto in Docker on `localhost:1883`
- waits for both services to be ready
- runs `alembic upgrade head`
- opens a logger PowerShell window
- opens a dashboard PowerShell window
- opens a pipeline PowerShell window

The infrastructure file used for this mode is:

```text
deployment/docker-compose.local.yml
```

Optional flags:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_local_stack.ps1 -NoPipeline
powershell -ExecutionPolicy Bypass -File scripts/start_local_stack.ps1 -NoDashboard
powershell -ExecutionPolicy Bypass -File scripts/start_local_stack.ps1 -NoLogger
powershell -ExecutionPolicy Bypass -File scripts/start_local_stack.ps1 -NoInfra
```

If you run from WSL Ubuntu with conda, use:

```bash
cd /mnt/d/Machine_Learning/Vision/SmartAssemblyLine
bash scripts/start_local_stack.sh
```

WSL options:

```bash
bash scripts/start_local_stack.sh --conda-env torch
bash scripts/start_local_stack.sh --no-pipeline
bash scripts/start_local_stack.sh --no-dashboard
bash scripts/start_local_stack.sh --no-logger
bash scripts/start_local_stack.sh --no-infra
```

This WSL script:

- activates your conda environment
- starts Docker services
- runs migrations
- starts logger and dashboard in the background
- writes logs under `data/runtime/logs/`
- runs the pipeline in the current terminal

To stop the WSL local stack:

```bash
bash scripts/stop_local_stack.sh
```

## What You Should See

### In the pipeline terminal

- a window named `Production Tracker`
- ROI polygon drawn on the video
- finish line drawn across the frame
- tracked carton IDs and angles
- messages like `[STREAM] Dispatched: BOX-...`

### In the logger terminal

- messages like `[DB] Inserted payload BOX-...`
- messages like `[SAVED] Box 7 -> data/logs/shift_Morning_Shift_YYYY-MM-DD.csv`

### In the browser dashboard

- dashboard status changes to connected
- existing history loads from PostgreSQL on page refresh
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

## Database Setup

The project is now PostgreSQL-only.

### Docker Postgres

The project now includes a Docker Compose file that uses:

```text
pgvector/pgvector:0.8.2-pg17
```

Start it with:

```bash
docker compose -f deployment/docker-compose.db.yml up -d
```

That container exposes:

```text
host: localhost
port: 5433
database: smart_assembly
user: smartassembly
password: smartassembly
```

To make the app use that container, set:

```bash
export SMART_ASSEMBLY_DB_BACKEND=postgres
```

Or set `DATABASE_URL` directly:

```bash
export DATABASE_URL=postgresql://smartassembly:smartassembly@localhost:5433/smart_assembly
```

The project also supports a local `.env` file. A ready-to-edit example is included:

```text
.env.example
```

Copy it to `.env` and edit if needed:

```bash
cp .env.example .env
```

Important:

- SQLite is no longer supported by the project
- the app now auto-loads `.env` from the project root
- every terminal that runs the app will use the same database config as long as `.env` is present
- if neither is set, the app now fails fast instead of silently falling back to a local file

### Initialize the database schema

From the project root, run:

```bash
python scripts/init_db.py
```

This initializes the schema against the configured PostgreSQL database.

### Run Alembic migrations

To apply all tracked schema migrations:

```bash
alembic upgrade head
```

If you are using the Docker database, make sure the container is already running before this step.

### Create a future migration

When you change models later, create a new migration with:

```bash
alembic revision --autogenerate -m "describe your change"
```

## API Endpoints

Once the dashboard server is running, these endpoints are available:

### Event endpoints

- `GET /api/events?limit=10`
- `GET /api/events/latest`

Example:

```bash
curl http://127.0.0.1:8000/api/events?limit=10
curl http://127.0.0.1:8000/api/events/latest
```

### KPI endpoints

- `GET /api/kpis/current`
- `GET /api/stats/shifts`

Example:

```bash
curl http://127.0.0.1:8000/api/kpis/current
curl http://127.0.0.1:8000/api/stats/shifts
```

### Chart endpoints

- `GET /api/charts/overview?limit=50`

Example:

```bash
curl http://127.0.0.1:8000/api/charts/overview?limit=10
```

## Database Fetch Tool

You can now inspect PostgreSQL records with a simple CLI tool instead of writing SQL manually.

### Fetch recent events

```bash
python scripts/fetch_db.py events --limit 20
```

### Fetch only the latest event

```bash
python scripts/fetch_db.py events --latest
```

### Filter by shift and shift date

```bash
python scripts/fetch_db.py events --shift Morning_Shift --shift-date 2026-04-19 --limit 50
```

### Fetch one exact UUID

```bash
python scripts/fetch_db.py events --uuid BOX-20260419-Morning_Shift-0007
```

### Print JSON instead of a table

```bash
python scripts/fetch_db.py events --limit 5 --json
```

### Show shift summaries

```bash
python scripts/fetch_db.py shifts --limit 10
```

### Count rows

```bash
python scripts/fetch_db.py count
python scripts/fetch_db.py count --shift Morning_Shift --shift-date 2026-04-19
```

## Verify The Data Flow

If everything is running, verify it in this order:

1. Logger prints `[DB] Inserted payload ...`
2. Postgres contains rows in `box_events`
3. FastAPI endpoints return JSON data
4. Dashboard shows both history and live updates

To inspect Postgres directly:

```bash
docker exec -it smart-assembly-db psql -U smartassembly -d smart_assembly
```

Then run:

```sql
SELECT * FROM box_events ORDER BY id DESC LIMIT 10;
```

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
- database settings and repository logic
- CSV logging
- tracker filtering and one-shot counting behavior
- dashboard template/API bootstrap checks

## Troubleshooting

### MQTT data is not flowing

- make sure Mosquitto is running on `localhost:1883`
- make sure `paho-mqtt` is installed
- confirm the topic is `factory/assembly/boxes`

### FastAPI endpoints show empty data

- make sure `python src/utils/logger.py` is running
- make sure the logger prints `[DB] Inserted payload ...`
- verify Postgres contains rows in `box_events`
- make sure the dashboard server is started from the project root so `.env` is loaded
- call `curl http://127.0.0.1:8000/api/events?limit=10` to confirm API data directly

### Dashboard does not start

- install `fastapi` and `uvicorn`
- run `uvicorn src.dashboard.main:app --reload`

### Database connection fails

- make sure Docker Postgres is running on `localhost:5433`
- make sure `.env` exists in the project root
- verify `DATABASE_URL` inside `.env`
- run `alembic upgrade head`

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
- The logger depends on MQTT and PostgreSQL.
- The dashboard now supports both live MQTT updates and database-backed historical bootstrap.
- CSV output is kept as a temporary backup path beside database persistence.
- The current implementation is focused on analytics and monitoring, not actuator control.

## License

This project is intended for educational, industrial prototyping, and analytics workflow development.
Add your preferred license here if you plan to publish the repository publicly.
