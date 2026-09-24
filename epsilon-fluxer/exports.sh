# Fluxer requires long-lived secrets and a valid P-256 VAPID key pair.
export POSTGRES_PASSWORD="$(derive_entropy "${app_entropy_identifier}-postgres-password" | openssl dgst -sha256 -hex | cut -d' ' -f2)"
export MEILI_MASTER_KEY="$(derive_entropy "${app_entropy_identifier}-meili-master-key" | openssl dgst -sha256 -hex | cut -d' ' -f2)"
export FLUXER_S3_ACCESS_KEY="fluxer"
export FLUXER_S3_SECRET_KEY="$(derive_entropy "${app_entropy_identifier}-s3-secret" | openssl dgst -sha256 -hex | cut -d' ' -f2)"
export LIVEKIT_API_KEY="fluxer"
export LIVEKIT_API_SECRET="$(derive_entropy "${app_entropy_identifier}-livekit-secret" | openssl dgst -sha256 -hex | cut -d' ' -f2)"

export FLUXER_SUDO_MODE_SECRET="$(derive_entropy "${app_entropy_identifier}-sudo-mode" | openssl dgst -sha256 -hex | cut -d' ' -f2)"
export FLUXER_CONNECTION_INITIATION_SECRET="$(derive_entropy "${app_entropy_identifier}-connection-initiation" | openssl dgst -sha256 -hex | cut -d' ' -f2)"
export FLUXER_GATEWAY_RPC_AUTH_TOKEN="$(derive_entropy "${app_entropy_identifier}-gateway-rpc" | openssl dgst -sha256 -hex | cut -d' ' -f2)"
export FLUXER_MEDIA_PROXY_SECRET_KEY="$(derive_entropy "${app_entropy_identifier}-media-proxy" | openssl dgst -sha256 -hex | cut -d' ' -f2)"
export FLUXER_MEDIA_PROXY_UPLOAD_RELAY_SECRET_BASE64="$(derive_entropy "${app_entropy_identifier}-media-relay" | openssl dgst -sha256 -binary | base64 | tr -d '\n')"
export FLUXER_ADMIN_SECRET_KEY_BASE="$(derive_entropy "${app_entropy_identifier}-admin-secret" | openssl dgst -sha256 -hex | cut -d' ' -f2)"
export FLUXER_ADMIN_OAUTH_CLIENT_SECRET="$(derive_entropy "${app_entropy_identifier}-admin-oauth" | openssl dgst -sha256 -hex | cut -d' ' -f2)"

# Build a deterministic SEC1 P-256 private key, then derive the uncompressed
# public point in the format expected by Web Push VAPID.
vapid_scalar="$(derive_entropy "${app_entropy_identifier}-vapid" | openssl dgst -sha256 -binary | od -An -tx1 | tr -d ' \n')"
vapid_der="$(printf '30310201010420%sA00A06082A8648CE3D030107' "$vapid_scalar")"
vapid_file="${TMPDIR:-/tmp}/fluxer-vapid.$$"
trap 'rm -f "$vapid_file" "$vapid_file.pub"' EXIT
printf '%s' "$vapid_der" | perl -e 'local $/; print pack("H*", <STDIN>)' >"$vapid_file"
vapid_public="$(openssl ec -inform DER -in "$vapid_file" -pubout -outform DER 2>/dev/null | tail -c 65 | openssl base64 -A | tr '+/' '-_' | tr -d '=')"
export FLUXER_VAPID_PRIVATE_KEY="$(printf '%s' "$vapid_scalar" | perl -e 'local $/; print pack("H*", <STDIN>)' | openssl base64 -A | tr '+/' '-_' | tr -d '=')"
export FLUXER_VAPID_PUBLIC_KEY="$vapid_public"

export FLUXER_VAPID_EMAIL="admin@${DEVICE_DOMAIN_NAME}"
export FLUXER_DOMAIN="${DEVICE_DOMAIN_NAME}"
export FLUXER_PUBLIC_ORIGIN="https://${DEVICE_DOMAIN_NAME}:$(printf '%s' "${APP_PORT:-8080}")"
export FLUXER_EDGE_SITE_ADDRESS=":8080"
export FLUXER_LIVEKIT_TCP_PORT="37881"
export FLUXER_LIVEKIT_UDP_PORT="37882"
