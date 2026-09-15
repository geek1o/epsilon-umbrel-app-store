# Ente Photos on Umbrel

This package runs the official Ente Photos self-hosted stack with PostgreSQL and
MinIO. Ente encrypts photos and videos on the client before they are uploaded.

## First account

Open Ente Photos from Umbrel and create an account. SMTP is not configured by
default, so Museum writes the one-time verification code to its container log.
On the Umbrel host, retrieve the newest code with:

```sh
sudo docker logs epsilon-ente-photos_museum_1 2>&1 | grep "Verification code" | tail -1
```

The first registered account is treated as the initial administrator. Register
your own account first before making the instance reachable outside your local
network.

## Native Ente apps

On the onboarding screen in an Ente mobile or desktop app, tap the screen seven
times to open developer settings. Set the custom server endpoint to:

```text
http://umbrel.local:38080
```

If your Umbrel uses another hostname, replace `umbrel.local` with that hostname.
The hostname must be reachable both from the client and from the Umbrel host.

## Ports

- `33000`: Ente Photos web app
- `33002`: public Albums web app
- `38080`: Museum API for native clients
- `33200`: MinIO object API used by signed upload and download URLs

The Museum API and MinIO ports are protected by Ente's own authentication and
signed object URLs, not by the Umbrel application proxy.

## Backups and public access

Back up the entire `epsilon-ente-photos` app data directory. PostgreSQL data,
MinIO objects, and the stable secrets derived by Umbrel belong together; an
incomplete backup may be unusable.

This package is configured for HTTP access on the local network. Publishing it
on the internet requires HTTPS and a reverse proxy for the Photos, Albums, API,
and object-storage endpoints. Follow Ente's official self-hosting documentation
before exposing these ports publicly.
