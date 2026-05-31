# Release prerequisites — `truenas_ng`

These steps are **manual** and must be completed **before the first tagged release**. They live outside the integration code (GitHub + the `home-assistant/brands` repo) and are not covered by CI.

## 1. Brand assets → `home-assistant/brands`

Home Assistant and HACS render the integration's icon/logo from the central [`home-assistant/brands`](https://github.com/home-assistant/brands) repository, keyed by the **domain** `truenas_ng`. Until the assets are merged, the integration shows a generic placeholder.

Submit a pull request to `home-assistant/brands` adding, for **custom** integrations:

- `custom_integrations/truenas_ng/icon.png` — square icon, **256×256** (a `icon@2x.png` at 512×512 may also be supplied).
- `custom_integrations/truenas_ng/logo.png` — wider logo used on integration pages.

Asset rules (per the brands repo `README`):

- PNG, transparent background, trimmed to the artwork (no extra padding).
- `icon.png` must be square; keep file sizes small.
- Use the official TrueNAS / iXsystems marks; do not recolor or distort them.

**Checklist:**

- [ ] `icon.png` (256×256) created and trimmed.
- [ ] `logo.png` created and trimmed.
- [ ] PR opened against `home-assistant/brands` under `custom_integrations/truenas_ng/`.
- [ ] PR merged (or, at minimum, opened and linked in the release notes).

## 2. GitHub repository settings

HACS surfaces the repo Description and Topics, and users need a place to file bugs. On `https://github.com/japatton/ha-truenas-ng` → **Settings** (and the **About** gear on the repo home page):

- [ ] **Description** — set a one-line description, e.g. `Native TrueNAS 26 integration for Home Assistant (JSON-RPC WebSocket API)`.
- [ ] **Topics** — add at least: `home-assistant`, `homeassistant`, `hacs`, `hacs-integration`, `truenas`, `zfs`, `custom-integration`.
- [ ] **Issues** — ensure the **Issues** feature is enabled (it backs the `issue_tracker` URL in `manifest.json`).

## 3. Distribution note

The canonical origin is Forgejo; HACS resolves from GitHub only, so releases are mirrored to `github.com/japatton/ha-truenas-ng` and Forgejo Actions pushes the release tag to the GitHub mirror. Ensure the mirror's default branch and the pushed tag both contain `custom_components/truenas_ng/`, `hacs.json`, `README.md`, `info.md`, and `LICENSE` so HACS validation passes.
