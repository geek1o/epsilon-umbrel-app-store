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

## Agent source requirement (run_agent)

The WebUI runs the agent **in-process**: at startup its init looks for the
Hermes Agent source inside its own container at
`$HERMES_HOME/hermes-agent` (i.e. `/home/hermeswebui/.hermes/hermes-agent`)
or `/opt/hermes`. The official Hermes Agent app ships its source at
`/opt/hermes` inside *its* container — it is NOT part of the shared home.
Without an agent source in the shared home, the WebUI starts but reports
`Missing imports: run_agent` and runs with reduced functionality.

Fix applied: the Hermes Agent source (tag `v2026.9.14`, the exact commit the
official app image runs — build sha `345cd2b057a452236de401d3534b8502a7465e8d`)
is cloned into the shared home at `data/hermes/hermes-agent`. On first start
after that, the WebUI's init stages it into `/app/hermes-agent-src`, installs
the agent's Python deps into `/app/venv` via uv, and the in-process agent
works. If the WebUI was already running before the source appeared, recreate
its container (umbrelOS: Restart the app; if that is not enough, update or
reinstall the WebUI app) so the dependency-install guard `/app/venv/.deps_installed`
is re-evaluated.

**Maintenance:** when the official Hermes Agent app updates (new image,
new `/opt/hermes` version), re-sync the clone in the shared home:

```bash
cd /path/to/app-data/hermes-agent/data/hermes/hermes-agent
git fetch --tags && git checkout <new-tag>   # tag matching the agent app image
```

Version of the clone and the agent app image should stay in sync — the WebUI
shares the same session state DB with the official agent.
