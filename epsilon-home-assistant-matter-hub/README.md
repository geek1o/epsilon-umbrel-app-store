# Home Assistant Matter Hub for Umbrel

[Home Assistant Matter Hub](https://riddix.github.io/home-assistant-matter-hub)
exposes selected Home Assistant devices to Matter controllers such as Apple Home,
Google Home, Alexa, Aqara Home, and SmartThings.

## Required initial configuration

The upstream application requires a Home Assistant Long-Lived Access Token. It is
not stored in this package or in Git.

1. In Home Assistant, open your user profile and create a **Long-Lived Access
   Token**.
2. In Umbrel, open **Home Assistant Matter Hub → Settings → Environment**.
3. Add `HAMH_HOME_ASSISTANT_ACCESS_TOKEN` with that token, then start or restart
   the app.
4. If Home Assistant is on another machine, also set
   `HAMH_HOME_ASSISTANT_URL`, for example `http://homeassistant.local:8123`.
   The built-in default is `http://umbrel.local:8123`.
5. Open the app at `http://umbrel.local:8482`, create a bridge, choose entities,
   and commission it with your controller.

Matter requires working IPv6 and mDNS on the local network. For VLAN setups,
ensure multicast and local IPv6/ULA connectivity are available between the
controller and Umbrel.

## Data and updates

Bridge configuration, Matter fabrics, certificates, and backups are persisted in
this application's Umbrel data directory. Back up that data before major upgrades
or before factory-resetting a bridge. Package issues belong in this repository;
upstream issues belong at
[RiDDiX/home-assistant-matter-hub](https://github.com/RiDDiX/home-assistant-matter-hub/issues).
