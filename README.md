# Epsilon App Store for umbrelOS

Epsilon is a community app store maintained by [GeekIO](https://github.com/geek1o).
It provides separately maintained packages for installing and updating self-hosted
applications through umbrelOS.

The store currently focuses on media management, private photo storage, manga
reading, workflow automation, networking, network booting, backup, identity, certificates, and local developer tools.
Application containers are pinned by digest and normally checked for both
`linux/amd64` and `linux/arm64` support before publication. Architecture-specific
exceptions are identified explicitly in the application description.

## Add the store to Umbrel

1. Open **App Store** on your Umbrel.
2. Open the menu in the upper-right corner and select **Community App Stores**.
3. Click **Add** and enter this repository URL:

   ```text
   https://github.com/geek1o/epsilon-umbrel-app-store
   ```

4. Open the **Epsilon** store and install the application you need.

Community app stores are not reviewed or vetted by the official Umbrel team.
Only install applications and updates after reviewing their permissions and
trusting their upstream developers.

## Applications

| Application | Category | Description | Upstream |
| --- | --- | --- | --- |
| [Aliasarr](epsilon-aliasarr) | Media | Media manager for movies, series, and anime with multilingual titles, download automation, imports, and hardlink support. | [lQwestl/aliasarr](https://github.com/lQwestl/aliasarr) |
| [Anime365 Sidecar](epsilon-anime365-sidecar) | Media | Anime 365 and Emby integration with automated episode downloads, metadata, watch-state sync, and a dedicated configuration panel. | [flaksp/anime365-sidecar](https://github.com/flaksp/anime365-sidecar) |
| [atvloadly](epsilon-atvloadly) | Developer | Web interface for pairing with Apple TV, sideloading IPA files, and refreshing signed applications. | [bitxeno/atvloadly](https://github.com/bitxeno/atvloadly) |
| [Emby](epsilon-emby) | Media | Personal media server for organising and streaming movies, TV shows, music, photos, and home videos. | [MediaBrowser/Emby](https://github.com/MediaBrowser/Emby) |
| [Ente Photos](epsilon-ente-photos) | Files | End-to-end encrypted photo and video backup with self-hosted web apps, API, database, and object storage. | [ente/ente](https://github.com/ente/ente) |
| [netboot.xyz](epsilon-netbootxyz) | Networking | Menu-based network boot environment for booting OS installers and live images over the network via iPXE, with a web menu editor and TFTP/HTTP menu hosting. | [netbootxyz/docker-netbootxyz](https://github.com/netbootxyz/docker-netbootxyz) |
| [n8n](epsilon-n8n) | Automation | Epsilon-maintained n8n alternative with the official external task runner, n8n Assistant sandbox service, privileged sandbox runner, and bundled SearXNG JSON web search. Uses a separate `epsilon-n8n` app/data directory; back up existing official n8n data before migrating. | [n8n-io/n8n](https://github.com/n8n-io/n8n) |
| [n8n Assistant Sandbox](epsilon-n8n-assistant) | Automation | Companion sandbox provider for the Epsilon n8n package, with the official n8n sandbox service and bundled SearXNG web search. For users who keep the official n8n app; the integrated `epsilon-n8n` package is recommended for new installs. | [n8n-io/n8n-sandbox-service](https://github.com/n8n-io/n8n-sandbox-service) |
| [Newt](epsilon-newt) | Networking | Userspace WireGuard connector with Pangolin discovery for containers on the shared Umbrel network. | [fosrl/newt](https://github.com/fosrl/newt) |
| [Zerobyte](epsilon-zerobyte) | Files | Encrypted restic backup automation with schedules, retention, notifications, and mirror sync for local and remote volumes. | [nicotsx/zerobyte](https://github.com/nicotsx/zerobyte) |
| [Pocket ID](epsilon-pocket-id) | Networking | Passkey-only OpenID Connect provider with a local trusted-HTTPS setup powered by Caddy. | [pocket-id/pocket-id](https://github.com/pocket-id/pocket-id) |
| [Suwayomi](epsilon-suwayomi) | Media | Browser-based manga server and reader compatible with Mihon/Tachiyomi extensions. | [Suwayomi/Suwayomi-Server](https://github.com/Suwayomi/Suwayomi-Server) |
| [Hermes WebUI](epsilon-hermes-webui) | AI | Browser interface for Hermes Agent with streaming chat, sessions, workspace browsing, and tasks; connects to the official Hermes Agent app data. | [nesquena/hermes-webui](https://github.com/nesquena/hermes-webui) |

Some applications need extra first-run steps or access to shared Umbrel storage.
Read the full description in the App Store before installation. Ente Photos also
includes a dedicated [setup and backup guide](epsilon-ente-photos/README.md).

## Updates and compatibility

- Packages follow upstream releases when suitable multi-architecture container
  images are available.
- Container images are pinned to immutable SHA-256 digests to prevent an upstream
  tag from silently changing an installed package.
- Manifests and container architectures are checked with the Umbrel application
  linter before changes are merged.
- Persistent application data is stored below the app's Umbrel data directory.
  Removing an app may remove that data, so keep independent backups.

An upstream release may introduce migrations or other breaking changes. Check the
application's release notes and backup important data before updating.

## Support and contributions

Use this repository's [issues](https://github.com/geek1o/epsilon-umbrel-app-store/issues) for problems
with installation, container wiring, storage paths, ports, icons, or App Store
metadata. Report bugs in the application itself to the corresponding upstream
project linked in the table above.

Pull requests for new applications and package updates are welcome. A package
should use pinned multi-architecture images, persistent storage, unique ports,
accurate setup instructions, and working icon and gallery links.

## Disclaimer

Epsilon is an independent community project and is not affiliated with Umbrel or
the upstream application developers. Product names and trademarks belong to their
respective owners.
