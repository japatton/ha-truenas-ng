# ha-truenas-ng

HACS custom integration "TrueNAS (Native)" (`truenas_ng`) for TrueNAS 26 over
JSON-RPC 2.0 WebSocket — replaces the broken `tomaae` integration. Ships pools,
disks, system, services, alerts, reporting, apps, and VMs as HA entities.
Forgejo (`origin`, private) is canonical; push-mirrors to a public GitHub repo
(HACS requires a public repo). The public mirror is sanitized (fake hostnames/
serials/domains; real design docs kept out-of-repo).

## Build
No build step — a plain Python HA custom component (`custom_components/truenas_ng/`).

## Lint/format
`ruff check custom_components tests` (ruff runs clean per project history; no
committed ruff config — defaults apply).

## Test
```
pip install pytest-homeassistant-custom-component==0.13.330 websocket-client==1.9.0
pytest tests/ -q
```
PHACC pins HA `2026.5.1`; run on Python 3.14. See `reference_ha_custom_integration_testing.md`
for HA-specific mocking/fixture gotchas.

## Pre-push verification
CI (`.github/workflows/validate.yml`) runs HACS validation, Hassfest, and
`pytest tests/ -q` on every push/PR — run ruff + the pytest command above locally
first. Bump `manifest.json` version and re-run the live-test recipe (mint a
throwaway `hauser` API key, connect `wss://truenas.homelab.jp-labs.net:9443`)
before tagging a release.

## Deploy notes
No deploy step — HACS users pull releases directly; tag + GitHub release triggers
the HACS update flow. Vault: `~/notes-vault/memory/projects/ha-truenas-ng/`, `~/notes-vault/memory/global/project_ha_truenas_ng.md`
