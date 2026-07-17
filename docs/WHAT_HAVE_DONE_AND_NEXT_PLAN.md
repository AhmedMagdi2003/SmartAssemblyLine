# What Have Done And Next Plan

Last updated: 2026-05-09

This file is a full AI handoff for the Smart Assembly Line project.
Use it in new chats so another AI assistant can continue the work without re-discovering the architecture, previous fixes, deployment modes, and open problems.

## Project Summary

Smart Assembly Line is a computer-vision carton analytics system for a packing line.

Current functional flow:

1. YOLOv8 + BotSort detect and track cartons
2. ROI and size filters keep only valid cartons
3. transit time and orientation are calculated
4. one completion event is generated per carton
5. payload is published over MQTT
6. logger saves the event into PostgreSQL and mirrors it to CSV
7. dashboard reads persisted history from Postgres and also receives live updates

## Current Core Runtime

Main runtime files:

- [scripts/run_pipeline.py](/D:/Machine_Learning/Vision/SmartAssemblyLine/scripts/run_pipeline.py)
- [src/core/tracking.py](/D:/Machine_Learning/Vision/SmartAssemblyLine/src/core/tracking.py)
- [src/utils/analytics.py](/D:/Machine_Learning/Vision/SmartAssemblyLine/src/utils/analytics.py)
- [src/comms/streamer.py](/D:/Machine_Learning/Vision/SmartAssemblyLine/src/comms/streamer.py)
- [src/utils/logger.py](/D:/Machine_Learning/Vision/SmartAssemblyLine/src/utils/logger.py)
- [src/dashboard/main.py](/D:/Machine_Learning/Vision/SmartAssemblyLine/src/dashboard/main.py)
- [src/dashboard/index.html](/D:/Machine_Learning/Vision/SmartAssemblyLine/src/dashboard/index.html)

Database layer:

- [src/db/base.py](/D:/Machine_Learning/Vision/SmartAssemblyLine/src/db/base.py)
- [src/db/settings.py](/D:/Machine_Learning/Vision/SmartAssemblyLine/src/db/settings.py)
- [src/db/session.py](/D:/Machine_Learning/Vision/SmartAssemblyLine/src/db/session.py)
- [src/db/models.py](/D:/Machine_Learning/Vision/SmartAssemblyLine/src/db/models.py)
- [src/db/repositories.py](/D:/Machine_Learning/Vision/SmartAssemblyLine/src/db/repositories.py)

Migration layer:

- [alembic.ini](/D:/Machine_Learning/Vision/SmartAssemblyLine/alembic.ini)
- [alembic/env.py](/D:/Machine_Learning/Vision/SmartAssemblyLine/alembic/env.py)
- initial migration for `box_events` under [alembic](/D:/Machine_Learning/Vision/SmartAssemblyLine/alembic)

## Important Architecture Decisions Already Made

These decisions should be preserved unless there is a strong reason to change them:

- PostgreSQL is the only runtime database now
- SQLite runtime fallback was intentionally removed
- `.env` is auto-loaded with `python-dotenv`
- the main DB URL pattern is:
  - `postgresql://smartassembly:smartassembly@localhost:5433/smart_assembly`
- MQTT is the decoupling layer between vision and persistence/dashboard
- CSV remains as a backup/export path beside the database
- dashboard history must survive refresh and restart by loading from Postgres first
- shift-based continuity is required across restart and power loss

## What Has Been Completed

### 1. Import, path, and tracker startup fixes

Completed:

- script import-path fixes
- tracker config path fix
- startup alignment for project-root execution

Impact:

- `run_pipeline.py` and related modules now resolve project files more reliably
- tracker config files are no longer as fragile to working-directory differences

### 2. Orientation and analytics improvements

Completed:

- carton orientation logic improved
- event payload generation stabilized
- shift-based analytics layer improved

Impact:

- orientation data is more usable in payloads and dashboard
- counts and event generation are more consistent

### 3. Postgres-first persistence

Completed:

- full SQLAlchemy database layer added
- Alembic configured
- initial `box_events` schema migration added
- logger now inserts into Postgres
- logger also writes CSV as backup

Impact:

- dashboard and analysis are no longer dependent on in-memory sessions
- data survives process restart and browser refresh

### 4. `.env` support and runtime configuration

Completed:

- `.env` is auto-loaded from project root
- DB config is no longer spread manually across terminals
- MQTT config is now also env-driven across services

Important MQTT env vars now supported:

- `MQTT_HOST`
- `MQTT_PORT`
- `MQTT_TOPIC`
- `MQTT_USERNAME`
- `MQTT_PASSWORD`
- `MQTT_TLS_ENABLED`
- `MQTT_KEEPALIVE`

Files involved:

