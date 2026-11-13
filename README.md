# Redmine AI Helper DMSF Extension

A separate Redmine plugin that adds **read-only DMSF document search and
analysis** to [Redmine AI Helper](https://github.com/haru/redmine_ai_helper).
It uses AI Helper's custom-agent extension mechanism, following
[`example/redmine_fortune/`](https://github.com/haru/redmine_ai_helper/tree/10362446a2eefd814ae76c6ec23094bddfc3cfe6/example/redmine_fortune).

[Documentazione in italiano](README.it.md) ·
[Compatibility and API contracts](docs/compatibility.md) ·
[Testing](docs/testing.md) · [Licenses and provenance](THIRD_PARTY_NOTICES.md)

Installable ZIP/TAR.GZ packages and SHA-256 checksums are published under
[GitHub Releases](https://github.com/p4535992/redmine_ai_helper_extension_dmfs/releases).
The [release workflow](docs/releasing.md) validates the plugin on Ruby 3.2, 3.3
and 3.4 before publishing a new version.

**Version:** 0.1.0 · **License:** GPL-3.0-or-later, with the original MIT notices
preserved for adapted AI Helper code.

## What this plugin does

- Finds permitted DMSF documents by current filename, title and description.
- Optionally includes candidates from DMSF's existing Xapian search, which the
  administrator can turn off from AI Helper's settings page.
- Analyzes the latest permitted PDF or UTF-8 text/code revision with the AI
  model already configured in AI Helper.
- Returns a normal DMSF document URL, current version and revision ID.
- Checks AI Helper's project access rules, DMSF project permissions, folder
  ACLs and revision visibility before disclosing metadata or reading bytes.

The extension has no document creation, editing, deletion, moving or approval
tools. It adds no database tables, routes, migrations, index or external MCP
service. DMSF, Redmine and AI Helper are installed separately; their files are
not modified by this plugin.

## Requirements

| Component | Requirement |
| --- | --- |
| AI Helper | 3.13.0 or later; 3.13.0 is the inspected extension API baseline |
| DMSF | 5.0.0 or later, using Active Storage |
| Redmine | 6.1 or later for DMSF 5.0.x; DMSF 5.1.x/5.2.x require Redmine 7.0 or later |
| Ruby | A version supported by the installed Redmine and AI Helper; AI Helper's baseline is Ruby 3.2+ |
| AI model | An AI Helper model that supports the selected attachment type |

The relevant source APIs were inspected in DMSF 5.0.0, 5.0.5, 5.1.1 and 5.2.0.
This is a **source compatibility assessment**, not a completed runtime
certification of those combinations. See [the compatibility matrix](docs/compatibility.md).
DMSF 4.x uses different storage APIs and is not supported by this release.

## Installation

1. Install compatible versions of Redmine, AI Helper and DMSF using their own
   instructions. Ensure AI Helper chat and DMSF work independently first.
2. From the **Redmine root**, install this repository using the exact folder
   name below:

   ```bash
   git clone https://github.com/p4535992/redmine_ai_helper_extension_dmfs.git plugins/redmine_ai_helper_extension_dmfs
   ```

3. Set this environment variable for every Redmine process serving AI Helper:

   ```bash
   REDMINE_AI_HELPER_DMSF_ENABLED=1
   ```

   Set it in your application service/container configuration. An `export` in
   an unrelated interactive shell will not change a running service.
4. In **Administration → AI Helper**, enable **Send attachments to LLM** and
   choose the attachment size limit. Both this setting and the environment
   variable are required, including for metadata search.
5. Enable **DMSF** on the target project. The project must also be accessible
   under AI Helper's normal project rules, including its **Target all projects**
   setting when applicable.
6. Give intended users **View DMSF files** (`view_dmsf_files`). Analysis also
   requires **View DMSF file revisions** (`view_dmsf_file_revisions`). Existing
   folder ACLs still apply.
7. Restart Redmine and check **Administration → Plugins** for
   **Redmine AI Helper DMSF Extension**. Run the checks in [Testing](docs/testing.md)
   on a suitable test installation before enabling access to real documents.

The spelling **`dmfs` in the repository and installation folder is intentional**:
it preserves this repository's existing name. The integration and Ruby namespace
correctly use **DMSF**. Keep the folder name exactly as shown so Redmine loads
AI Helper before this extension.

This plugin has no additional gems or database migrations. Its dependencies
still require their normal installation and migration steps.

## Settings

This extension has no separate configuration screen. Its options are a **DMSF
tab inside Administration → AI Helper**, saved with AI Helper's own settings
form, so the operator configures everything in one place.

| Option | Default | Effect |
| --- | --- | --- |
| Full-text search in document contents | enabled | `search_files` also queries DMSF's Xapian index. When disabled, only the current filename, title and description are searched and the tool reports `content_search: "disabled"`. |

The tab states whether `redmine_dmsf` is detected and whether its full-text
index is reported as available. **These options only work when `redmine_dmsf`
is installed and enabled on the project**: without DMSF they are stored but have
no effect, and the agent stays disabled. The agent also needs
`REDMINE_AI_HELPER_DMSF_ENABLED=1` and AI Helper's **Send attachments to LLM**
option, both shown as reminders in the same tab.

The values are stored as this plugin's own Redmine plugin setting
(`Setting.plugin_redmine_ai_helper_extension_dmfs`). AI Helper's model, tables,
migrations and settings are not modified. Unknown or hand-edited values are
normalized to `0`/`1`, and a submission that does not carry this field leaves
the stored value unchanged.

If you previously installed the experimental AI Helper branch with built-in
DMSF tools, use an upstream-compatible AI Helper installation when moving to
this extension. The new agent has a distinct name to avoid overwriting the old
one, but keeping both integrations enabled exposes duplicate DMSF agents.

## Use in AI Helper chat

No additional chat screen or endpoint is needed. AI Helper discovers
`RedmineAiHelperDmsf::DmsfExtensionAgent` automatically and can delegate document
requests to it when the integration is enabled.

Example requests:

- “Find the DMSF documents about the API specification in project 12.”
- “Summarize DMSF document 42 and give me its original link and version.”
- “Does the latest revision of DMSF document 42 describe the retention period?”

Use a user account with the appropriate permissions. A missing or inaccessible
document receives the same generic access error. If a required opt-in is off,
DMSF is missing, or its storage API is unsupported, the agent is disabled and
direct tool calls are rejected.

### Tools

| Tool | Parameters | Result |
| --- | --- | --- |
| `search_files` | Required `query` (up to 200 characters); optional `project_id`; `limit` defaults to 10, capped at 20 | Current authorized document metadata and search-coverage flags |
| `analyze_file` | Required `file_id`; optional `question` (up to 2,000 characters) | Current authorized metadata and the configured model's analysis |

Supported analysis extensions:
`.pdf`, `.txt`, `.md`, `.csv`, `.json`, `.xml`, `.log`, `.rb`, `.py`, `.js`,
`.html`, `.css`. Text must be valid UTF-8. Office formats, historical revision
analysis and comparisons are not implemented.

Analysis sends the selected document's contents to the AI provider configured in
AI Helper. It checks the configured size limit before downloading and checks the
actual downloaded size again before sending. The contents are carried as an
in-memory attachment; storage keys, signed blob URLs and disk paths are not
returned to the calling agent.

### Search coverage

The metadata stage scans at most 2,000 candidate documents in authorized projects
and returns at most 20 permitted matches. An optional DMSF search call has its
own 2,000-candidate cap; DMSF's Xapian implementation has additional internal
limits. These are separate bounds, not a claim that all content was searched.

Search responses include:

| Field | Meaning |
| --- | --- |
| `scanned` | Candidate rows examined in the extension's metadata stage |
| `truncated` | An extension scan/result/candidate bound was encountered |
| `content_search` | `unavailable`, `attempted`, `disabled` when the administrator turned full-text search off, or `not_attempted` when no projects are authorized |
| `content_search_limited` | The returned DMSF candidate batch reached its bound or reported more candidates |
| Per-document `match_source` | `current_metadata` or `dmsf_search` |

`attempted` reports an invocation, not a guarantee that the Xapian index is
healthy or complete. DMSF can handle index initialization failures internally.
`truncated: false` does not certify exhaustive index coverage.

**DMSF search can match earlier revisions.** A `dmsf_search` candidate does not
prove that the query appears in its current revision. Returned metadata and
`analyze_file` always use the latest active revision; indexed snippets and
historical contents are never included in search responses. Ask for analysis
to verify a statement against the current document.

## Architecture and maintenance

- `init.rb` registers an independent Redmine plugin and checks AI Helper's
  required version before loading the agent.
- `DmsfExtensionAgent < RedmineAiHelper::BaseAgent` registers automatically and
  returns the extension's provider through `available_tool_providers`.
- `DmsfTools < RedmineAiHelper::Tools::FileTools` reuses AI Helper's configured
  model and project access rules while declaring only two read-only tools.
- The agent's prompts live in this plugin's English, Italian and Japanese
  locales, with English fallback. They do not depend on an added upstream prompt.
- `lib/redmine_ai_helper_dmsf/patches/` appends the DMSF tab to AI Helper's
  settings page and persists this plugin's own setting. AI Helper's views, model
  and tables are not replaced or copied; the patch is applied idempotently from
  `to_prepare` and `after_initialize`, because Redmine 7 production eager-loads
  plugin code without running a plugin-registered `to_prepare`.
- DMSF availability is checked at request time because its initializer runs
  after this plugin. No DMSF model is manually loaded or patched during startup.

The current upstream MCP server enumerates direct `BaseTools` subclasses.
Because this provider extends `FileTools`, this release integrates with **AI
Helper chat** and does not automatically add DMSF tools to that MCP endpoint.

Compatibility with DMSF's internal APIs is maintained in this repository.
Review [the pinned contracts and matrix](docs/compatibility.md) when updating
either dependency.

## Disable or uninstall

Remove `REDMINE_AI_HELPER_DMSF_ENABLED=1` from the service configuration, or turn
off AI Helper's attachment-sharing setting, and restart the affected processes
when changing their environment. Disabling either gate prevents new tool calls.
Turning off full-text search in the DMSF tab does not disable the agent: it only
restricts searches to current metadata.
To uninstall, remove this plugin's directory from the Redmine installation and
restart Redmine. No extension database rollback is required.

Existing AI Helper conversation history is managed by AI Helper; disabling this
extension does not erase earlier messages or provider-side records.

## License and acknowledgements

This extension is **GPL-3.0-or-later**. AI Helper's adapted code retains its
original MIT notice in [LICENSES/redmine_ai_helper-MIT.txt](LICENSES/redmine_ai_helper-MIT.txt).
DMSF is GPL-3.0-or-later; Redmine is GPL-2.0-or-later. Their implementations are
not bundled or relicensed here.

See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for
the complete terms, original copyrights and pinned source provenance.
