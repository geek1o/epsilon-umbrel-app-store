# Anime365 Sidecar on Umbrel

This package runs the official [Anime365 Sidecar 0.15.0](https://github.com/flaksp/anime365-sidecar/releases/tag/0.15.0) container unchanged and adds a separate Python web panel for configuration and library statistics. The image is pinned by its multi-platform digest in `docker-compose.yml`.

## Requirements

- An Anime 365 account with an active premium subscription.
- Emby or Jellyfin reachable from the sidecar container. Jellyfin support is experimental.
- Enough storage for the selected episodes and memory for the package's temporary download directory (tmpfs).

The panel defaults to the internal address of [Epsilon Emby](../epsilon-emby). Install your chosen media server separately; the package has no mandatory Emby dependency. One installation supports one Anime 365 account and one media server.

## Configure the media server

1. Share Umbrel's `downloads/anime365` directory with the media server. Epsilon Emby already sees it as `/downloads/anime365`. An external Jellyfin or Emby installation needs a mount of that same directory.
2. Create a **TV Shows** library pointing to the shared directory. Jellyfin requires exactly one path in that library.
3. Enable real-time monitoring. Follow the upstream [Emby](https://github.com/flaksp/anime365-sidecar/wiki/Emby) or [Jellyfin](https://github.com/flaksp/anime365-sidecar/wiki/Jellyfin) instructions for metadata providers and Image Capture.
4. Create an API key in the server's administrator panel. Copy the library ID and user ID from the corresponding page URLs. Jellyfin IDs must be nonzero UUIDs, with or without hyphens.

Switching an existing library between Emby and Jellyfin is unsupported. They use different manifests (`manifest.json` and `manifest-jellyfin.json`); the panel rejects saving settings for the other server when its manifest is present. To use a different server, prepare a separate library directory and change the shared volume mappings. The panel never deletes or migrates library files.

## Configure Anime365 Sidecar

Open the app from Umbrel. The panel groups the settings into five sections:

- **Подключение**: Anime 365 credentials, server selection, internal API address, API key, library and user IDs, and the address for Telegram links. Only the selected server's variables are written to `.env`; upstream rejects mixed Emby/Jellyfin settings.
- **Загрузка**: Anime 365 lists or title IDs, translation languages and types, preferred and excluded authors, download-ahead limit, and scan interval.
- **Очистка**: keep all episodes (default), remove watched episodes, or remove completed/dropped shows and shows outside all Anime 365 lists. The delay defaults to `336h` and counts from the latest playback reported by the media server, not from download time. If no playback time is reported, the delay does not apply. Removing unavailable translations is independent of this policy and delay. Saving changes does not delete files; cleanup runs in the sidecar after restart.
- **Уведомления**: Telegram Bot API credentials. The public media server address is set in **Подключение**.
- **Дополнительно**: metadata and catalog refresh intervals, Shikimori and anime mapping database URLs, download timeouts, log level, proxy settings, and the fixed container paths.

All variables from the upstream [environment reference](https://github.com/flaksp/anime365-sidecar/wiki/Переменные-окружения) are represented. The library and temporary directories are shown read-only because their mounts are part of the Umbrel package (`/library` and `/tmp/anime365-sidecar`). Changing them requires editing Docker Compose, not only `.env`.

Intervals use Go duration syntax, such as `30s`, `5m`, `1h30m`, or `336h`; use hours instead of days. `HTTP_PROXY`, `HTTPS_PROXY`, and `NO_PROXY` apply to standard Go HTTP clients, but the multi-threaded video downloader does not use them.

Connection checks use the current form values and reuse saved secrets when their fields are empty. The Anime 365 check tests website reachability; the sidecar verifies the login when it starts. The Emby/Jellyfin check tests API access, not library permissions or path mappings.

After saving, restart the app from its Umbrel menu. The official sidecar reads `.env` only at startup. The status section summarizes the selected server's manifest and configuration; the actual process state and logs are available in Umbrel.

## Saved secrets and backups

Secrets are never returned to the browser after saving. Leave a secret field empty to keep its saved value, or type a replacement. Use **Удалить сохранённое значение** to disable saved Telegram or proxy settings. Required passwords and API keys can be replaced but cannot be cleared while still required.

Back up the app's `data/config/.env` and Umbrel's shared `downloads/anime365` directory together. The panel writes the configuration atomically with mode `0600` and preserves unknown environment variables. Do not manually rename library files or edit manifests.

The web panel has no Docker socket access and cannot control the sidecar container. The official container mounts configuration read-only, and both containers run as `1000:1000`. Umbrel's app proxy protects the panel with the Umbrel account.

## Development checks

The panel uses the Python standard library and static HTML/CSS/JavaScript, without a frontend build step.

```sh
python3 -m unittest discover -s epsilon-anime365-sidecar/web/tests -v
node --check epsilon-anime365-sidecar/web/static/app.js
```

This independent community package is not affiliated with Anime 365, Emby, Jellyfin, Umbrel, or the upstream developer.
