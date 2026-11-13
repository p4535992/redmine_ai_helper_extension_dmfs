# Testing and validation

## Status of the initial extraction

The initial implementation was checked against the pinned source APIs listed in
[compatibility.md](compatibility.md), including the real DMSF folder ACL gate,
the Active Storage transition and AI Helper's agent registration/DSL.

The initial authoring environment had no Ruby executable or Redmine installation,
so the original extraction did not execute Ruby tests there. The
[Release workflow](releasing.md) now runs Ruby syntax checks and the standalone
suite on Ruby 3.2, 3.3 and 3.4, and publishes only when those jobs succeed.
Consult the corresponding Actions run for its actual result. Static file
checks and locale parsing are not a substitute for test execution.

The workflow still does not boot a real Redmine application or call a model.
The Redmine/DMSF compatibility matrix remains a source assessment until the
real-installation checks below are run on the intended combination.

## Standalone behavior tests

From this plugin's directory, with Ruby 3.2+ and Minitest available:

```bash
ruby -Itest/standalone test/standalone/dmsf_tools_test.rb
```

The suite loads the production `DmsfTools` implementation with isolated fakes
for external Redmine, DMSF, AI Helper and RubyLLM boundaries. It requires no
database, network, model credentials or real documents. Minitest is a test
dependency; it is not an additional runtime requirement for this plugin.

The fakes intentionally do not implement the DMSF instance methods `visible?`
and `view_url`, which did not exist in DMSF 5.0. The production code must use
explicit project/folder checks and the stable named route instead.

The tests exercise dependency and double-opt-in gates, permissions before
attachment access, folder ACLs, current revision filtering, strict IDs,
search caps, indexed-result reauthorization/deduplication, malformed search
responses, surfaced integration failures, supported formats, UTF-8, size
checks before and after download, and the two read-only tool declarations.

They also cover the full-text search setting: the enabled default, fallback for
stored settings without the key, `content_search: "disabled"` with no DMSF
search call when the administrator turns it off, metadata matches that keep
working, normalization of unexpected values, and submissions that must not
reset the stored value.

**Run the standalone suite in its own Ruby process.** Its fake top-level classes
must not be loaded into a running Redmine environment. Do not add its files to
a generic in-process Redmine test task.

## Syntax check

From this plugin's directory:

```bash
find . -name '*.rb' -not -path './.git/*' -exec ruby -c {} \;
```

## Smoke check inside Redmine

Install the plugin and its dependencies in a test Redmine instance first.
Run from that instance's **Redmine root**:

```bash
RAILS_ENV=test bundle exec ruby plugins/redmine_ai_helper_extension_dmfs/test/redmine_smoke.rb
```

The script also accepts `REDMINE_ROOT` if the plugin is being checked outside
the normal `plugins/` layout. The selected environment must already contain an
AI Helper settings row and the dependencies' schema. The script does not create
them; AI Helper's normal settings getter can create a row when none exists, so
the smoke check explicitly requires one and prevents writes during assertions.

The smoke check loads the real application and verifies plugin registration,
the automatic agent registry entry, generated read-only tools, activation
gates, and locale fallback. It avoids constructing an LLM provider and performs
no document analysis or model calls. Application boot itself follows the host
installation's normal initialization behavior.

It also verifies the settings integration without saving anything: the plugin
setting is declared, the plugin has no separate settings screen, AI Helper's
settings helper and controller carry the extension patches, the DMSF tab is
appended to AI Helper's tab list, the tab partial exists, and the stored value is
normalized to `0`/`1`.

## Acceptance on the intended Redmine/DMSF version

With a test project and non-sensitive sample documents:

1. Confirm the agent is disabled with either administrative opt-in off.
2. Enable both gates and grant the account the required project permissions.
3. Search a root document and an allowed folder document; verify the URL,
   filename, current version and revision ID.
4. Deny access to a folder through DMSF's normal ACLs; neither metadata search
   nor direct analysis of a known ID may disclose or download it.
5. Remove `view_dmsf_file_revisions`; metadata access can remain available,
   but analysis must fail before reading attachment bytes.
6. Analyze a small PDF and valid UTF-8 text file using a compatible model.
   Confirm the actual provider call, citations and size-limit behavior.
7. If Xapian is used, test with the index disabled and enabled. Test a term
   found only in an older revision: the result must not be presented as proof
   about the current revision. Confirm the returned `match_source`.
8. Check project boundaries, deleted files, hidden system/issue folders and
   AI Helper's all-project setting with accounts that have different roles.

These steps cover behavior that dependency fakes cannot establish: Rails load
order, the real database scopes/ACL inheritance, Active Storage backends, URL
mounting, RubyLLM/provider attachment handling and the configured Xapian index.
