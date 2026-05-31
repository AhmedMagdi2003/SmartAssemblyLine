# Google Cloud Option 3 Guide

This guide is for the hybrid deployment model that fits Smart Assembly Line best:

- Raspberry Pi or camera source:
  - sends video to the local PC
- Local PC:
  - runs `scripts/run_pipeline.py`
  - publishes carton events to MQTT in Google Cloud
- Google Cloud:
  - Cloud SQL for PostgreSQL
  - Cloud Run for the dashboard and API
  - Google Compute Engine VM for Mosquitto and the always-on logger

This layout keeps the heavy computer-vision work local and moves only events to the cloud.

## Why This Topology

The dashboard is a normal web service, so Cloud Run is a good fit.

The logger is different:

- it is an always-on MQTT subscriber
- it does not serve HTTP traffic
- a plain Cloud Run service is not a good runtime for that pattern

For that reason, Option 3 uses:

- Cloud Run for `dashboard`
- Cloud Run Job for Alembic migrations
- Compute Engine VM for `logger + Mosquitto`

## Files Used

Cloud Run:

- `deployment/cloud/Dockerfile.dashboard`
- `deployment/cloud/Dockerfile.migrate`
- `deployment/cloud/cloudrun/dashboard-service.yaml`
- `deployment/cloud/cloudrun/migrate-job.yaml`

Google VM:

- `deployment/cloud/Dockerfile.logger`
- `deployment/cloud/compute/docker-compose.logger-broker.yml`
- `deployment/cloud/compute/mosquitto/mosquitto.conf`
- `deployment/cloud/env/logger.env.example`

Local PC edge:

- `deployment/cloud/env/edge-hybrid.env.example`
- `scripts/start_hybrid_edge.sh`
- `scripts/start_hybrid_edge.ps1`

## Environment Variables

The runtime now supports these MQTT settings everywhere:

- `MQTT_HOST`
- `MQTT_PORT`
- `MQTT_TOPIC`
- `MQTT_USERNAME`
- `MQTT_PASSWORD`
- `MQTT_TLS_ENABLED`
- `MQTT_KEEPALIVE`

This lets the same code run locally or against the cloud broker without changing Python files.

## Google Cloud Resources To Create

Create these resources in one Google Cloud project:

1. Artifact Registry Docker repository
2. Cloud SQL PostgreSQL instance
3. Secret Manager secret for `DATABASE_URL`
4. Compute Engine e2-micro VM for:
   - Mosquitto
   - logger container
5. Cloud Run service for the dashboard
6. Cloud Run job for Alembic migrations

Official references used:

