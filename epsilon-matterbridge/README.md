# Matterbridge for Umbrel

[Matterbridge](https://matterbridge.io) is a self-hosted Matter bridge and plugin
manager. It exposes supported devices and plugins to Matter controllers while
running locally on your Umbrel.

## First run

1. Open Matterbridge from the Umbrel App Store.
2. Use the web interface to install and configure the plugins you need.
3. Commission the bridge with your Matter controller using the pairing details
   shown by Matterbridge.

Matterbridge uses host networking so that Matter and mDNS discovery work on your
local network. Its plugins, configuration, certificates, and Matter data are
stored persistently in this application's Umbrel data directory.

## Updates and support

The container image is pinned to the upstream Matterbridge 3.10.11 release. Back
up the app data before major Matterbridge upgrades. Report package issues in this
repository; report Matterbridge bugs upstream at
[github.com/Luligu/matterbridge](https://github.com/Luligu/matterbridge/issues).
