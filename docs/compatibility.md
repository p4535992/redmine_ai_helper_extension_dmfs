# Compatibility and maintenance

## Scope of the compatibility claim

This extension targets Redmine AI Helper 3.13.0 or later and the Active Storage
API introduced in DMSF 5.0.0. The source interfaces below were inspected at pinned
commits. This is a **source review, not runtime certification** of every version,
database, storage service or language-model provider combination.

The standalone tests exercise the extension's real authorization, search,
validation and attachment-handling code with dependency doubles. They do not
boot Redmine, query a real DMSF database, open a Xapian index, or send a request
to an LLM provider. Validate the installed combination in a staging Redmine
instance before deployment.

| Component inspected | Source revision | Relevant requirement or result |
| --- | --- | --- |
| AI Helper 3.13.0 | [`10362446a2ee`](https://github.com/haru/redmine_ai_helper/tree/10362446a2eefd814ae76c6ec23094bddfc3cfe6) | Custom-agent registration, provider DSL, project-access helpers and attachment-analysis entry point reviewed. |
| DMSF 4.2.4 | [`11565f2d80f4`](https://github.com/picman/redmine_dmsf/tree/11565f2d80f41eff432ffb56394edb8f49ffe6fc) | Legacy filesystem storage; **unsupported by this extension**. |
| DMSF 5.0.0 | [`bbd3cc953c37`](https://github.com/picman/redmine_dmsf/tree/bbd3cc953c3791d61e8560c41689975691611f09) | Active Storage, current-revision methods, folder ACLs, search and named routes reviewed; DMSF requires Redmine >= 6.1.0. |
| DMSF 5.0.5 | [`e0a7f2969abb`](https://github.com/picman/redmine_dmsf/tree/e0a7f2969abb4979b6025368fb249a73eb4ce28e) | Version requirements and file-model interfaces checked; DMSF requires Redmine >= 6.1.0. |
| DMSF 5.1.1 | [`6e405399861c`](https://github.com/picman/redmine_dmsf/tree/6e405399861c7461bc5ea3b7589384cdb9eac8fd) | Version requirements and file-model interfaces checked; DMSF requires Redmine >= 7.0.0. |
| DMSF 5.2.0 | [`fceb0b694a59`](https://github.com/picman/redmine_dmsf/tree/fceb0b694a59ff98f044b39c45d7b218bb836268) | Active Storage, current-revision methods, folder ACLs, controller authorization, search and named routes reviewed; DMSF requires Redmine >= 7.0.0. |

The effective Redmine requirement is the highest requirement of all installed
plugins. This extension requires at least Redmine 6.1.0, matching DMSF 5.0.x;
DMSF 5.1.x/5.2.x raise that requirement to Redmine 7.0.0. DMSF's own installation and Active Storage migration
instructions still apply. This extension does not migrate DMSF data or storage.

Future versions are not automatically certified by satisfying the numeric
minimum. DMSF implementation details are maintained here rather than in AI
Helper's core repository.

## AI Helper extension interfaces

The plugin follows the upstream
[`example/redmine_fortune/`](https://github.com/haru/redmine_ai_helper/tree/10362446a2eefd814ae76c6ec23094bddfc3cfe6/example/redmine_fortune)
pattern: a separate Redmine plugin loads an agent subclass and its tool provider.

| Interface | Use in this extension |
| --- | --- |
| `RedmineAiHelper::BaseAgent.inherited` | Registers `RedmineAiHelperDmsf::DmsfExtensionAgent` automatically. |
| `BaseAgent#available_tool_providers` | Supplies this extension's provider while retaining AI Helper's read-only tool filtering. |
| `BaseTools.define_function` | Registers only `search_files` and `analyze_file`, both with `write: false`. |
| `BaseTools#accessible_projects` / `#accessible_project?` | Enforces AI Helper project visibility, role permissions and its all-projects data-access setting. |
| `BaseTools#user_errors_as_result` | Converts expected input/access errors into `{ error: ... }`; unexpected failures remain exceptions. |
| `FileTools#analyze_with_llm` | Uses AI Helper's configured provider and forwards in-memory attachments to `chat.ask(..., with: ...)`. |

Source references:
[`BaseAgent`](https://github.com/haru/redmine_ai_helper/blob/10362446a2eefd814ae76c6ec23094bddfc3cfe6/lib/redmine_ai_helper/base_agent.rb),
[`BaseTools`](https://github.com/haru/redmine_ai_helper/blob/10362446a2eefd814ae76c6ec23094bddfc3cfe6/lib/redmine_ai_helper/base_tools.rb),
[`FileTools`](https://github.com/haru/redmine_ai_helper/blob/10362446a2eefd814ae76c6ec23094bddfc3cfe6/lib/redmine_ai_helper/tools/file_tools.rb),
[`PermissionChecker`](https://github.com/haru/redmine_ai_helper/blob/10362446a2eefd814ae76c6ec23094bddfc3cfe6/lib/redmine_ai_helper/util/permission_checker.rb).

AI Helper registers agents by their short class name. The distinct
`DmsfExtensionAgent` name avoids replacing an existing `DmsfAgent` from the
original development branch. Use an upstream AI Helper installation without the
old built-in DMSF integration to avoid exposing two overlapping agents.

The provider subclasses `FileTools` to reuse its analysis implementation.
AI Helper's tool registries are class-instance variables, so inherited public
Ruby methods do not automatically become additional registered LLM tools.
Only this provider's two declared functions are exposed through this agent.
The extension does not register a new MCP endpoint or modify AI Helper's MCP
provider list.

### AI Helper settings page

The administrator options are rendered inside AI Helper's global settings page
instead of a separate screen. The integration relies on these host contracts,
which are re-checked by the Redmine smoke check:

| Interface | Use in this extension |
| --- | --- |
| `AiHelperSettingsHelper#ai_helper_settings_tabs` | Prepended to append the `dmsf` tab after AI Helper's own tabs; the tab list is returned unchanged if the host method changes shape. |
| `AiHelperSettingsController#update` | Prepended to persist this plugin's setting after AI Helper reported success (it redirects on success and re-renders the form on failure). |
| `render_tabs` + plugin `app/views` | The tab partial lives in this plugin, which Redmine adds to the controller's view path. |
| `Redmine::Plugin#settings` | Declares `full_text_search_enabled` as this plugin's own serialized setting; no `:partial` is declared, so no separate settings screen is advertised. |

The patches are applied from `to_prepare` and `after_initialize` because
Redmine 7 production eager-loads plugin code and does not run a plugin-registered
`to_prepare`. Both calls are idempotent, and AI Helper's model, tables,
migrations and settings are never modified. If a future AI Helper release renames
these methods, the smoke check fails instead of silently dropping the tab.

## DMSF interfaces and authorization

The extension deliberately avoids `DmsfFile#visible?` and `DmsfFile#view_url`:
neither method exists in the inspected DMSF 5.0.x or 5.1.1 file model. In 5.2.0,
`visible?` checks project permission but does not enforce folder ACLs.

Every disclosed document must pass all of these checks:

1. Its project is inside the authorized AI Helper project set.
2. DMSF is enabled for that project and the user has `view_dmsf_files` permission.
3. The file is not deleted and has an active current revision.
4. `DmsfFolder.permissions?(folder, allow_system: true, file: true)` permits
   access, matching DMSF's file controller. DMSF handles inherited role, user and
   group rules, root folders, administrators and issue-linked system folders.
5. For analysis, the user also has `view_dmsf_file_revisions` permission.

The extension checks access again when analysis begins; a prior search result
does not authorize later access. DMSF's revision visibility method checks its
active/deleted status, so it is used in addition to project and folder checks.

Analysis reads `DmsfFileRevision#file`, an Active Storage attachment. This also
supports DMSF's shared attachment inheritance between revisions. It does not
construct storage paths. Metadata links use `view_dmsf_file_url`, whose route is
`/dmsf/files/:id/view` in both the inspected 5.0.0 and 5.2.0 sources. The link uses
Redmine's configured host and protocol; signed blob URLs and storage keys are
not returned.

The configured AI Helper attachment size limit is checked before download
against blob metadata and again against the downloaded byte count before LLM
transmission. The download is held in memory; the post-download check is not a
streaming memory limit. Supported text files must be valid UTF-8. PDF support
also depends on the configured model/provider accepting PDF attachments.

Source references:
[`DmsfFile` 5.0.0](https://github.com/picman/redmine_dmsf/blob/bbd3cc953c3791d61e8560c41689975691611f09/app/models/dmsf_file.rb),
[`DmsfFileRevision` 5.0.0](https://github.com/picman/redmine_dmsf/blob/bbd3cc953c3791d61e8560c41689975691611f09/app/models/dmsf_file_revision.rb),
[`DmsfFolder` 5.2.0](https://github.com/picman/redmine_dmsf/blob/fceb0b694a59ff98f044b39c45d7b218bb836268/app/models/dmsf_folder.rb),
[`DmsfFilesController` 5.2.0](https://github.com/picman/redmine_dmsf/blob/fceb0b694a59ff98f044b39c45d7b218bb836268/app/controllers/dmsf_files_controller.rb),
[`routes` 5.0.0](https://github.com/picman/redmine_dmsf/blob/bbd3cc953c3791d61e8560c41689975691611f09/config/routes.rb),
[`routes` 5.2.0](https://github.com/picman/redmine_dmsf/blob/fceb0b694a59ff98f044b39c45d7b218bb836268/config/routes.rb).

### Folder scope

`folder_id` is resolved with `DmsfFolder.find_by`, then checked against the
authorized project set, `DmsfFolder.visible.exists?(id:)` and
`DmsfFolder.permissions?(folder, allow_system: true, file: false)`. The folder
gate therefore requires `view_dmsf_folders`, which is DMSF's own condition for
displaying a folder; files inside it are still checked with the `file: true`
gate. A folder of an unauthorized project, a deleted folder or a denied folder
is rejected with the same generic error.

`folder_path` is resolved from the project root one segment at a time, reading
only the visible children of the current folder and comparing titles
case-insensitively. The walk is limited to 20 segments, so a malformed path
cannot trigger unbounded queries. `folder_id` and `folder_path` are mutually
exclusive.

`include_subfolders` walks `dmsf_folders` breadth-first through the visible
children, de-duplicating IDs and stopping at 500 folders; the response reports
`folders_truncated` when it stops early. DMSF has no single recursive scope for
this, and `DmsfFolder.directory_subtree` builds a display tree rather than an ID
set, so the bounded walk lives in this extension.

### DMSF page action

DMSF exposes no view hook on its document page (`dmsf_files/show.html.erb`
renders only `_main`) or on its folder page, and its row context menu is built by
a helper without `call_hook`. The extension therefore does not patch DMSF views.
It registers `view_layouts_base_body_bottom`, decides server-side whether the
action applies (controller `dmsf_files`/`dmsf`, action `show`, the rendered
`@dmsf_file`/`@folder`, the activation gates, DMSF permissions and an available
AI Helper chat), and emits a small script that appends the action to the page's
first `#content > .contextual` element.

The script only fills the AI Helper chat input and opens the popup; it never
submits. It depends on AI Helper's public chat surface: the
`#ai-helper-message-input` textarea, `ai_helper.page_info` with
`controller_name`/`action_name`/`content_id`, and `AiHelperChatPopup.open()`.
Those names must be re-checked when AI Helper changes its chat assets; the
standalone suite cannot detect such a change, so the Redmine acceptance step
covers it.

## Search coverage and limits

The metadata pass examines at most 2,000 active file records in permitted
projects. It matches the current filename, title or description. Up to 20
documents are returned, with a default limit of 10. Restricted documents may
consume scan budget without appearing in results; the scan count is not a
count of accessible or matching documents.

When DMSF reports Xapian availability, the extension calls
`DmsfFile.search(query, projects, { limit: 2_000 }, User.current)`. The inspected
DMSF contract is `[Array<DmsfFile>, Integer]`. The integer counts returned
candidates; it is not an exhaustive count of all possible matches. DMSF's
implementation also limits its Xapian match set to 1,000 entries. The extension
deduplicates candidates and rechecks current project, folder and revision
authorization before adding them to the shared result limit.

| Response field | Meaning |
| --- | --- |
| `match_source: "current_metadata"` | The current filename, title or description matched the query. |
| `match_source: "dmsf_search"` | DMSF's combined metadata/index search returned the document. It may have matched an earlier revision; this does not prove the current bytes contain the query. |
| `content_search: "unavailable"` | DMSF did not report an available Xapian configuration. Only the metadata pass ran. |
| `content_search: "not_attempted"` | No authorized project was available, so DMSF search was not called. |
| `content_search: "attempted"` | DMSF search was called. This is not proof that its index is healthy, current or complete. |
| `content_search_limited` | The returned candidate count reached the extension's DMSF-search cap, or the returned count reported more candidates than were supplied. A false value does not rule out DMSF's own internal Xapian cap. |
| `truncated` | The extension detected a scan/candidate limit or an additional visible match beyond the requested result count. A false value does not certify exhaustive full-text coverage. |

DMSF internally catches some index-opening failures and may return metadata
matches after logging an error. The extension cannot detect every such case
from the returned pair. Unexpected failures that DMSF does raise are allowed to
surface; the extension does not convert them to a successful empty search.
Historical snippets are not included in tool responses. Returned metadata and
analyzed bytes always refer to the current active revision.

See the inspected
[`DmsfFile.search` implementation](https://github.com/picman/redmine_dmsf/blob/fceb0b694a59ff98f044b39c45d7b218bb836268/app/models/dmsf_file.rb).

## Read-only behavior

This extension exposes no document creation, update, deletion, upload, folder
mutation, workflow change or permission change tool. It does not patch DMSF or
AI Helper classes and introduces no database migrations.

"Read-only" describes document operations. DMSF's existing search implementation
can write transient search snippets into Redmine's search cache. The AI Helper
chat and the configured LLM provider retain their normal conversation, logging
and request behavior. Reading attachment bytes directly does not invoke DMSF's
download controller, so this extension does not create that controller's
download-access records or send its download notification emails.

## Maintenance checks for dependency upgrades

- Confirm `BaseAgent` still discovers independent subclasses, filters disabled
  agents and obtains tools from `available_tool_providers`.
- Confirm `BaseTools` keeps provider registries separate, supports `write: false`
  and retains the project-access and user-error helpers used here.
- Confirm `FileTools#analyze_with_llm` and the installed RubyLLM version accept
  `RubyLLM::Attachment` objects backed by `StringIO` with a filename. Exercise
  both a PDF and UTF-8 text against the actual configured provider.
- Inspect DMSF's file controller and folder permission implementation together;
  project permission alone is not an adequate substitute for folder ACLs.
- Verify DMSF's active-file scope, deleted/current-revision methods, Active
  Storage attachment accessor, URL route and search response shape.
- Test denied project access, denied inherited folder access, issue-linked
  system folders, deleted/current revisions and permission revocation between
  search and analysis in a real staging database.
- Test the deployed storage backend, configured host/protocol, attachment size
  settings and Xapian behavior with indexed historical revisions.
- Re-check the DMSF page action against the installed DMSF and AI Helper: DMSF
  may add a real view hook, and AI Helper may rename the chat input, the
  `page_info` keys or the popup API used by the inserted script.
- Re-run the extension's regression suite and report source review, standalone
  test execution and full Redmine integration results separately.
