# TrueNAS (Native)

Monitor and control **TrueNAS 26** from Home Assistant over the native JSON-RPC 2.0 WebSocket API (`wss://`) — no REST, no SSH, no add-ons.

**Includes:** pool capacity & ZFS health (+ scrub button), per-disk temperature & ZFS error counts, dataset usage & snapshot counts, live CPU % / CPU temperature / memory, service up/down sensors, alerts as Repairs issues, and reboot / shutdown buttons.

Requires TrueNAS 26 (`26.0.0-BETA.1`+) and Home Assistant 2026.5.0+. **TLS is mandatory** — connect to the HTTPS API port (default `9443`) with an API key; TrueNAS auto-revokes keys sent over cleartext.

See the [README](https://github.com/japatton/ha-truenas-ng) for setup details.
