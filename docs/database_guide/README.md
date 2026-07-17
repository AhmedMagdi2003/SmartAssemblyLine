# Smart Assembly Line Database Guide

How to inspect, query, reset, rebuild, and extract data from the project database

| Field | Value |
| --- | --- |
| Project | SmartAssemblyLine |
| Audience | Developers and operators working on the local factory stack |
| Source basis | Current workspace code and docs reviewed on 2026-07-08 |

# 1. Database Mental Model

> Important repo note: this checkout contains `deployment/docker-compose.local.yml`. Use `deployment/docker-compose.local.yml` for the real local database and MQTT stack.

At runtime, this project is `PostgreSQL`-only. The vision pipeline publishes carton completion events over `MQTT`, the logger writes those events into Postgres and mirrors them into CSV, and the FastAPI dashboard reads historical data back from the database.

- The runtime source of truth is Postgres, not the CSV files.
- The only runtime table in the current schema is `box_events`.
- The dashboard mixes live updates over MQTT/WebSocket with database-backed history and analytics endpoints.
- Duplicate events are prevented by a unique `uuid` on each carton event.

**Runtime Facts**

| Setting | Value |
| --- | --- |
| Compose file | `deployment/docker-compose.local.yml` |
| Database container | `smart-assembly-db` |
| MQTT container | `smart-assembly-mqtt` |
| Database image | `pgvector/pgvector:0.8.2-pg17` |
| Database URL | `postgresql://smartassembly:smartassembly@localhost:5433/smart_assembly` |
| Database name | `smart_assembly` |
| User / password | `smartassembly / smartassembly` |
| Compose DB volume key | `smart_assembly_db_data` (Docker will project-prefix the real volume name) |
| Backup trail | `data/logs/shift_<ShiftName>_<YYYY-MM-DD>.csv` |

# 2. File Map You Will Actually Use

These are the main files that matter when you need to understand, query, or rebuild the database layer.

**Database File Map**

| Path | Why it matters |
| --- | --- |
| `src/db/settings.py` | Loads `.env` and resolves `DATABASE_URL`. |
| `src/db/session.py` | Builds the SQLAlchemy `engine`, `SessionLocal`, and `get_db()` helper. |
| `src/db/models.py` | Defines the `BoxEvent` ORM model and its columns. |
| `src/db/repositories.py` | Contains the read/write functions used by the logger and dashboard. |
| `src/db/bootstrap.py` | Runs `Base.metadata.create_all()` for local bootstrapping. |
| `scripts/init_db.py` | Small entry point that calls `create_database()`. |
| `alembic/env.py` | Points Alembic at the same runtime database URL and metadata. |
| `alembic/versions/20260412_0001_create_box_events.py` | Current tracked schema migration. |
| `scripts/fetch_db.py` | CLI tool for extracting rows, summaries, and counts without writing SQL. |
| `src/utils/logger.py` | Subscribes to MQTT, inserts rows into Postgres, and mirrors them to CSV. |
| `src/dashboard/main.py` | Reads history and KPIs from repository functions and exposes API endpoints. |
| `deployment/docker-compose.local.yml` | Starts the local Postgres and Mosquitto containers. |

# 3. What The Database Stores

The current schema stores completed carton events in one table named `box_events`. The `uuid` is the important business key, and it encodes the operational shift date and shift name.

**`box_events` Columns**

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | integer | Primary key used for internal ordering. |
| `uuid` | string(128) | Unique event key such as `BOX-20260404-Morning_Shift-0001`. |
| `yolo_session_id` | integer | Tracker ID at the moment the carton was completed. |
| `timestamp_iso` | string(64) | Production timestamp stored as text and used in ordering. |
| `shift` | string(64) | Logical shift name such as `Morning_Shift`. |
| `shift_count` | integer | Running carton count inside the shift window. |
| `transit_time_sec` | float | Measured carton travel time. |
| `orientation_deg` | float | Measured orientation angle from the vision step. |
| `status` | string(32) | Current code writes `COMPLETED`. |
| `created_at` | timestamp with time zone | Database-side insertion timestamp from `now()`. |

- The runtime app is Postgres-only even though some unit tests use SQLite as a lightweight test harness.
- The effective `shift_date` used by filters and KPIs is derived from the `uuid` prefix, not from `created_at`.
- For night-shift data that crosses midnight, the operational date still comes from the encoded `uuid` date. This is intentional and is also covered by tests.
- The logger writes CSV only after a successful new database insert. If the same `uuid` is seen again, the duplicate is skipped.

# 4. Start, Stop, And Health-Check The Database

## 4.1 Start only the database infrastructure

This is the minimum you need if you want Postgres and MQTT available but you are not launching the full app stack.

```text
docker compose -f deployment/docker-compose.local.yml up -d
python -m alembic upgrade head
python -c "from src.db.session import DATABASE_URL; print(DATABASE_URL)" 
```

## 4.2 Start the local stack the repo already provides

The PowerShell launcher starts Docker, waits for health, applies Alembic migrations, then launches the logger and dashboard.

