# Epsilon App Store for umbrelOS

Epsilon is a community app store maintained by [GeekIO](https://github.com/geek1o).
It provides separately maintained packages for installing and updating self-hosted
applications through umbrelOS.

The store currently focuses on media management, private photo storage, manga
reading, and local developer tools. Application containers are pinned by digest
and checked for both `linux/amd64` and `linux/arm64` support before publication.

## Add the store to Umbrel

1. Open **App Store** on your Umbrel.
2. Open the menu in the upper-right corner and select **Community App Stores**.
3. Click **Add** and enter this repository URL:

   ```text
   https://github.com/geek1o/umbrel
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
| [Suwayomi](epsilon-suwayomi) | Media | Browser-based manga server and reader compatible with Mihon/Tachiyomi extensions. | [Suwayomi/Suwayomi-Server](https://github.com/Suwayomi/Suwayomi-Server) |
| [Uchiyomi](epsilon-uchiyomi) | Media | Self-hosted manga and manhwa library with downloads, automatic chapter updates, OPDS, and multi-user progress. | [AngeloSha/uchiyomi](https://github.com/AngeloSha/uchiyomi) |

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

Use this repository's [issues](https://github.com/geek1o/umbrel/issues) for problems
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
