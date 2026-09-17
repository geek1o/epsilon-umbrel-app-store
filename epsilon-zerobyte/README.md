# Zerobyte (Epsilon package)

This package ships the official [Zerobyte container](https://github.com/nicotsx/zerobyte)
pinned to a digest. Zerobyte is backup automation for self-hosters, built on
top of restic: encrypted snapshots, schedules, retention policies, health
checks, notifications, and mirror sync to secondary repositories.

## What this package changes

- The web UI (port 4096) is proxied through the Umbrel UI and served at
  `https://umbrel.local:4096`. `BASE_URL` and `TRUSTED_ORIGINS` are preset to
  that origin so that authentication (passkey/admin signup) passes origin
  validation. If you rename your Umbrel device, update these two values in
  the app's compose configuration accordingly.
- Remote mount support (NFS, SMB, WebDAV, SFTP) is enabled, which requires the
  `SYS_ADMIN` Linux capability and the host `/dev/fuse` device. These are used
  only to mount configured network shares inside the container. See the
  upstream [Mounted Shares and Permissions guide](https://zerobyte.app/docs/guides/mounted-shares-and-acls)
  before backing up metadata-sensitive data from mounted shares.
- An application secret is generated once on first start by a small init
  container and stored at `${APP_DATA_DIR}/data/secrets/app_secret`. It
  encrypts sensitive data in the Zerobyte database — keep an independent
  backup of this file. Losing it makes encrypted database contents
  unrecoverable.
- Data lives in `${APP_DATA_DIR}/data` (mounted at `/data` inside the
  container). Removing the app removes that data, including repositories
  metadata and local backups — keep separate backups of anything critical.

## Notes

- Zerobyte is intended to run on a trusted network. Do not expose it directly
  to the internet.
- Backups are restic repositories; they can be accessed with any restic client
  (`restic` binary) if needed, since Zerobyte stores standard restic repos.
