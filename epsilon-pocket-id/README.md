# Pocket ID on Umbrel

Pocket ID is a passkey-only OpenID Connect and OAuth 2.0 provider. Passkeys use
the WebAuthn browser API, which requires HTTPS with a certificate trusted by the
client device.

## First setup

1. Open Pocket ID from Umbrel. This opens a protected setup page, not the
   identity provider itself.
2. Download the Pocket ID root CA certificate.
3. Install that certificate in the trusted root store of every computer, phone,
   or tablet that will use Pocket ID.
4. Open `https://umbrel.local:1411/setup`. Replace `umbrel.local` with your
   Umbrel hostname if it is different.
5. Create the first administrator and register a passkey.

The certificate is issued for the hostname reported by umbrelOS. Always use the
same hostname rather than the server IP address.

## Trusting the certificate

- **macOS:** add the downloaded certificate to the System keychain and set it
  to **Always Trust**.
- **iPhone and iPad:** install the downloaded configuration profile, then enable
  full trust under **Settings > General > About > Certificate Trust Settings**.
- **Windows:** import it into **Trusted Root Certification Authorities** for the
  current computer.
- **Linux:** follow the trust-store instructions for your distribution and
  browser. Firefox may use its own certificate store.

Close and reopen the browser after changing its trust store.

## Security and backups

The public root certificate is safe to distribute to your own devices. Its
private key is stored under `data/caddy` and must remain secret. Anyone who gets
that private key can issue certificates trusted by those devices.

Back up both `data/pocket-id` and `data/caddy`. Protect the backup as carefully
as the live data. If the private CA is compromised or you permanently remove the
app, remove its root certificate from every client trust store.

Pocket ID is reachable directly on HTTPS port `1411` and provides its own
authentication. Umbrel authentication protects only the certificate download
and setup guide on the app's normal launch page.
