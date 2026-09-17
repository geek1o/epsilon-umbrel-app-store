# netboot.xyz (Epsilon package)

This package ships the official [netboot.xyz container](https://github.com/netbootxyz/docker-netbootxyz)
unchanged, pinned to a digest. netboot.xyz is a menu-based network boot
environment built on iPXE that lets you boot operating system installers and
live environments for many Linux distributions, BSD, and utility images.

## What this package adds

- The netboot.xyz web configuration interface is proxied through the Umbrel UI
  (port 3000 inside the app network).
- TFTP is published on the host at UDP port 69.
- The iPXE menu files are also served over HTTP on host port 8080
  (`NGINX_PORT`), for clients that fetch menus over HTTP.
- Menus persist in the app data directory (`/config`); mirrored assets go to
  `/assets`.

## Booting a machine

netboot.xyz does **not** include a DHCP server. Configure your existing DHCP
server or router:

- `tftp-server` / `next-server`: the IP address of your Umbrel device
- `boot-file-name`:
  - `netboot.xyz.kpxe` for legacy BIOS clients
  - `netboot.xyz.efi` for UEFI clients

After the first start, open the app UI and let it download the menu release,
then boot a client on the same network and it should reach the netboot.xyz
menu. See the upstream [TFTP booting guide](https://netboot.xyz/docs/booting/tftp/)
for DHCP server examples (dnsmasq, pfSense, OPNsense, and others).

## Notes

- TFTP requires the UDP port to be reachable on the Umbrel host; no other
  container is modified, and the app does not use host networking.
- Removing the app removes the downloaded menus and mirrored assets, so keep
  independent backups of `/config` if you customized it.