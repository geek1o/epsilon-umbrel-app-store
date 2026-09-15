#!/bin/sh
set -eu

until mc alias set ente http://minio:3200 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null 2>&1; do
  echo "Waiting for MinIO..."
  sleep 1
done

for bucket in b2-eu-cen wasabi-eu-central-2-v3 scw-eu-fr-v3; do
  mc mb --ignore-existing "ente/$bucket"
done
