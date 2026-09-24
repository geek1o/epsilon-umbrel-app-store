# Fluxer for Umbrel

This package adapts Fluxer's upstream self-hosting stack for the Umbrel app
proxy. Caddy serves Fluxer internally on port `8080`; Umbrel terminates HTTPS
and routes the web application through `app_proxy`.

## Networking

- Web, API, media, and LiveKit signalling: the Umbrel app proxy.
- LiveKit media: TCP `37881` and UDP `37882`.
- `FLUXER_DOMAIN` and `FLUXER_PUBLIC_ORIGIN` are generated from the device
  domain so passkeys and browser push use the address users open in Umbrel.

## Persistence

All stateful services use `${APP_DATA_DIR}/data`. The generated credentials in
`exports.sh` are deterministic for the app installation and must be preserved
with the app data during backups and migrations.

## Upstream

The service layout follows `fluxerapp/fluxer` self-hosting files at commit
`dcd5f09d6aa30c96e2dbfc250d868103a861ca98`. Container images are pinned by
digest in `docker-compose.yml`.
