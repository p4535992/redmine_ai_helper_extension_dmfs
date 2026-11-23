# Publishing a release

The [Create Release workflow](../.github/workflows/release.yml) builds an installable
plugin archive from the selected committed revision. You select the version
(`X.Y.Z` only) and GitHub release channel (`stable` or `prerelease`). The channel
changes GitHub publication metadata, not the source ZIP or the version string.
The workflow uses the repository's `GITHUB_TOKEN`; no additional release secret
is required.

## Triggering a release

For a new version:

1. Update `RedmineAiHelperDmsf::VERSION` in `version.rb` to a numeric version such as `0.4.0`.
2. Add the matching `## 0.4.0` section to `CHANGELOG.md`.
3. Commit the intended source, version and changelog changes.
4. Open **Actions → Create Release → Run workflow** and select the source branch.
5. Enter **version** `0.4.0` (no `v`, `-rc.1`, or other suffix) and choose **channel**:
   - `stable` (default): publish as a normal GitHub release and mark it latest.
   - `prerelease`: publish as a GitHub prerelease, without marking it latest.

Both choices use tag `v0.4.0` and publish archives named
`redmine_ai_helper_extension_dmfs-0.4.0.zip` and
`redmine_ai_helper_extension_dmfs-0.4.0.tar.gz` from the exact selected commit.
The prerelease choice does not change the version or files inside the archives.

The Create Release workflow runs **only when manually started**. Pushing to a
branch triggers the separate Check workflow, not release publication.
GitHub supports only one release per tag: `stable` and `prerelease` are not
two different assets or tags for the same version.

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

Release notes come from the matching changelog section. They also explain that
standalone CI uses dependency doubles: it does not certify a real Redmine/DMSF
installation, storage backend, Xapian index or LLM provider. Perform the
[installation acceptance checks](testing.md) separately.

## Existing versions and failures

- A published release for the same tag and channel is reported as already
  published; its assets, tag and notes are left unchanged. If the same tag was
  published in the other channel, publication stops instead of silently changing
  its status. Promoting a prerelease to stable is a separate GitHub operation.
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
python3 scripts/build_release.py --output-dir dist
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
