# BookOrbit on umbrelOS

This package runs BookOrbit 3.1.0 with its required PostgreSQL/pgvector database.

## First launch

1. Open BookOrbit from the Umbrel dashboard.
2. Create the administrator account.
3. When asked for the setup bootstrap token, use the generated password shown by
   Umbrel in BookOrbit's app details.
4. Create a library inside `/books`.

The container path `/books` maps to Umbrel's shared
`/downloads/books` directory. Files added through BookOrbit or copied into that
shared folder remain available outside the app.

## Client address

Use `http://umbrel.local:3010` for BookOrbit's web interface, native clients,
Kobo/KOReader integrations, and OPDS readers. If the Umbrel hostname was changed,
replace `umbrel.local` with its current local hostname or LAN address.

BookOrbit provides its own user authentication, so Umbrel's additional proxy login
is intentionally disabled for this package. Complete the initial setup before
making the service reachable outside a trusted network.

## Backups

Back up both of these app-data directories together:

- `data/app` — covers, avatars, caches, and other BookOrbit-managed files
- `data/postgres` — accounts, libraries, metadata, progress, and settings

Back up `/downloads/books` separately. Restoring only the database or only the app
files can leave the library incomplete.