- [src/comms/mqtt_config.py](/D:/Machine_Learning/Vision/SmartAssemblyLine/src/comms/mqtt_config.py)
- [src/comms/streamer.py](/D:/Machine_Learning/Vision/SmartAssemblyLine/src/comms/streamer.py)
- [src/utils/logger.py](/D:/Machine_Learning/Vision/SmartAssemblyLine/src/utils/logger.py)
- [src/dashboard/main.py](/D:/Machine_Learning/Vision/SmartAssemblyLine/src/dashboard/main.py)

### 5. Restart-safe shift counting

Completed:

- after shutdown/power-off, counting resumes from the last persisted shift count
- duplicate first-carton IDs after restart were addressed
- night shift continuity across midnight was handled using `shift_date`
- shift CSV naming now respects `shift_date`

Impact:

- same-shift resume is supported
- duplicate DB rejections on first resumed cartons were addressed at the logic level
- same shift continues writing to the same CSV file

### 6. Dashboard history bootstrap

Completed:

- dashboard loads persisted Postgres history on refresh
- dashboard then continues with live updates through WebSocket
- API endpoints were added for events, KPIs, shifts, charts, and health

Available endpoints:

- `GET /api/events?limit=...`
- `GET /api/events/latest`
- `GET /api/kpis/current`
- `GET /api/stats/shifts`
- `GET /api/charts/overview?limit=...`
- `GET /api/health`

### 7. Dashboard behavior improvements

Completed:

- current shift mode and all history mode were introduced
- all-history layout was separated conceptually from the live shift mode
- period filtering ideas were added into the dashboard work
- dashboard can bootstrap historical data from DB after restart
- current-shift layout ordering was changed so top widgets are more operator-focused

Important note:

- some dashboard chart/layout iterations were changed multiple times
- the current state should be verified visually in the browser before doing more UI work

### 8. Database fetch tool

Completed:

- a CLI fetch tool was added for easier DB inspection

File:

- [fetch_db.py](/D:/Machine_Learning/Vision/SmartAssemblyLine/scripts/fetch_db.py)

Purpose:

- inspect recent events
- inspect latest event
- filter by shift and shift date
- count rows
- output JSON for scripting

### 9. Option 1 deployment: full local PC stack

Completed:

- local Docker Compose for Postgres + Mosquitto
- Windows PowerShell launcher
- WSL/Ubuntu launcher
- WSL stop script

Main files:

- [docker-compose.local.yml](/D:/Machine_Learning/Vision/SmartAssemblyLine/deployment/docker-compose.local.yml)
- [mosquitto.conf](/D:/Machine_Learning/Vision/SmartAssemblyLine/deployment/mosquitto/mosquitto.conf)
- [start_local_stack.ps1](/D:/Machine_Learning/Vision/SmartAssemblyLine/scripts/start_local_stack.ps1)
- [start_local_stack.sh](/D:/Machine_Learning/Vision/SmartAssemblyLine/scripts/start_local_stack.sh)
- [stop_local_stack.sh](/D:/Machine_Learning/Vision/SmartAssemblyLine/scripts/stop_local_stack.sh)

Purpose:

- Raspberry Pi or future camera source can remain separate
- local PC runs DB, broker, logger, dashboard, and pipeline

### 10. Raspberry Pi camera integration prep

Completed:

- Raspberry Pi camera integration was planned as a future extension
- the current delivery path remains focused on the local video pipeline and dashboard stack

Purpose:

- keep a future integration path for a Raspberry Pi camera feed
- avoid blocking current local testing

Important note:

- Raspberry Pi runtime is not the active production path yet
- current active test path still uses `data/videos/videoproject 1.mp4`

### 11. Option 3 deployment: hybrid Google Cloud

Completed:

- Google Cloud deployment package added
- hybrid edge launchers added
- Cloud Run dashboard container path added
- Cloud SQL path documented
- Compute Engine VM path added for Mosquitto + logger

Main files:

- [Dockerfile.dashboard](/D:/Machine_Learning/Vision/SmartAssemblyLine/deployment/cloud/Dockerfile.dashboard)
- [Dockerfile.logger](/D:/Machine_Learning/Vision/SmartAssemblyLine/deployment/cloud/Dockerfile.logger)
- [Dockerfile.migrate](/D:/Machine_Learning/Vision/SmartAssemblyLine/deployment/cloud/Dockerfile.migrate)
- [dashboard-service.yaml](/D:/Machine_Learning/Vision/SmartAssemblyLine/deployment/cloud/cloudrun/dashboard-service.yaml)
- [migrate-job.yaml](/D:/Machine_Learning/Vision/SmartAssemblyLine/deployment/cloud/cloudrun/migrate-job.yaml)
- [docker-compose.logger-broker.yml](/D:/Machine_Learning/Vision/SmartAssemblyLine/deployment/cloud/compute/docker-compose.logger-broker.yml)
- [deploy_cloudrun.sh](/D:/Machine_Learning/Vision/SmartAssemblyLine/deployment/cloud/scripts/deploy_cloudrun.sh)
- [GOOGLE_CLOUD_OPTION3_GUIDE.md](/D:/Machine_Learning/Vision/SmartAssemblyLine/docs/GOOGLE_CLOUD_OPTION3_GUIDE.md)

