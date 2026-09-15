# Anime365 Sidecar on Umbrel

This package runs the official
[Anime365 Sidecar](https://github.com/flaksp/anime365-sidecar) image unchanged
and adds a separate, lightweight web container for configuration and status.
The two containers share only the generated `.env` file and the Anime365 media
directory.

## Requirements

- An Anime 365 account with an active premium subscription.
- [Emby](../epsilon-emby) installed and configured on the same Umbrel.
- Enough free storage for the episodes selected for download.

Anime365 Sidecar supports one Anime 365 account per installation.

## Configure Emby

1. In Emby, create a library with content type **TV Shows**.
2. Add `/downloads/anime365` as its media folder.
3. In the library settings, disable metadata providers that could overwrite the
   sidecar metadata. Keep real-time monitoring and Image Capture enabled.
4. Create an API key under **Settings > Advanced > API Keys**.
5. Copy the library ID from the `parentId` value in the library page URL.
6. Copy your user ID from the user settings page URL.

The default internal Emby endpoint in the panel targets the `epsilon-emby`
package. Change it only if you use another Emby installation.

## Configure Anime365 Sidecar

Open Anime365 Sidecar from Umbrel and complete the required fields. The panel
can check whether the Anime 365 site is reachable and whether the Emby endpoint
accepts the supplied API key. The Anime 365 login itself is checked by the
sidecar when it starts.

After saving, restart Anime365 Sidecar from its Umbrel app menu. The official
sidecar reads `.env` only at process startup, so a restart is required after
every configuration change.

The status cards show whether configuration is complete and summarize the
titles, episodes, and translations recorded in `manifest.json`. The upstream
sidecar has no health endpoint, so its actual process state and logs remain in
the Umbrel app controls.

## Data and backups

- Configuration and secrets: the app's `data/config/.env` file.
- Downloaded media and `manifest.json`: Umbrel shared storage under
  `downloads/anime365`.

The panel writes the configuration atomically with mode `0600` and does not
return saved secrets to the browser. Back up both locations together. Avoid
manually renaming or moving downloaded files because the sidecar relies on its
directory layout and manifest.

## Architecture and security

The web panel does not have access to the Docker socket and cannot control the
sidecar container. It writes configuration through a shared volume; the
official sidecar mounts that volume read-only and runs as user `1000:1000`.
Umbrel's app proxy protects the panel with the Umbrel account.

This is an independent community package and is not affiliated with Anime 365,
Emby, Umbrel, or the upstream developer.