```text
powershell -ExecutionPolicy Bypass -File scripts/start_local_stack.ps1
powershell -ExecutionPolicy Bypass -File scripts/start_local_stack.ps1 -NoPipeline
```

## 4.3 Stop the stack without deleting data

The provided stop script shuts down background services and runs `docker compose down`, but it does not erase the Postgres volume.

```text
powershell -ExecutionPolicy Bypass -File scripts/stop_local_stack.ps1
docker compose -f deployment/docker-compose.local.yml down
```

## 4.4 Quick health checks

```text
docker ps --filter "name=smart-assembly"
docker inspect -f "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" smart-assembly-db
python scripts/fetch_db.py count
curl http://127.0.0.1:8000/api/health
```

- If `api/health` says `database=connected`, the dashboard can reach the same database URL the app is using.
- If `scripts/fetch_db.py count` works but the dashboard is empty, the dashboard process may be running with a different environment or before migrations were applied.

# 5. Extract Data Without Writing SQL

The easiest extraction tool already in the repo is `scripts/fetch_db.py`. It uses the same SQLAlchemy session layer as the main app, so it is the safest first step for day-to-day inspection.

## 5.1 Read recent or specific events

```text
python scripts/fetch_db.py events --limit 20
python scripts/fetch_db.py events --latest
python scripts/fetch_db.py events --shift Morning_Shift --shift-date 2026-04-19 --limit 50
python scripts/fetch_db.py events --uuid BOX-20260419-Morning_Shift-0007
python scripts/fetch_db.py events --limit 5 --json
```

## 5.2 Read summaries and counts

```text
python scripts/fetch_db.py shifts --limit 10
python scripts/fetch_db.py count
python scripts/fetch_db.py count --shift Morning_Shift --shift-date 2026-04-19
```

- Use `--json` when you want structured output that is easy to redirect into a file or another script.
- The `--shift-date` filter matches the encoded operational date in the UUID prefix, which is why it works correctly for overnight shifts.

## 5.3 Read through the dashboard API

```text
curl "http://127.0.0.1:8000/api/events?limit=20"
curl "http://127.0.0.1:8000/api/events/latest"
curl "http://127.0.0.1:8000/api/kpis/current"
curl "http://127.0.0.1:8000/api/stats/shifts?limit=10"
curl "http://127.0.0.1:8000/api/charts/overview?limit=100"
curl "http://127.0.0.1:8000/api/events?current_shift_only=true&limit=100"
curl "http://127.0.0.1:8000/api/charts/overview?shift=Morning_Shift&shift_date=2026-04-19&limit=100" 
```

- The API is useful when you want the same shape the browser dashboard consumes.
- In `/api/events`, rows are fetched newest-first in the repository layer and then reversed before the API response, so the API payload is oldest-to-newest inside the selected result set.

# 6. Extract Data With Direct SQL

When `fetch_db.py` is not enough, open `psql` inside the Postgres container and run direct SQL against `box_events`.

```text
docker exec -it smart-assembly-db psql -U smartassembly -d smart_assembly
```

## 6.1 Latest rows

```text
SELECT id, uuid, shift, shift_count, transit_time_sec, orientation_deg, timestamp_iso
FROM box_events
ORDER BY id DESC
LIMIT 20;
```

## 6.2 One exact shift window

```text
SELECT id, uuid, shift_count, transit_time_sec, orientation_deg, timestamp_iso
FROM box_events
WHERE shift = 'Morning_Shift'
  AND uuid LIKE 'BOX-20260419-Morning_Shift-%'
ORDER BY id;
```

## 6.3 Summary by operational shift window

```text
SELECT split_part(uuid, '-', 2) AS shift_date_raw,
       shift,
       COUNT(*) AS events,
       MAX(shift_count) AS shift_volume,
       ROUND(AVG(transit_time_sec)::numeric, 2) AS avg_transit_sec
FROM box_events
GROUP BY split_part(uuid, '-', 2), shift
ORDER BY shift_date_raw DESC, shift;
```

## 6.4 Find slow or misaligned cartons

```text
SELECT uuid, shift, shift_count, transit_time_sec, orientation_deg, timestamp_iso
FROM box_events
WHERE transit_time_sec > 2.0
   OR ABS(orientation_deg) > 15
ORDER BY timestamp_iso DESC;
```

- Use `MAX(shift_count)` when you want final volume for a shift window, because `shift_count` is cumulative inside that window.
- If you need file exports, the safest repo-native path is usually `python scripts/fetch_db.py ... --json` and then redirect the output in your shell.

# 7. Extract Data From Python

Use the repository helpers when you want to write one-off analysis scripts without re-implementing filters and serializers.

## 7.1 Repository-level reads

```text
from src.db.repositories import get_current_kpis, get_shift_summary, list_recent_box_events

print(get_current_kpis())
print(get_shift_summary(limit=3))

for row in list_recent_box_events(limit=5, shift='Morning_Shift', shift_date='2026-04-19'):
    print(row['uuid'], row['transit_time_sec'])
```

## 7.2 Raw SQLAlchemy session reads