Important design correction already made:

- logger should not be treated as a plain Cloud Run service
- logger is an always-on MQTT subscriber
- the hybrid plan now uses:
  - Cloud Run for dashboard
  - Cloud Run Job for migrations
  - Compute Engine VM for Mosquitto + logger

### 12. Option 4 deployment: full local with online dashboard

Completed:

- local-only runtime can now expose the dashboard online through Cloudflare Tunnel
- quick tunnel mode and named tunnel mode were documented
- tunnel launcher scripts were added for WSL and PowerShell

Main files:

- [dashboard-tunnel.env.example](/D:/Machine_Learning/Vision/SmartAssemblyLine/deployment/cloud/env/dashboard-tunnel.env.example)
- [start_dashboard_tunnel.sh](/D:/Machine_Learning/Vision/SmartAssemblyLine/scripts/start_dashboard_tunnel.sh)
- [start_dashboard_tunnel.ps1](/D:/Machine_Learning/Vision/SmartAssemblyLine/scripts/start_dashboard_tunnel.ps1)
- [LOCAL_ONLINE_DASHBOARD_GUIDE.md](/D:/Machine_Learning/Vision/SmartAssemblyLine/docs/LOCAL_ONLINE_DASHBOARD_GUIDE.md)

Purpose:

- keep full stack on local PC
- expose only the dashboard URL online
- avoid directly exposing Postgres or Mosquitto

## Current Supported Deployment Modes

### Option 1: full local PC

Use when:

- everything except future camera/Raspberry work should stay local
- internet is weak or unreliable
- easiest factory-floor deployment is preferred

### Option 3: hybrid local edge + Google Cloud

Use when:

- local PC runs vision
- cloud hosts dashboard/history
- managers need remote access

### Option 4: full local with online dashboard link

Use when:

- you want to keep DB/logger/dashboard local
- you only need remote dashboard viewing
- you do not want to move persistence to cloud yet

## Known Issues, Leaks, and Gaps

This section is important. These are the current weak points and incomplete areas.

### 1. Raspberry Pi integration is not completed end-to-end

Current state:

- deployment planning exists
- current pipeline still reads local test video

Gap:

- no finalized Pi camera stream ingestion into the real pipeline yet
- no production camera stream bridge validated end-to-end with the existing tracker

### 2. Cloud deployment is prepared but not fully validated end-to-end

Current state:

- deployment files and docs exist
- architecture is more realistic now

Gap:

- no confirmed production rollout log is recorded in the repo
- no verified live Google Cloud runbook from first deployment to real traffic
- no confirmed infrastructure-as-code for all cloud resources

### 3. Security is only partially handled

Current state:

- env-based MQTT credentials are supported
- Cloudflare Tunnel path avoids direct port exposure

Gaps:

- MQTT TLS is configurable but not fully provisioned/documented end-to-end
- no complete certificate-management flow for Mosquitto is included
- no role-based DB hardening document exists yet
- secrets rotation process is not documented

### 4. Dashboard UI still needs product-level cleanup

Current state:

- dashboard is functional
- current shift and all history concepts exist
- multiple layout iterations were already done

Gaps:

- all-history view may still need cleaner product decisions
- chart semantics and operator readability need another review pass
- some UI behavior was changed iteratively and should be stabilized with real user feedback

### 5. API filtering is not complete enough yet

Current state:

- current-shift filtering exists in some endpoints

Gaps:

- date-range filtering is still incomplete as a formal API design
- month/year analytics mode likely needs server-side endpoints instead of only client-side shaping
- shift/day/week/month aggregations are not yet formalized as stable API contracts

### 6. Testing is still not strong enough for production confidence

Current state:

- unit tests exist for analytics, logger, tracking, some dashboard behavior, and MQTT config

Gaps:

- limited real-environment integration testing
- limited cloud-deployment validation tests
- no full end-to-end test from pipeline publish -> MQTT -> logger -> DB -> dashboard
- dashboard/browser behavior is not covered by browser automation tests

### 7. Local launchers exist, but service supervision is still lightweight

Current state:

- there are helpful start scripts

Gaps:

