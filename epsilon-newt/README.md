# Newt on Umbrel

This package runs the official [Newt](https://github.com/fosrl/newt) container
unchanged and adds a separate local panel for configuration and tunnel status.
Newt is a connector for Pangolin; it is not a standalone VPN server.

## Connect to Pangolin

1. In Pangolin, create a site and choose Newt as the connection method.
2. Copy the Pangolin endpoint, Newt ID, and Newt secret.
3. Open Newt in Umbrel and paste those three values into the panel.
4. Save the configuration and restart Newt from the Umbrel app menu.
5. Wait for the panel to report that the tunnel is connected.

Newt reads its JSON configuration when the process starts, so every saved
change requires an app restart. The secret is stored with mode `0600` and is
not returned to the browser after saving.

## Publish Umbrel services

Open the site's resource editor in Pangolin and use Docker discovery to select
an Umbrel container. Newt reports only containers that share its Umbrel network,
so the listed container names and private ports are reachable from Newt. In most
cases, select an app's `app_proxy` container and its HTTP port; this preserves
the app's normal proxy routing instead of exposing a database or other internal
service directly.

Containers on isolated application-only networks are intentionally omitted.
For services published on the Umbrel host, you can still enter the Umbrel host
name and published port manually. `127.0.0.1` refers to the Newt container, not
to the Umbrel host.

Newt does not receive the Docker socket directly. A separate socket proxy gives
it read-only access to the container list, container metadata, and Docker event
stream. Mutating requests, exec, logs, process lists, archives, and filesystem
exports are denied. The proxy has no network interface and exposes its filtered
API only through a private Unix socket mounted into Newt. It is not reachable
from other Umbrel applications or the LAN and does not appear as a publishable
container in Pangolin. Container metadata can still contain sensitive operational
information, so enable only resources that you intend to publish through Pangolin.

Newt does not use host networking, privileged mode, or additional Linux
capabilities. It creates its WireGuard tunnel in userspace.

## Backups and removal

Back up `data/config/config.json` if you want to preserve the site credentials.
Removing the app deletes the local credentials and disconnects the site, but it
does not remove the corresponding site or resources from Pangolin.
