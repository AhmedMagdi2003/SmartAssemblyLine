# Run And Debug Guide

This guide shows how to open, run, verify, and debug the full Smart Assembly Line project.

## Project Directory

Always start from:

```bash
cd /mnt/d/Machine_Learning/Vision/SmartAssemblyLine
conda activate torch
```

## Prerequisites

Make sure these are installed:

```bash
pip install -r requirements.txt
```

Make sure these files exist:

```text
models/best.pt
data/videos/conveyor.mp4
config/tracker_params.yaml
config/botsort.yaml
.env
```

## Database Setup

The project is PostgreSQL-only.

### Start Docker Postgres

```bash
docker compose -f deployment/docker-compose.db.yml up -d
```

Database connection used by the project:

```text
postgresql://smartassembly:smartassembly@localhost:5433/smart_assembly
```

### Apply Alembic migrations

```bash
alembic upgrade head
```

### Verify the app sees the correct database

```bash
python -c "from src.db.session import DATABASE_URL; print(DATABASE_URL)"
```

Expected:

```text
postgresql://smartassembly:smartassembly@localhost:5433/smart_assembly
```

## Full Run Order

Use this order every time.

### Terminal 1. Start Mosquitto

```bash
mosquitto
```

If you see `Address already in use`, Mosquitto is already running. Continue.

### Terminal 2. Start the logger

```bash
cd /mnt/d/Machine_Learning/Vision/SmartAssemblyLine
conda activate torch
python src/utils/logger.py
```

Expected logger output after events arrive:

```text
[DB] Inserted payload BOX-...
[SAVED] Box ... -> data/logs/shift_...csv
```

### Terminal 3. Start the dashboard

```bash
cd /mnt/d/Machine_Learning/Vision/SmartAssemblyLine
conda activate torch
uvicorn src.dashboard.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

### Terminal 4. Start the vision pipeline

```bash
cd /mnt/d/Machine_Learning/Vision/SmartAssemblyLine
conda activate torch
python scripts/run_pipeline.py
```

## API Endpoints

Once the dashboard server is running:

### Events

```bash
curl http://127.0.0.1:8000/api/events?limit=10
curl http://127.0.0.1:8000/api/events/latest
```

### KPIs

```bash
curl http://127.0.0.1:8000/api/kpis/current
curl http://127.0.0.1:8000/api/stats/shifts
```

### Charts

```bash
curl http://127.0.0.1:8000/api/charts/overview?limit=10
```

## Verify PostgreSQL Directly

Open psql inside the Docker container:

```bash
docker exec -it smart-assembly-db psql -U smartassembly -d smart_assembly
```

Then run:

```sql
SELECT id, uuid, shift, shift_count
FROM box_events
ORDER BY id DESC
LIMIT 10;
```

## If Logger Inserts But FastAPI Endpoints Return Empty Data

Run these commands in order.

### 1. Verify the dashboard process is using Postgres

In the same terminal where you start `uvicorn`:

```bash
python -c "from src.db.session import DATABASE_URL; print(DATABASE_URL)"
```

It must print:

```text
postgresql://smartassembly:smartassembly@localhost:5433/smart_assembly
```

### 2. Verify rows exist in Postgres

```bash
docker exec -it smart-assembly-db psql -U smartassembly -d smart_assembly -c "SELECT id, uuid, shift, shift_count FROM box_events ORDER BY id DESC LIMIT 10;"
```

### 3. Restart the dashboard cleanly

Stop the running dashboard with `Ctrl+C`, then restart:

```bash
cd /mnt/d/Machine_Learning/Vision/SmartAssemblyLine
conda activate torch
uvicorn src.dashboard.main:app --reload
```

### 4. Test the endpoints again

```bash
curl http://127.0.0.1:8000/api/events?limit=10
curl http://127.0.0.1:8000/api/kpis/current
curl http://127.0.0.1:8000/api/charts/overview?limit=10
```

## If Refresh Clears The Dashboard

The dashboard restores state from these endpoints on page load:

- `/api/events`
- `/api/kpis/current`
- `/api/charts/overview`

If refreshing clears the page, one of these is true:

- FastAPI is connected to the wrong database
- PostgreSQL has no rows
- the dashboard server was started before `.env` was in place and needs restart

Use this exact check:

```bash
python -c "from src.db.session import DATABASE_URL; print(DATABASE_URL)"
docker exec -it smart-assembly-db psql -U smartassembly -d smart_assembly -c "SELECT id, uuid, shift, shift_count FROM box_events ORDER BY id DESC LIMIT 10;"
curl http://127.0.0.1:8000/api/events?limit=10
```

## Quick Health Checklist

If everything is working:

1. `python src/utils/logger.py` prints DB insert messages
2. `SELECT * FROM box_events ...` shows rows
3. `curl /api/events?limit=10` returns JSON data
4. dashboard shows history after refresh
5. dashboard continues updating live when new boxes finish

## Notes

- The logger writes to PostgreSQL first and CSV second.
- CSV is currently kept as a backup/export path.
- The dashboard uses both database history and live MQTT updates.
- `.env` is auto-loaded from the project root.
