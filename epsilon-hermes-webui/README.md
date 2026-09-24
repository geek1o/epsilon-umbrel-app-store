# Hermes WebUI (Epsilon package)

Browser interface for [Hermes Agent](https://github.com/NousResearch/hermes-agent)
running on umbrelOS, packaged from the upstream
[nesquena/hermes-webui](https://github.com/nesquena/hermes-webui) project.

## How it works

- Installs with a dependency on the official **Hermes Agent** app (`hermes-agent`).
- Mounts the same persistent Hermes home (`app-data/hermes-agent/data/hermes`)
  that the Hermes Agent app uses, so the WebUI shares configuration, provider
  keys, sessions, memory, and skills with it. No extra model setup.
- The WebUI runs the agent in-process for chat. Messaging integrations
  (Telegram etc.) and gateway-delivered cron jobs keep running in the Hermes
  Agent app; tasks are visible and manually runnable in the WebUI.
- Authentication is handled by the umbrelOS app proxy, so no separate WebUI
  password is configured. Do not expose the app port outside umbrelOS.

## Notes

- The container image is pinned by digest: `ghcr.io/nesquena/hermes-webui:0.52.113`
  (multi-arch: linux/amd64 and linux/arm64).
- `HERMES_SKIP_CHMOD=1` is set so the WebUI never rewrites permissions inside
  the Hermes home owned by the Hermes Agent app.
- On update of the Hermes Agent app, both apps share one data directory —
  backing up `app-data/hermes-agent/data/hermes` covers both.
