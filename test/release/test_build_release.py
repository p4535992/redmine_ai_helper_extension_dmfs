# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 p4535992 and contributors.

"""Offline release-builder tests using disposable, local Git repositories."""

import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
import zipfile


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_release.py"
SPEC = importlib.util.spec_from_file_location("build_release", SCRIPT)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class BuildReleaseTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="dmsf-release-test-")
        self.addCleanup(self.temporary.cleanup)
        self.repository = Path(self.temporary.name) / "repository"
        self.repository.mkdir()
        self.git("init", "--quiet", "-b", "main")
        self.write("version.rb", 'module RedmineAiHelperDmsf\n  VERSION = "0.1.0"\nend\n')
        self.write("init.rb", "# plugin initializer\n")
        self.write("LICENSE", "Synthetic GPL license fixture\n")
        self.write("LICENSES/redmine_ai_helper-MIT.txt", "Synthetic MIT notice fixture\n")
        self.write("README.md", "# Synthetic plugin fixture\n")
        self.write("lib/example.rb", "# tracked runtime source\n")
        self.write("CHANGELOG.md", "# Changes\n\n## 0.1.0 — 2026-11-12\n\n- Current release changes.\n\n## 0.0.9\n\n- Previous release only.\n")
        self.commit()

    def git(self, *arguments):
        environment = os.environ.copy()
        environment.update({"GIT_AUTHOR_DATE": "2026-11-12T12:00:00Z", "GIT_COMMITTER_DATE": "2026-11-12T12:00:00Z"})
        return subprocess.run(
            ["git", "-C", str(self.repository), *arguments],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
        ).stdout.decode("utf-8").strip()

    def write(self, name, contents):
        path = self.repository / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")

    def commit(self):
        self.git("add", "--all")
        self.git("-c", "user.name=Release Test", "-c", "user.email=release-test@example.invalid", "commit", "--quiet", "-m", "Local release test fixture")

    def test_builds_verified_archives_checksums_and_current_changelog(self):
        manifest = builder.build_release(self.repository)
        output = self.repository / "dist"
        self.assertEqual("0.1.0", manifest["version"])
        self.assertEqual("v0.1.0", manifest["tag"])
        self.assertEqual(self.git("rev-parse", "HEAD"), manifest["commit"])
        self.assertEqual(manifest, json.loads((output / "release.json").read_text()))
        expected_files = set(self.git("ls-files").splitlines())
        prefix = "redmine_ai_helper_extension_dmfs/"
        with zipfile.ZipFile(output / manifest["assets"][0]) as archive:
            self.assertIsNone(archive.testzip())
            self.assertTrue(all(name.startswith(prefix) for name in archive.namelist()))
            names = {entry.filename[len(prefix):] for entry in archive.infolist() if not entry.is_dir()}
            self.assertEqual(expected_files, names)
            self.assertEqual(b"Synthetic MIT notice fixture\n", archive.read(prefix + "LICENSES/redmine_ai_helper-MIT.txt"))
        tar_gz = (output / manifest["assets"][1]).read_bytes()
        self.assertEqual(b"\x00\x00\x00\x00", tar_gz[4:8])
        with tarfile.open(fileobj=io.BytesIO(gzip.decompress(tar_gz)), mode="r:") as archive:
            names = {entry.name[len(prefix):] for entry in archive if entry.isfile()}
            self.assertEqual(expected_files, names)
        checksum_lines = (output / "SHA256SUMS").read_text().splitlines()
        self.assertEqual(2, len(checksum_lines))
        for line in checksum_lines:
            digest, name = line.split("  ", 1)
            self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)
        notes = (output / manifest["notes_file"]).read_text()
        self.assertIn("Current release changes.", notes)
        self.assertNotIn("Previous release only.", notes)
        self.assertIn("real Redmine/DMSF installations", notes)
        self.assertIn("not covered", notes)

    def test_uncommitted_content_is_not_accidentally_released(self):
        self.write("version.rb", 'VERSION = "9.9.9"\n')
        self.write("lib/example.rb", "# uncommitted content\n")
        self.write("untracked-secret.txt", "not part of the committed source\n")
        manifest = builder.build_release(self.repository)
        self.assertEqual("0.1.0", manifest["version"])
        with zipfile.ZipFile(self.repository / "dist" / manifest["assets"][0]) as archive:
            prefix = "redmine_ai_helper_extension_dmfs/"
            self.assertEqual(b"# tracked runtime source\n", archive.read(prefix + "lib/example.rb"))
            self.assertNotIn(prefix + "untracked-secret.txt", archive.namelist())

    def test_identical_rerun_is_deterministic_and_preserves_existing_files(self):
        builder.build_release(self.repository)
        output = self.repository / "dist"
        before = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in output.iterdir()}
        builder.build_release(self.repository)
        after = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in output.iterdir()}
        self.assertEqual(before, after)

    def test_different_existing_output_is_never_overwritten(self):
        output = self.repository / "dist"
        output.mkdir()
        existing = output / "SHA256SUMS"
        existing.write_text("previous output must remain\n")
        with self.assertRaisesRegex(builder.ReleaseBuildError, "Refusing to overwrite"):
            builder.build_release(self.repository)
        self.assertEqual("previous output must remain\n", existing.read_text())
        self.assertEqual([existing], list(output.iterdir()))

    def test_output_cannot_be_inside_tracked_source_or_git_metadata(self):
        for requested in (Path("."), Path("lib/releases"), Path(".git/releases")):
            with self.subTest(requested=requested):
                with self.assertRaises(builder.ReleaseBuildError):
                    builder.build_release(self.repository, requested)

    def test_malformed_versions_are_rejected_without_running_ruby(self):
        for version in ("v0.1.0", "0.1", "0.1.0-rc.1", "01.2.3", "0.1.0;echo unsafe"):
            with self.subTest(version=version):
                with self.assertRaises(builder.ReleaseBuildError):
                    builder.parse_version(f'  VERSION = "{version}"\n')
        with self.assertRaises(builder.ReleaseBuildError):
            builder.parse_version('VERSION = "0.1.0"; system("false")\n')
        with self.assertRaises(builder.ReleaseBuildError):
            builder.parse_version('VERSION = "0.1.0"\nVERSION = "0.2.0"\n')
        self.write("version.rb", 'VERSION = "bad-version"\n')
        self.commit()
        with self.assertRaises(builder.ReleaseBuildError):
            builder.build_release(self.repository)
        self.assertFalse((self.repository / "dist").exists())

    def test_missing_exact_changelog_section_is_rejected(self):
        self.write("CHANGELOG.md", "## 0.1.00\n\n- Not the expected version.\n")
        self.commit()
        with self.assertRaisesRegex(builder.ReleaseBuildError, "CHANGELOG.md"):
            builder.build_release(self.repository)
        self.assertFalse((self.repository / "dist").exists())

    def test_empty_or_duplicate_changelog_sections_are_rejected(self):
        for changelog in ("## 0.1.0\n\n", "## 0.1.0\n\n- One.\n\n## 0.1.0\n\n- Two.\n"):
            with self.subTest(changelog=changelog):
                with self.assertRaises(builder.ReleaseBuildError):
                    builder.changelog_section(changelog, "0.1.0")

    def test_required_license_notice_cannot_be_omitted(self):
        (self.repository / "LICENSES/redmine_ai_helper-MIT.txt").unlink()
        self.commit()
        with self.assertRaisesRegex(builder.ReleaseBuildError, "Required tracked release files"):
            builder.build_release(self.repository)

    def test_git_export_ignore_cannot_silently_omit_tracked_source(self):
        self.write(".gitattributes", "lib/example.rb export-ignore\n")
        self.commit()
        with self.assertRaisesRegex(builder.ReleaseBuildError, "contents do not exactly match"):
            builder.build_release(self.repository)

    def test_archive_validation_rejects_path_traversal_and_wrong_roots(self):
        for path in (
            "redmine_ai_helper_extension_dmfs/../escape.rb",
            "/redmine_ai_helper_extension_dmfs/init.rb",
            "other_plugin/init.rb",
            "redmine_ai_helper_extension_dmfs/dir\\escape.rb",
        ):
            with self.subTest(path=path):
                with self.assertRaises(builder.ReleaseBuildError):
                    builder.archive_relative_path(path, directory=False)

    def test_plain_directory_is_not_accepted_as_a_git_repository(self):
        plain = Path(self.temporary.name) / "not-a-repository"
        plain.mkdir()
        with self.assertRaisesRegex(builder.ReleaseBuildError, "Git"):
            builder.build_release(plain)
        self.assertFalse((plain / "dist").exists())


if __name__ == "__main__":
    unittest.main()
