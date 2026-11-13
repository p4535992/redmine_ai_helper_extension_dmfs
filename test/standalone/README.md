# Standalone behavior tests

From this plugin's root directory, run in a **fresh Ruby process**:

```sh
ruby -Itest/standalone test/standalone/dmsf_tools_test.rb
```

The suite requires Ruby and `minitest`. It loads the actual DMSF tool provider
with small, in-memory test doubles for AI Helper, Redmine, DMSF, Rails routes,
attachment storage, and the LLM boundary. It performs no network calls, database
operations, file downloads, model requests, or document modifications.

The tests exercise the production authorization and input-validation paths,
optional full-text result handling, scan/result limits, and attachment handling.
They also verify that permission failures happen before attachment reads and that
only two read-only tools are declared. The test DMSF file intentionally does not
provide `visible?` or `view_url`, because these APIs are absent in supported older
DMSF 5.x versions.

The full-text search setting is covered too: enabled default, fallback when the
stored hash has no key, `content_search: "disabled"` without a DMSF search call,
metadata-only results that keep working, and normalization of unexpected or
missing submissions.

These are contract/behavior tests, not an end-to-end Redmine installation test.
They do not verify Rails autoloading, actual database scopes, DMSF permission
inheritance, Xapian index health, or requests to a configured AI model. Use the
separate Redmine smoke check and an installation with the real dependencies to
validate those integrations.

Do not load this suite using Rails' or Redmine's test runner. Its helper rejects
an already-loaded Redmine/Rails process to avoid replacing real dependency
classes with test doubles.
