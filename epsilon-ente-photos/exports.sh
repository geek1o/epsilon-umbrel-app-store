# Stable, unique credentials derived from Umbrel's per-device application seed.
export APP_ENTE_DB_PASSWORD="$(derive_entropy "${app_entropy_identifier}-db-password" | head -c32)"
export APP_ENTE_MINIO_PASSWORD="$(derive_entropy "${app_entropy_identifier}-minio-password" | head -c32)"

# Ente expects 32-byte encryption/JWT keys and a 64-byte hash key, encoded as
# standard Base64 (URL-safe Base64 for JWT). These values must remain stable.
export APP_ENTE_KEY_ENCRYPTION="$(derive_entropy "${app_entropy_identifier}-key-encryption" | openssl dgst -sha256 -binary | base64 | tr -d '\n')"
export APP_ENTE_KEY_HASH="$(derive_entropy "${app_entropy_identifier}-key-hash" | openssl dgst -sha512 -binary | base64 | tr -d '\n')"
export APP_ENTE_JWT_SECRET="$(derive_entropy "${app_entropy_identifier}-jwt-secret" | openssl dgst -sha256 -binary | base64 | tr '+/' '-_' | tr -d '\n')"
