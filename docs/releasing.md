# Publishing a release

The [Create Release workflow](../.github/workflows/release.yml) builds an installable
plugin archive from the selected committed revision. Select a numeric `X.Y.Z`
release label and a GitHub channel (`release` or `prerelease`). Neither choice
rewrites the selected source code or the version embedded in the ZIP.
The workflow uses the repository's `GITHUB_TOKEN`; no additional release secret
is required.

## Triggering a release

1. Commit the source to be distributed and push it to the selected branch.
2. Open **Actions → Create Release → Run workflow** and select that branch.
3. Enter a numeric **version** such as `0.4.0`, never a leading `v` or suffix.
4. Select the **channel** dropdown: `release` (default) publishes a normal
   release marked Latest; `prerelease` publishes a GitHub prerelease, not Latest.

Both channels package the exact same committed source. The input `0.4.0` labels
the GitHub tag `v0.4.0` and ZIP/TAR.GZ assets but **does not change version.rb
inside the source archive**. If the source says `0.3.0`, the installed plugin
still reports `0.3.0`. For matching internal version numbers, edit and commit
`version.rb` before publishing.

Notes use the matching `CHANGELOG.md` section, or `Unreleased` when no numbered
entry exists, or a generic source-snapshot note when neither is present.
A mismatch between input and source version is explicitly recorded in notes.

This release workflow is manual-only; pushing a branch triggers **Check**.
GitHub supports only one release per tag, not a separate release and prerelease
with the same tag.

## Checks and assets

The validation jobs use Ruby **3.2, 3.3 and 3.4**. They check the syntax of all
tracked Ruby files and run the standalone plugin tests. The release scripts'
offline Python tests run once, on the Ruby 3.2 job. Publication waits for the
entire matrix to succeed.

The publishing job checks out the same full commit SHA that was validated,
reads version/changelog from that commit, and builds these assets:

| Asset for version 0.1.0 | Contents |
| --- | --- |
| `redmine_ai_helper_extension_dmfs-0.1.0.zip` | Complete tracked source under the installable plugin directory |
| `redmine_ai_helper_extension_dmfs-0.1.0.tar.gz` | The same source in a compressed tar archive |
| `SHA256SUMS` | SHA-256 hashes for both archives |

Both archives contain a single root directory named
**`redmine_ai_helper_extension_dmfs/`**. The version is in the archive filename,
not the installation directory. This preserves the plugin ID and Redmine load
order. The archives include the GPL license, original MIT notice, attribution,
documentation and tests.

Release notes prefer the matching changelog section, then Unreleased, then generic snapshot notes. They also explain that
standalone CI uses dependency doubles: it does not certify a real Redmine/DMSF
installation, storage backend, Xapian index or LLM provider. Perform the
[installation acceptance checks](testing.md) separately.

## Existing versions and failures

- A published release for the same tag and channel is reported as already
  published; its assets, tag and notes are left unchanged. If the same tag was
  published in the other channel, publication stops instead of silently changing
  its status. Promoting a prerelease to a normal release is a separate GitHub operation.
- A tag that exists without a published release must resolve to the tested
  commit before it can be used. A tag pointing elsewhere stops publication.
- A leftover draft stops publication for review. The workflow does not delete
  drafts, overwrite assets, move tags or force-push.
- Validation, packaging or API errors fail the run. Fix the cause and rerun, or
  publish a new version when the original release already exists.

Only the publishing job has `contents: write`; validation jobs have read-only
repository access. Action dependencies are pinned to full commit SHAs.
Concurrent release runs are coordinated and an active publication is not
cancelled by a later push.

## Building locally

From a Git checkout with Python 3 and Git installed:

```bash
python3 -m unittest discover -s test/release -p 'test_*.py' -v
python3 scripts/build_release.py --output-dir dist --version 0.4.0
```

The builder archives **committed HEAD**, not uncommitted changes. It writes
ZIP, TAR.GZ, checksums, notes and a manifest to `dist/`. Identical existing
outputs are accepted; differing outputs with the same names are not silently
replaced. Use a new output directory when inspecting a different commit of the
same version.

To verify downloaded archives, place `SHA256SUMS` beside them and run:

```bash
sha256sum -c SHA256SUMS
```

Extract the selected archive inside Redmine's `plugins/` directory and follow
the normal activation instructions in [README.md](../README.md).
