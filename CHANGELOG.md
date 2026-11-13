# Changelog

## 0.2.0 — 2026-11-13

- Add an administrator setting for DMSF full-text search. It is rendered as a
  DMSF tab inside AI Helper's own settings page, states that it only works with
  `redmine_dmsf` installed and enabled, and is stored as this plugin's own
  Redmine plugin setting without touching AI Helper's model, tables or
  migrations.
- Report `content_search: "disabled"` and skip the DMSF search call when the
  administrator turned full-text search off; metadata search keeps working.
- Normalize stored values to `0`/`1`, merge defaults for installations that
  saved settings before this release, and ignore submissions from other AI
  Helper tabs.
- Extend the standalone suite with settings/default/normalization coverage and
  the Redmine smoke check with settings-page registration assertions.

## 0.1.0 — 2026-11-12

- Extract the DMSF integration into an independently installed Redmine plugin
  using AI Helper's custom-agent mechanism.
- Add a distinct agent namespace/registration key and local English, Italian
  and Japanese instructions.
- Retain read-only metadata search, optional DMSF indexed search and current
  PDF/UTF-8 document analysis with explicit administrative activation.
- Enforce DMSF folder ACLs in addition to project permissions and active
  revision checks; reauthorize indexed candidates before returning metadata.
- Use Active Storage and the stable DMSF route for source compatibility with
  DMSF 5.x, including versions without `DmsfFile#visible?` or `#view_url`.
- Bound indexed candidates, validate DMSF's result contract, surface unexpected
  integration errors and distinguish indexed matches from current metadata.
- Check actual downloaded byte size before model transmission and reject
  non-integer IDs.
- Add standalone behavior tests, a real-Redmine registration smoke check,
  installation instructions, compatibility evidence and explicit test status.
- Add a GitHub Actions release workflow with a Ruby 3.2/3.3/3.4 validation
  matrix, installable ZIP/TAR.GZ archives, SHA-256 checksums and changelog notes.
- License the extension GPL-3.0-or-later and preserve the original MIT notice
  and source provenance.
