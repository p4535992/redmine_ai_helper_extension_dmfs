# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 p4535992 and contributors.

"""Offline checks for release publication boundaries; no network is used."""

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from urllib.error import HTTPError


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "publish_release.py"
SPEC = importlib.util.spec_from_file_location("release_publisher_under_test", SCRIPT)
publisher = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = publisher
SPEC.loader.exec_module(publisher)

REPOSITORY = "p4535992/redmine_ai_helper_extension_dmfs"
TOKEN = "test-token-that-must-not-appear-in-errors"
COMMIT = "a" * 40
OTHER_COMMIT = "b" * 40
TAG_OBJECT = "c" * 40
VERSION = "0.1.0"
TAG = "v0.1.0"
PLUGIN = "redmine_ai_helper_extension_dmfs"
RELEASE_URL = f"https://github.com/{REPOSITORY}/releases/tag/{TAG}"


class IsolatedEnvironmentTest(unittest.TestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(os.environ, {}, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)


class ArtifactFixtureTest(IsolatedEnvironmentTest):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory(prefix="release-publisher-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.directory = self.root / "dist"
        self.directory.mkdir()
        self.zip_name = f"{PLUGIN}-{VERSION}.zip"
        self.tar_name = f"{PLUGIN}-{VERSION}.tar.gz"
        (self.directory / self.zip_name).write_bytes(b"archive zip test bytes")
        (self.directory / self.tar_name).write_bytes(b"archive tar test bytes")
        checksum_lines = []
        for name in (self.zip_name, self.tar_name):
            digest = hashlib.sha256((self.directory / name).read_bytes()).hexdigest()
            checksum_lines.append(f"{digest}  {name}\n")
        (self.directory / "SHA256SUMS").write_text("".join(checksum_lines), encoding="utf-8")
        (self.directory / "release-notes.md").write_text(
            "# Version 0.1.0\n\nChanges taken from CHANGELOG.md.\n", encoding="utf-8"
        )
        self.manifest = {
            "version": VERSION,
            "tag": TAG,
            "commit": COMMIT,
            "assets": [self.zip_name, self.tar_name, "SHA256SUMS"],
            "notes_file": "release-notes.md",
        }
        self.write_manifest()

    def write_manifest(self):
        (self.directory / "release.json").write_text(
            json.dumps(self.manifest), encoding="utf-8"
        )

    def load(self, head=COMMIT, event=None):
        return publisher.load_manifest(self.directory, head, event)


class ManifestTests(ArtifactFixtureTest):
    def test_valid_manifest_preserves_exact_commit_and_safe_artifact_paths(self):
        plan = self.load(event=COMMIT)

        self.assertEqual(VERSION, plan.version)
        self.assertEqual(TAG, plan.tag)
        self.assertEqual(COMMIT, plan.commit)
        self.assertEqual(
            {self.zip_name, self.tar_name, "SHA256SUMS"},
            {path.name for path in plan.assets},
        )
        self.assertTrue(all(path.parent == self.directory for path in plan.assets))
        self.assertEqual(self.directory / "release-notes.md", plan.notes_file)

    def test_manifest_commit_must_match_checked_out_head(self):
        with self.assertRaises(publisher.ReleaseError):
            self.load(head=OTHER_COMMIT)

    def test_event_commit_must_match_manifest(self):
        with self.assertRaises(publisher.ReleaseError):
            self.load(event=OTHER_COMMIT)

    def test_event_commit_cannot_be_a_branch_name_or_partial_hash(self):
        for value in ("main", COMMIT[:7], "z" * 40):
            with self.subTest(value=value), self.assertRaises(publisher.ReleaseError):
                self.load(event=value)

    def test_stable_semver_is_required(self):
        for value in ("01.0.0", "1.2", "1.2.3-rc.1", "1.2.3+build", "../0.1.0", 123):
            with self.subTest(version=value):
                self.manifest["version"] = value
                self.write_manifest()
                with self.assertRaises(publisher.ReleaseError):
                    self.load()

    def test_tag_must_match_version(self):
        self.manifest["tag"] = "v0.2.0"
        self.write_manifest()

        with self.assertRaises(publisher.ReleaseError):
            self.load()

    def test_full_commit_sha_is_required(self):
        for value in (COMMIT[:7], "refs/heads/main", "z" * 40, 123):
            with self.subTest(commit=value):
                self.manifest["commit"] = value
                self.write_manifest()
                with self.assertRaises(publisher.ReleaseError):
                    self.load()

    def test_duplicate_assets_are_rejected(self):
        self.manifest["assets"] = [self.zip_name, self.zip_name, "SHA256SUMS"]
        self.write_manifest()

        with self.assertRaises(publisher.ReleaseError):
            self.load()

    def test_unexpected_or_traversing_assets_are_rejected(self):
        original = self.manifest["assets"][:]
        for path in ("../secret.txt", "/tmp/secret.txt", "nested/asset.zip", "other.zip"):
            with self.subTest(path=path):
                self.manifest["assets"] = [path, original[1], original[2]]
                self.write_manifest()
                with self.assertRaises(publisher.ReleaseError):
                    self.load()

    def test_notes_filename_is_fixed(self):
        self.manifest["notes_file"] = "../release-notes.md"
        self.write_manifest()

        with self.assertRaises(publisher.ReleaseError):
            self.load()

    def test_missing_asset_is_rejected(self):
        (self.directory / self.zip_name).unlink()

        with self.assertRaises(publisher.ReleaseError):
            self.load()

    def test_empty_notes_are_rejected(self):
        (self.directory / "release-notes.md").write_bytes(b"")

        with self.assertRaises(publisher.ReleaseError):
            self.load()

    def test_tampered_archive_is_rejected(self):
        (self.directory / self.zip_name).write_bytes(b"different archive bytes")

        with self.assertRaises(publisher.ReleaseError):
            self.load()

    def test_checksum_manifest_must_cover_both_archives(self):
        checksum_path = self.directory / "SHA256SUMS"
        checksum_path.write_text(checksum_path.read_text().splitlines()[0] + "\n")

        with self.assertRaises(publisher.ReleaseError):
            self.load()

    def test_asset_symlink_is_rejected(self):
        target = self.root / "outside.zip"
        asset = self.directory / self.zip_name
        target.write_bytes(asset.read_bytes())
        asset.unlink()
        asset.symlink_to(target)

        with self.assertRaises(publisher.ReleaseError):
            self.load()

    def test_json_root_must_be_an_object(self):
        self.manifest = []
        self.write_manifest()

        with self.assertRaises(publisher.ReleaseError):
            self.load()


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_arguments):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def getcode(self):
        return self.status


class FakeOpener:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.requests = []

    def open(self, request, *arguments, **keywords):
        self.requests.append(request)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return FakeResponse(response)


def http_error(status):
    return HTTPError(
        "https://api.github.com/test", status, "test failure", {},
        io.BytesIO(json.dumps({"message": TOKEN}).encode("utf-8")),
    )


class GitHubAPITests(IsolatedEnvironmentTest):
    def test_request_uses_fixed_github_api_host_and_authorization_header(self):
        opener = FakeOpener({"tag_name": TAG})
        api = publisher.GitHubAPI(REPOSITORY, TOKEN, opener=opener)

        self.assertEqual({"tag_name": TAG}, api.get(f"releases/tags/{TAG}"))
        request = opener.requests[0]
        self.assertEqual(f"https://api.github.com/repos/{REPOSITORY}/releases/tags/{TAG}", request.full_url)
        self.assertEqual("GET", request.get_method())
        self.assertEqual(f"Bearer {TOKEN}", request.get_header("Authorization"))

    def test_only_explicitly_allowed_404_becomes_absent(self):
        api = publisher.GitHubAPI(REPOSITORY, TOKEN, opener=FakeOpener(http_error(404)))

        self.assertIsNone(api.get(f"releases/tags/{TAG}", missing_ok=True))

    def test_nonoptional_404_remains_an_error(self):
        api = publisher.GitHubAPI(REPOSITORY, TOKEN, opener=FakeOpener(http_error(404)))

        with self.assertRaises(publisher.ReleaseError):
            api.get(f"releases/tags/{TAG}")

    def test_permission_errors_are_not_treated_as_missing_and_do_not_expose_token(self):
        api = publisher.GitHubAPI(REPOSITORY, TOKEN, opener=FakeOpener(http_error(403)))

        with self.assertRaises(publisher.ReleaseError) as raised:
            api.get(f"releases/tags/{TAG}", missing_ok=True)
        self.assertNotIn(TOKEN, str(raised.exception))

    def test_unapproved_endpoint_is_rejected_before_opening_network(self):
        opener = FakeOpener()
        api = publisher.GitHubAPI(REPOSITORY, TOKEN, opener=opener)

        with self.assertRaises(publisher.ReleaseError):
            api.get("../../users/test")
        self.assertEqual([], opener.requests)

    def test_annotated_tag_resolves_to_commit(self):
        api = publisher.GitHubAPI(REPOSITORY, TOKEN, opener=FakeOpener(
            {"object": {"type": "tag", "sha": TAG_OBJECT}},
            {"object": {"type": "commit", "sha": COMMIT}},
        ))

        self.assertEqual(COMMIT, api.tag_commit(TAG))

    def test_missing_tag_is_absent(self):
        api = publisher.GitHubAPI(REPOSITORY, TOKEN, opener=FakeOpener(http_error(404)))

        self.assertIsNone(api.tag_commit(TAG))

    def test_noncommit_tag_target_is_rejected(self):
        api = publisher.GitHubAPI(REPOSITORY, TOKEN, opener=FakeOpener(
            {"object": {"type": "tree", "sha": COMMIT}},
        ))

        with self.assertRaises(publisher.ReleaseError):
            api.tag_commit(TAG)

    def test_cyclic_annotated_tag_is_rejected(self):
        cycle = {"object": {"type": "tag", "sha": TAG_OBJECT}}
        api = publisher.GitHubAPI(REPOSITORY, TOKEN, opener=FakeOpener(*([cycle] * 12)))

        with self.assertRaises(publisher.ReleaseError):
            api.tag_commit(TAG)


def published_release(**overrides):
    release = {
        "tag_name": TAG,
        "draft": False,
        "prerelease": False,
        "published_at": "2026-11-12T12:00:00Z",
        "html_url": RELEASE_URL,
    }
    release.update(overrides)
    return release


class FakeAPI:
    def __init__(self, releases, tags=()):
        self.releases = iter(releases)
        self.tags = iter(tags)
        self.release_calls = []
        self.tag_calls = []

    def release(self, tag):
        self.release_calls.append(tag)
        return next(self.releases)

    def tag_commit(self, tag):
        self.tag_calls.append(tag)
        return next(self.tags)


class PublicationTests(ArtifactFixtureTest):
    def setUp(self):
        super().setUp()
        self.plan = self.load()
        self.runner = mock.Mock(return_value=subprocess.CompletedProcess(
            [], 0, stdout=RELEASE_URL + "\n", stderr=""
        ))

    def publish(self, api, channel="release"):
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            return publisher.publish_release(
                self.plan, REPOSITORY, TOKEN, self.root,
                api=api, runner=self.runner, channel=channel,
            )

    def test_published_release_is_left_unchanged_when_main_has_moved(self):
        api = FakeAPI([published_release(target_commitish=OTHER_COMMIT)])

        self.assertEqual("skipped", self.publish(api))
        self.runner.assert_not_called()
        self.assertEqual([], api.tag_calls)

    def test_existing_draft_requires_review_without_mutation(self):
        api = FakeAPI([published_release(draft=True, published_at=None)])

        with self.assertRaises(publisher.ReleaseError):
            self.publish(api)
        self.runner.assert_not_called()

    def test_release_response_must_refer_to_the_requested_tag(self):
        api = FakeAPI([published_release(tag_name="v9.9.9")])

        with self.assertRaises(publisher.ReleaseError):
            self.publish(api)
        self.runner.assert_not_called()

    def test_tag_pointing_to_a_different_commit_blocks_publication(self):
        api = FakeAPI([None], [OTHER_COMMIT])

        with self.assertRaises(publisher.ReleaseError):
            self.publish(api)
        self.runner.assert_not_called()

    def test_new_release_uses_tested_commit_assets_and_changelog_notes(self):
        api = FakeAPI([None, published_release()], [None, COMMIT])

        self.assertEqual("published", self.publish(api))
        self.runner.assert_called_once()
        arguments = self.runner.call_args.args[0]
        self.assertEqual(["gh", "release", "create", TAG], arguments[:4])
        self.assertEqual(COMMIT, arguments[arguments.index("--target") + 1])
        self.assertEqual(REPOSITORY, arguments[arguments.index("--repo") + 1])
        self.assertEqual(str(self.plan.notes_file), arguments[arguments.index("--notes-file") + 1])
        self.assertIn("--latest", arguments)
        self.assertNotIn("--prerelease", arguments)
        self.assertNotIn("--generate-notes", arguments)
        self.assertNotIn("--clobber", arguments)
        self.assertNotIn(TOKEN, arguments)
        for asset in self.plan.assets:
            self.assertIn(str(asset), arguments)
        self.assertFalse(self.runner.call_args.kwargs.get("shell", False))
        self.assertEqual(self.root, self.runner.call_args.kwargs["cwd"])
        self.assertEqual([TAG, TAG], api.release_calls)
        self.assertEqual([TAG, TAG], api.tag_calls)

    def test_prerelease_uses_same_version_and_archives_with_github_flag(self):
        api = FakeAPI([None, published_release(prerelease=True)], [None, COMMIT])

        self.assertEqual("published", self.publish(api, channel="prerelease"))
        arguments = self.runner.call_args.args[0]
        self.assertEqual(["gh", "release", "create", TAG], arguments[:4])
        self.assertIn("--prerelease", arguments)
        self.assertIn("--latest=false", arguments)
        self.assertNotIn("--latest", arguments)
        for asset in self.plan.assets:
            self.assertIn(str(asset), arguments)

    def test_prerelease_rerun_does_not_republish_existing_version(self):
        api = FakeAPI([published_release(prerelease=True)])

        self.assertEqual("skipped", self.publish(api, channel="prerelease"))
        self.runner.assert_not_called()

    def test_channel_mismatch_does_not_change_existing_release(self):
        api = FakeAPI([published_release(prerelease=True)])

        with self.assertRaisesRegex(publisher.ReleaseError, "channel"):
            self.publish(api, channel="release")
        self.runner.assert_not_called()

    def test_invalid_channel_is_rejected_before_api_access(self):
        api = FakeAPI([])

        with self.assertRaisesRegex(publisher.ReleaseError, "channel"):
            self.publish(api, channel="candidate")
        self.assertEqual([], api.release_calls)
        self.runner.assert_not_called()

    def test_github_must_confirm_prerelease_state(self):
        api = FakeAPI([None, published_release(prerelease=False)], [None, COMMIT])

        with self.assertRaisesRegex(publisher.ReleaseError, "channel"):
            self.publish(api, channel="prerelease")

    def test_existing_matching_tag_can_be_used_without_moving_it(self):
        api = FakeAPI([None, published_release()], [COMMIT, COMMIT])

        self.assertEqual("published", self.publish(api))
        self.runner.assert_called_once()

    def test_cli_failure_surfaces_without_followup_mutation_or_token_leak(self):
        api = FakeAPI([None], [None])
        self.runner.return_value = subprocess.CompletedProcess(
            [], 1, stdout="", stderr=f"Upload failed: {TOKEN}"
        )

        with self.assertRaises(publisher.ReleaseError) as raised:
            self.publish(api)
        self.assertNotIn(TOKEN, str(raised.exception))
        self.assertEqual([TAG], api.release_calls)
        self.assertEqual([TAG], api.tag_calls)

    def test_successful_cli_exit_still_requires_a_published_release(self):
        api = FakeAPI([None, published_release(draft=True, published_at=None)], [None, COMMIT])

        with self.assertRaises(publisher.ReleaseError):
            self.publish(api)

    def test_tag_is_verified_again_after_publication(self):
        api = FakeAPI([None, published_release()], [None, OTHER_COMMIT])

        with self.assertRaises(publisher.ReleaseError):
            self.publish(api)


if __name__ == "__main__":
    unittest.main()
