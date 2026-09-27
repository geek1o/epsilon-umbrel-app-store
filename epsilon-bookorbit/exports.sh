# Stable, independent credentials derived from Umbrel's per-device app seed.
export APP_BOOKORBIT_DB_PASSWORD="$(derive_entropy "${app_entropy_identifier}-db-password")"
export APP_BOOKORBIT_JWT_SECRET="$(derive_entropy "${app_entropy_identifier}-jwt-secret")"
export APP_BOOKORBIT_PODCAST_ENCRYPTION_KEY="$(derive_entropy "${app_entropy_identifier}-podcast-encryption-key")"
export APP_BOOKORBIT_EMAIL_ENCRYPTION_KEY="$(derive_entropy "${app_entropy_identifier}-email-encryption-key")"
export APP_BOOKORBIT_MIGRATION_ENCRYPTION_KEY="$(derive_entropy "${app_entropy_identifier}-migration-encryption-key")"
export APP_BOOKORBIT_REQUEST_ENCRYPTION_KEY="$(derive_entropy "${app_entropy_identifier}-request-encryption-key")"
