# TrueNAS (Native) — `truenas_ng`

A HACS-distributed custom [Home Assistant](https://www.home-assistant.io/) integration that monitors and controls a **TrueNAS 26** system over the native **JSON-RPC 2.0 WebSocket API** (`wss://<host>:<port>/api/current`). No REST, no SSH, no add-ons — it talks to the same API the TrueNAS web UI uses.

> **Status:** v0.1 — read/monitor focused, with scrub / reboot / shutdown controls. Targets TrueNAS `26.0.0-BETA.1`+ and Home Assistant `2026.5.0`+.

## Features

- **Pools** — capacity, allocation, free space, fragmentation, scrub state; ZFS health as a binary sensor, plus a **Scrub** button per pool.
- **Disks** — per-disk temperature and ZFS read/write/checksum error counts (mapped from pool topology); a problem binary sensor per disk.
- **Datasets** — usage, available, quota, compression, dedup, and snapshot counts (sensors created disabled by default; enable the ones you want).
- **System** — hostname, version, uptime, CPU cores, load average, and product/serial as device attributes.
- **Live performance** — CPU usage %, CPU temperature, and memory used / free / used-% sampled every 20 seconds via `reporting.get_data`.
- **Services** — running/stopped binary sensors for `cifs`, `ssh`, `nfs`, and other configured services.
- **Alerts** — a sensor counting active alerts, and `WARNING`/`CRITICAL` alerts surfaced as Home Assistant **Repairs** issues (with a one-click dismiss flow).
- **Controls** — **Reboot** and **Shutdown** buttons for the appliance.
- **Diagnostics** — downloadable, API-key-redacted config + coordinator snapshots from the device page.

## Requirements

- Home Assistant **2026.5.0** or newer.
- TrueNAS **26** (tested against `26.0.0-BETA.1`). Earlier TrueNAS releases are **not** supported — the REST API was removed and the JSON-RPC method/field names differ.
- HTTPS reachable on the TrueNAS API port (default **9443**) with the WebSocket endpoint enabled (it is, by default).

## TLS is mandatory

This integration connects over `wss://` **only** — there is no plaintext (`ws://`) option, and the configured port is the **HTTPS** API port.

TrueNAS 26 **auto-revokes any API key transmitted over a cleartext connection.** If you point this integration at a plaintext endpoint (or terminate TLS incorrectly in front of it), TrueNAS will silently invalidate the key and the integration will fail to authenticate. Always use the HTTPS host/port and a valid certificate.

If your TrueNAS uses a self-signed or internal-CA certificate that Home Assistant does not trust, set **Verify SSL certificate** to off during setup (the connection is still encrypted; only certificate validation is relaxed). Prefer a trusted certificate where possible.

## Installation (HACS — custom repository)

This repository is **not** in the default HACS store yet, so add it as a custom repository:

1. In Home Assistant, open **HACS**.
2. Click the **⋮** (top-right) → **Custom repositories**.
3. Repository: `https://github.com/japatton/ha-truenas-ng`
4. Type / Category: **Integration**.
5. Click **Add**, then find **TrueNAS (Native)** in HACS and **Download** it.
6. **Restart Home Assistant.**

### Manual installation (alternative)

Copy the `custom_components/truenas_ng/` directory from this repository into your Home Assistant `config/custom_components/` directory, then restart Home Assistant.

## Configuration

After installation, add the integration from the UI: **Settings → Devices & Services → Add Integration → TrueNAS (Native)**. The config flow asks for:

| Field | Default | Notes |
| --- | --- | --- |
| **Host** | — | Hostname or IP of the TrueNAS API endpoint. Use the hostname that matches the certificate when **Verify SSL** is on. |
| **Port** | `9443` | The **HTTPS** API port. |
| **Username** | `homeassistant` | A dedicated TrueNAS service account with the `FULL_ADMIN` role. |
| **API key** | — | An API key minted for the username above (TrueNAS → **Credentials → API Keys**). The key value is only shown once at creation. |
| **Verify SSL certificate** (`verify_ssl`) | on | Turn off only for self-signed / internal-CA certificates. |

The flow validates the connection by logging in with the API key and calling `system.info` + `system.host_id`; on success a hub device (plus per-pool and per-disk devices) is created.

### Creating the API key on TrueNAS

1. On TrueNAS, create (or reuse) a dedicated user — `homeassistant` by convention — and grant it the `FULL_ADMIN` role.
2. Go to **Credentials → API Keys → Add**, associate it with that user, and copy the generated key.
3. Paste the key into the Home Assistant config flow. (Because TrueNAS revokes keys sent over cleartext, only ever enter it into the `wss://` HTTPS endpoint.)

## Screenshots

<!-- Screenshots placeholder — add device page, sensors, and Repairs examples before the first tagged release. -->
_Screenshots coming soon._

## Reauthentication & reconfiguration

If the API key is rotated or revoked, Home Assistant raises a reauth flow — enter a fresh key. You can also reconfigure the host/port/verify-SSL from the integration's **⋮ → Reconfigure** menu without removing the entry.

## License

[Apache-2.0](LICENSE). This project **imports** (never vendors) the LGPL-3.0 `truenas_api_client` library.
