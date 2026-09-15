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

Configure resources and access policies in Pangolin. From the Newt container,
use an address that is reachable over the local network, such as the Umbrel
host name and the service's published port. `127.0.0.1` refers to the Newt
container itself, not to the Umbrel host.

Newt does not receive the Docker socket, host networking, privileged mode, or
additional Linux capabilities. It creates its WireGuard tunnel in userspace.

## Backups and removal

Back up `data/config/config.json` if you want to preserve the site credentials.
Removing the app deletes the local credentials and disconnects the site, but it
does not remove the corresponding site or resources from Pangolin.