```text
from src.db.models import BoxEvent
from src.db.session import SessionLocal

session = SessionLocal()
try:
    rows = (
        session.query(BoxEvent)
        .order_by(BoxEvent.id.desc())
        .limit(10)
        .all()
    )
    for row in rows:
        print(row.id, row.uuid, row.transit_time_sec)
finally:
    session.close()
```

- Use repository functions when you want the same semantics as the dashboard and logger.
- Use raw sessions when you need custom SQLAlchemy queries the repository layer does not already expose.

# 8. Reset The Database Safely

> Before any reset, stop the writer processes first: the vision pipeline, the logger, and the dashboard. If they stay running, they can immediately reconnect and start repopulating the database while you are trying to clear it.

## 8.1 Optional: take a plain SQL backup first

```text
docker exec smart-assembly-db pg_dump -U smartassembly smart_assembly > smart_assembly_backup.sql
```

## 8.2 Reset only the data, keep the schema

This is the fastest safe reset when the table shape is fine and you only want an empty history.

```text
docker exec -i smart-assembly-db psql -U smartassembly -d smart_assembly -c "TRUNCATE TABLE box_events RESTART IDENTITY;" 
```

## 8.3 Reset the schema through Alembic

Use this when you want to drop tracked tables and recreate them from the migration history without destroying the Docker container itself.

```text
python -m alembic downgrade base
python -m alembic upgrade head
```

## 8.4 Wipe the whole local database volume and rebuild from zero

This is the most complete local reset. It removes the Docker-managed Postgres volume, starts a fresh container, and reapplies migrations.

```text
docker compose -f deployment/docker-compose.local.yml down -v
docker compose -f deployment/docker-compose.local.yml up -d
python -m alembic upgrade head
```

- `docker compose ... down -v` removes the Postgres volume and the Mosquitto volumes declared in the same compose file.
- `scripts/stop_local_stack.ps1` does not erase database data because it calls plain `docker compose down`.
- `python scripts/init_db.py` is useful for local bootstrapping, but for a real repo-consistent rebuild you should prefer `python -m alembic upgrade head`.

## 8.5 Recommended reset choices

**Which reset should you choose?**

| Situation | Best reset |
| --- | --- |
| You only want to clear history | `TRUNCATE TABLE box_events RESTART IDENTITY;` |
| You changed migrations and want a clean reapply | `python -m alembic downgrade base` then `python -m alembic upgrade head` |
| You want a truly fresh local DB container | `docker compose -f deployment/docker-compose.local.yml down -v` then `up -d` and `upgrade head` |

# 9. Change The Schema And Keep The Project Healthy

When you add new columns or tables, change the ORM model first, generate a migration, inspect it, then upgrade the database.

1. Edit the SQLAlchemy model under `src/db/models.py`.
2. Generate a migration with `python -m alembic revision --autogenerate -m "describe your change"`.
3. Inspect the generated file under `alembic/versions/` before running it.
4. Apply the change with `python -m alembic upgrade head`.
5. Smoke-test the database with `python scripts/fetch_db.py count` and one or two dashboard endpoints.

```text
python -m alembic revision --autogenerate -m "add new column"
python -m alembic upgrade head
python scripts/fetch_db.py count
curl http://127.0.0.1:8000/api/health
```

- The current tracked migration is `alembic/versions/20260412_0001_create_box_events.py`.
- Alembic uses the same database URL resolver as the app because `alembic/env.py` calls `get_database_url()`.
- If you skip migration review, it is easy to create a diff that technically runs but does not match the intended schema.

# 10. Troubleshooting And Useful Real-World Notes

- If you get `DATABASE_URL is not set`, either create `.env` in the project root or export `DATABASE_URL` manually before starting the process.
- If the logger falls back to CSV-only behavior, the database layer was unavailable when `src/utils/logger.py` started.
- If the dashboard health endpoint says `database=error`, test the same DB URL with `python scripts/fetch_db.py count` from the same environment.
- If you see fewer rows than expected, remember that duplicate UUIDs are ignored on insert by design.
- If you want a clean shutdown without losing data, use the stop script or `docker compose down` without `-v`.
- If you want a real wipe, `docker compose down -v` is the command that matters. Stopping containers alone is not enough.
- If you are comparing output from the API and direct SQL, remember the API may reverse event order for the frontend experience.

# 11. Quick Command Checklist

```text
# Start local infrastructure
docker compose -f deployment/docker-compose.local.yml up -d
python -m alembic upgrade head

# Check the database quickly
python scripts/fetch_db.py count
curl http://127.0.0.1:8000/api/health

# Read events
python scripts/fetch_db.py events --limit 20
python scripts/fetch_db.py events --limit 20 --json

# Empty the table but keep the schema
docker exec -i smart-assembly-db psql -U smartassembly -d smart_assembly -c "TRUNCATE TABLE box_events RESTART IDENTITY;"

# Full local wipe and rebuild
docker compose -f deployment/docker-compose.local.yml down -v
docker compose -f deployment/docker-compose.local.yml up -d
python -m alembic upgrade head
```
