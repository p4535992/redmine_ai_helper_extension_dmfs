# Changelog

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
- License the extension GPL-3.0-or-later and preserve the original MIT notice
  and source provenance.
