# Changelog

## v0.1.0 — unreleased

Initial release: a Home Assistant custom integration for **TrueNAS 26** over the
JSON-RPC 2.0 WebSocket API.

### Added
- Config flow (host / port / username / API key / verify-SSL) with reauth + reconfigure;
  device anchored on `system.host_id`.
- **Storage** — pool health, capacity, fragmentation, last-scrub state/date; per-disk
  temperature + ZFS read/write/checksum error counters; per-dataset used/available/quota/
  compression/snapshots (disabled by default).
- **System** — live CPU % and memory (used/free), load averages, uptime, OS version;
  active-alerts sensor.
- **Services** — per-service running binary sensors.
- **Controls** — per-pool scrub, host reboot, host shutdown buttons.
- Alerts surfaced via the **Repairs** platform (with dismiss); redacted **diagnostics**.

Requires TrueNAS 26 (BETA) and Home Assistant 2026.5+.
