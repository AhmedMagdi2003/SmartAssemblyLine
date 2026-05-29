#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID first}"
REGION="${REGION:-us-central1}"
REPOSITORY="${REPOSITORY:-smart-assembly}"

cd "$PROJECT_ROOT"

echo "Using project: $PROJECT_ID"
echo "Using region: $REGION"
echo "Using Artifact Registry repository: $REPOSITORY"

gcloud config set project "$PROJECT_ID"

for image_name in dashboard logger migrate; do
  gcloud builds submit \
    --tag "$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$image_name:latest" \
    -f "deployment/cloud/Dockerfile.$image_name" \
    .
done

echo "Apply dashboard service YAML after replacing placeholders:"
echo "  deployment/cloud/cloudrun/dashboard-service.yaml"
echo "Apply migration job YAML after replacing placeholders:"
echo "  deployment/cloud/cloudrun/migrate-job.yaml"
echo
echo "Suggested next commands:"
echo "  gcloud run jobs replace deployment/cloud/cloudrun/migrate-job.yaml --region $REGION"
echo "  gcloud run jobs execute smart-assembly-migrate --region $REGION"
echo "  gcloud run services replace deployment/cloud/cloudrun/dashboard-service.yaml --region $REGION"
echo
echo "Logger + MQTT broker are intended for the Option 3 Google Compute Engine VM."
echo "Use this file on the VM after replacing placeholders:"
echo "  deployment/cloud/compute/docker-compose.logger-broker.yml"