- [Cloud Run deploy containers](https://cloud.google.com/run/docs/deploying)
- [Connect Cloud Run to Cloud SQL for PostgreSQL](https://cloud.google.com/sql/docs/postgres/connect-instance-cloud-run)
- [Cloud SQL for PostgreSQL](https://cloud.google.com/sql/docs/postgres/)
- [Cloud Run jobs](https://cloud.google.com/run/docs/create-jobs)
- [Cloud Run secrets](https://cloud.google.com/run/docs/configuring/jobs/secrets)
- [Cloud Run minimum instances](https://docs.cloud.google.com/run/docs/configuring/min-instances)
- [Cloud Run billing settings](https://cloud.google.com/run/docs/configuring/cpu-allocation)

## Step 1. Build The Images

From the project root:

```bash
export PROJECT_ID=your-project-id
export REGION=us-central1
export REPOSITORY=smart-assembly
bash deployment/cloud/scripts/deploy_cloudrun.sh
```

This builds and pushes:

- `dashboard`
- `logger`
- `migrate`

to Artifact Registry.

## Step 2. Create Cloud SQL

Create a PostgreSQL instance and database:

- instance name: your choice
- database: `smart_assembly`
- user: `smartassembly`

Then prepare a SQLAlchemy URL for production.

For Cloud Run with Cloud SQL socket mount, the practical format is:

```text
postgresql://smartassembly:YOUR_DB_PASSWORD@/smart_assembly?host=/cloudsql/PROJECT_ID:REGION:INSTANCE_NAME
```

Store that value in Secret Manager as:

- `smart-assembly-database-url`

## Step 3. Deploy The Migration Job

Replace the placeholders in:

- `deployment/cloud/cloudrun/migrate-job.yaml`

Then run:

```bash
gcloud run jobs replace deployment/cloud/cloudrun/migrate-job.yaml --region "$REGION"
gcloud run jobs execute smart-assembly-migrate --region "$REGION"
```

## Step 4. Deploy The Dashboard To Cloud Run

Replace placeholders in:

- `deployment/cloud/cloudrun/dashboard-service.yaml`

Then deploy:

```bash
gcloud run services replace deployment/cloud/cloudrun/dashboard-service.yaml --region "$REGION"
```

### Dashboard mode choice

Cheap default:

- set `MQTT_ENABLED=false`
- dashboard reads Cloud SQL history
- operators refresh or reopen when needed

Live mode:

- set `MQTT_ENABLED=true`
- point `MQTT_HOST` to the VM public IP or DNS
- use Cloud Run minimum instances if you want a warm dashboard instance

For live mode, test cost and behavior before production. Cloud Run service billing can change depending on minimum instances and instance-based billing.

## Step 5. Prepare The Logger + MQTT VM

Use a small Linux VM such as:

- machine type: `e2-micro` or `e2-small`
- OS: Ubuntu LTS

On the VM:

1. install Docker and Docker Compose plugin
2. clone or copy this repo
3. create the logger env file
4. create the Mosquitto password file
5. start the compose stack

Create:

```text
deployment/cloud/env/logger.env
```

from:

```text
deployment/cloud/env/logger.env.example
```

Important values:

- `DATABASE_URL`
- `MQTT_USERNAME`
- `MQTT_PASSWORD`

Create the Mosquitto password file expected by:

```text
deployment/cloud/compute/mosquitto/passwd
```

Example on the VM:

```bash
docker run --rm -it -v "$(pwd)/deployment/cloud/compute/mosquitto:/mosquitto/config" eclipse-mosquitto:2 \
  mosquitto_passwd -c /mosquitto/config/passwd smartassembly
```

Then start the VM-side services:

```bash
docker compose -f deployment/cloud/compute/docker-compose.logger-broker.yml up -d
```

Open only the ports you need in the VM firewall:

- `1883` for MQTT without TLS
- `8883` only if you add TLS later

Restrict the source IPs if possible to your factory/public office IPs.

## Step 6. Configure The Local PC Edge

On the local PC or WSL machine, create:

```text
deployment/cloud/env/edge-hybrid.env
```

from:

```text
deployment/cloud/env/edge-hybrid.env.example
```

Set:

- `MQTT_HOST` to the VM public IP or DNS
- `MQTT_PORT`
- `MQTT_USERNAME`
- `MQTT_PASSWORD`

Then run the edge pipeline only:

WSL / Ubuntu:

```bash
bash scripts/start_hybrid_edge.sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_hybrid_edge.ps1
```

These launchers do not change your current test video path. They only inject cloud MQTT settings before starting `scripts/run_pipeline.py`.

## Final Data Flow

```text
Camera / Raspberry Pi
        |
        v
Local PC Vision Pipeline
        |
        v
Google VM Mosquitto ---> Google VM Logger ---> Cloud SQL
                                      |
                                      v
                              Cloud Run Dashboard
                                      |
                                      v
                              Managers at home
```

## Recommended First Validation

Test in this order:

1. start the VM broker and logger
2. run `python scripts/fetch_db.py count` against Cloud SQL from the VM if needed
3. run the local PC with `start_hybrid_edge`
4. confirm logger prints new inserts
5. open the Cloud Run dashboard URL
6. verify `/api/health`

## Cost Notes

Cheapest practical shape for Option 3:

- Cloud Run dashboard
- Cloud SQL small instance
- one small Compute Engine VM for broker + logger

This is usually cheaper and more stable than pushing the vision stream itself to the cloud.
