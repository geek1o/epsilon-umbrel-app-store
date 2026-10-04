# JellyPlex-Watched on Umbrel

This package runs the official stable
[JellyPlex-Watched 8.5.3](https://github.com/luigi311/JellyPlex-Watched/releases/tag/v8.5.3)
container and adds a Russian-language configuration panel. The upstream
synchronization code and its installed dependencies are not modified.

## First run

1. Install JellyPlex-Watched from Epsilon and open it from Umbrel (port **8370**).
2. Add at least two Plex, Jellyfin, or Emby servers, with their addresses and tokens.
   Multiple servers of each type are supported.
3. Test each connection. Jellyfin and Emby require an administrator API key from
   the dashboard; Plex requires an administrator
   [X-Plex-Token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/).
4. Select sync directions. A row pushes to a column. A direction applies to all
   configured servers of those types, following upstream 8.5.3 behavior.
5. Add user/library name mappings or filters if needed, and save.
6. Leave **Проверка без изменений** enabled and click **Запустить сейчас**.
   Inspect **Журнал** for proposed updates and matching errors.
7. When satisfied, disable dry-run. Enable **Автоматические запуски** to run on
   a schedule (one hour by default), or keep it disabled for manual runs only.

Neither scheduled nor manual runs start before at least two servers and an
applicable sync direction are configured. Saving with the schedule enabled
starts the first run when the worker is idle. Later scheduled runs start one
interval after the previous run finishes. There are no overlapping runs.
Disabling the schedule does not interrupt an active run; it prevents subsequent
scheduled runs. Saving changes during a run applies them to the next run.

## Addresses

Use addresses reachable from the app's Docker network. `localhost` points to
JellyPlex-Watched itself, not another media server.

- Epsilon Emby on the same Umbrel: `http://epsilon-emby_server_1:8096/emby`.
- Epsilon Emby through the Umbrel host: `http://<umbrel-host>:8098`.
- Plex usually exposes `32400`; Jellyfin usually exposes `8096`. Set the actual
  reachable host and port for your installation.

No hard dependency on an Emby, Plex, or Jellyfin Umbrel app is declared: servers
may run elsewhere, and any pair of supported types may be used.

## Configuration and matching

The stable image is pinned to 8.5.3 and its multi-platform digest. It uses legacy
upstream environment variables. The YAML/`JPW_` settings described on upstream
`main` belong to newer development code and must not be used with this image.
The panel translates its JSON configuration into the release's actual variables:
server lists and matching tokens stay in the same order, maps become JSON
objects, filters become comma-separated values, and all nine type-to-type
sync switches are set explicitly.

Plex token authentication is supported; Plex username/password authentication
is not exposed by this panel. Mappings are global, symmetric pairs of names,
following upstream 8.5.3; each name can occur in only one pair. At least one
matching method (provider IDs or filenames) must remain enabled. Different
metadata or filename conventions can cause missing matches. Empty allowlists
mean all names; denylist/allowlist precedence is handled by upstream.

Connection checks read an authenticated API endpoint without modifying data.
They verify token access and a valid API response, but do not guarantee that all
users or media entries will match. HTTP redirects are rejected to avoid sending
tokens to another host. TLS certificate verification is on; the optional bypass
skips hostname matching only for Plex, as in the upstream release. Certificate
trust is still verified; self-signed untrusted certificates are not accepted.

## Runtime and security

The official entrypoint starts the panel as UID/GID `1000:1000`. The panel's
scheduler runs the official `/app/main.py` in a child process, with
`RUN_ONLY_ONCE=True` and the saved settings. No Docker socket, media volume, or custom container image is needed. Plex
account/user discovery uses the upstream PlexAPI and can contact `plex.tv`. Umbrel's authenticated app
proxy is the only published UI entry point.

The container root filesystem and packaged UI are read-only. All Linux capabilities
are dropped and `no-new-privileges` prevents gaining privileges through executables. Persistent state
is under the app's `data` directory; transient raw upstream logs are under
`/tmp` and are removed after each run. API writes require JSON and a custom
header; no cross-origin API access is enabled. Saved tokens are never returned
through the state API. An empty token input retains the saved token for that
server ID and type. Remove the server to remove its stored token.

Output is redacted before it is persisted or displayed. Known API tokens and
common token query parameters are masked. Logs can still contain media titles,
usernames, library names, and server addresses. Only one run executes at a time;
upstream ERROR/CRITICAL records count as a failed run even if its exception
handler exits with status 0. Health checks cover the panel and scheduler;
connection/sync failures remain visible as application status and logs.

## Backups

- `data/config/config.json`: settings and plaintext API tokens, mode `0600`.
- `data/config/status.json`: last run result and timestamps.
- `data/logs/sync.log`: recent redacted history; rotates at about 512 KiB and
  retains one previous file.

Back up the app data directory privately. The panel and worker use restrictive
permissions, but tokens are not encrypted at rest. Uninstalling the app may
remove its data. Media and playback state live on the configured media servers.

## Validation

Run `python3 -m unittest discover -s web/tests -v` from this app directory.
Tests cover secret preservation/redaction, validation, upstream environment
translation, connection checks, HTTP API protection, and the worker lifecycle.
Optional integration tests use the unmodified stable upstream source and fake
Jellyfin/Emby HTTP servers. Set `JPW_TEST_UPSTREAM` to a checked-out `v8.5.3`
source directory and run the tests with its installed Python environment.
They verify dry-run, watched-state and partial-progress writes, disabled
directions, and same-type syncing. Test a dry-run with your actual media
servers after installation.

This is an independent community package; it is not affiliated with Umbrel,
Plex, Jellyfin, Emby, or the upstream developer. The panel code is licensed
under GPL-3.0-or-later; see `LICENSE`. The upstream image retains its own
GPL-3.0 license and source link above.