- no true production process manager yet for local long-running use
- no Windows service or Linux systemd setup for the main local runtime
- restart policy outside Docker services is still basic

### 8. Current repo state likely still contains generated or dirty files

Current state:

- previous work observed tracked/generated `__pycache__` artifacts in the tree

Gap:

- repo hygiene should be cleaned before production packaging or public release

### 9. CSV policy is still transitional

Current state:

- CSV is still written as backup

Gaps:

- long-term policy is not finalized:
  - keep CSV only as local backup
  - move exports to object storage
  - or treat CSV as operator export only

### 10. Observability is not mature yet

Gaps:

- no metrics backend
- no alerting policy
- no structured log aggregation
- no deployment health dashboard outside the app itself

## Current Known Functional Risks

These are the main risks a future AI should watch closely:

1. restart/shift continuity logic must not regress
2. duplicate UUID prevention must not regress
3. dashboard current-shift logic and all-history logic can easily drift apart
4. cloud logger/broker topology must not be simplified incorrectly back into an invalid Cloud Run service
5. Raspberry Pi integration should not break the current local test-video path before hardware is available

## Recommended Next Work Plan

### Near-term priorities

1. finalize the real Raspberry Pi camera-to-PC ingestion path
2. verify restart continuity with a power-loss simulation using Postgres data already stored
3. add stronger integration tests for:
   - MQTT publish
   - logger insert
   - dashboard history bootstrap
4. stabilize the dashboard UX for current shift vs all history
5. add proper date-range and aggregation APIs for historical analytics

### Mid-term priorities

1. perform a real Option 3 Google Cloud deployment
2. add TLS and credential hardening for cloud Mosquitto
3. add production process supervision for local services
4. define the long-term CSV retention/export policy
5. add monitoring, alerting, and backup documentation

### Longer-term priorities

1. multi-line or multi-site support
2. richer historical analytics by day/week/month/year
3. operator/admin roles and authentication
4. packaging the local stack into a cleaner installable runtime
5. optional service separation for a more scalable cloud architecture

## Recommended Future AI Prompt

Use something like this in a new chat:

```text
I am continuing work on Smart Assembly Line.

First read:
- docs/WHAT_HAVE_DONE_AND_NEXT_PLAN.md
- docs/RUN_AND_DEBUG_GUIDE.md
- docs/GOOGLE_CLOUD_OPTION3_GUIDE.md
- docs/LOCAL_ONLINE_DASHBOARD_GUIDE.md

Important project facts:
- YOLOv8 + BotSort tracking pipeline
- Postgres-only runtime
- MQTT event flow
- dashboard loads history from DB and continues with live updates
- shift continuity across restart is critical
- do not remove current local video test flow unless explicitly asked
- Option 1, Option 3, and Option 4 deployment modes already exist

Please continue from the documented current state without redoing the earlier architecture work.
Before editing, summarize:
1. current architecture
2. already completed work
3. current open gaps
4. a safe implementation plan for the specific task I ask next
```

## Files A Future AI Should Read First

Recommended order:

1. [WHAT_HAVE_DONE_AND_NEXT_PLAN.md](/D:/Machine_Learning/Vision/SmartAssemblyLine/docs/WHAT_HAVE_DONE_AND_NEXT_PLAN.md)
2. [RUN_AND_DEBUG_GUIDE.md](/D:/Machine_Learning/Vision/SmartAssemblyLine/docs/RUN_AND_DEBUG_GUIDE.md)
3. [Readme.md](/D:/Machine_Learning/Vision/SmartAssemblyLine/Readme.md)
4. [GOOGLE_CLOUD_OPTION3_GUIDE.md](/D:/Machine_Learning/Vision/SmartAssemblyLine/docs/GOOGLE_CLOUD_OPTION3_GUIDE.md)
5. [LOCAL_ONLINE_DASHBOARD_GUIDE.md](/D:/Machine_Learning/Vision/SmartAssemblyLine/docs/LOCAL_ONLINE_DASHBOARD_GUIDE.md)
6. [tracking.py](/D:/Machine_Learning/Vision/SmartAssemblyLine/src/core/tracking.py)
7. [logger.py](/D:/Machine_Learning/Vision/SmartAssemblyLine/src/utils/logger.py)
8. [main.py](/D:/Machine_Learning/Vision/SmartAssemblyLine/src/dashboard/main.py)
9. [repositories.py](/D:/Machine_Learning/Vision/SmartAssemblyLine/src/db/repositories.py)

## Final Notes

- Do not undo the Postgres-only direction.
- Do not assume Raspberry Pi integration is already finished.
- Do not treat current deployment docs as fully validated production evidence.
- Preserve the current test-video flow until the real Pi stream path is ready.
- Treat shift-based continuity and historical persistence as core requirements, not optional features.
