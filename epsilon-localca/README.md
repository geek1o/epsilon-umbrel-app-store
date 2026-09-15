# LocalCA on Umbrel

LocalCA provides a browser interface for managing a private certificate
authority for a home network or lab.

## Compatibility

This package supports **x86-64 (amd64) only**. The upstream project publishes
separate architecture-specific images and the package deliberately uses its
amd64 images. It does not run on Raspberry Pi or other ARM Umbrel devices.

## First sign-in

Use the upstream default credentials and change the password immediately:

- Username: `admin`
- Password: `password`

Open `/admin` from LocalCA and change the administrator password before issuing
certificates. Umbrel authentication is also enabled in front of the application.

## Security model

LocalCA stores certificates, account data, and unencrypted CA private keys in
`data/db/db.sqlite3`. Do not publish this application on the internet. Restrict
access to the Umbrel host and to every backup of the database.

Install only the public root certificate on client devices. If the database or
a CA private key is exposed, remove that root from every trust store, revoke the
old hierarchy, and create a new CA.

## Backups

Back up the entire `data/db` directory while the application is stopped. The
SQLite database contains the certificate hierarchy and application accounts.
Restoring only downloaded certificates is not sufficient to restore the CA.
