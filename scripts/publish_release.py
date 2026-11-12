#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 p4535992 and contributors.

"""Publish verified release artifacts without replacing an existing release."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any
import urllib.error
import urllib.request


PLUGIN_DIRECTORY = "redmine_ai_helper_extension_dmfs"
VERSION_PATTERN = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
COMMIT_PATTERN = r"[0-9a-f]{40}"
API_BASE = "https://api.github.com"


class ReleaseError(RuntimeError):
    """A release prerequisite failed; no automatic repair is attempted."""


@dataclass(frozen=True)
class ReleasePlan:
    version: str
    tag: str
    commit: str
    assets: tuple[Path, ...]
    notes_file: Path


def _artifact_file(directory: Path, name: str) -> Path:
    path = directory / name
    if path.is_symlink() or not path.is_file() or path.resolve().parent != directory:
        raise ReleaseError(f"Release artifact is missing or unsafe: {name}")
    if path.stat().st_size == 0:
        raise ReleaseError(f"Release artifact is empty: {name}")
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(directory: Path, head_sha: str, event_sha: str | None = None) -> ReleasePlan:
    """Bind a release manifest and its checksummed artifacts to the tested commit."""
    directory = directory.resolve()
    if not directory.is_dir():
        raise ReleaseError("Release output directory does not exist")

    manifest_path = _artifact_file(directory, "release.json")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ReleaseError("release.json is not valid UTF-8 JSON") from error
    if not isinstance(manifest, dict):
        raise ReleaseError("release.json must contain an object")

    version = manifest.get("version")
    if not isinstance(version, str) or not re.fullmatch(VERSION_PATTERN, version):
        raise ReleaseError("Release version must be a stable X.Y.Z version")
    tag = f"v{version}"
    if manifest.get("tag") != tag:
        raise ReleaseError("Release tag does not match its version")

    commit = manifest.get("commit")
    if not isinstance(commit, str) or not re.fullmatch(COMMIT_PATTERN, commit):
        raise ReleaseError("Release commit must be a full lowercase Git commit SHA")
    if not isinstance(head_sha, str) or not re.fullmatch(COMMIT_PATTERN, head_sha) or commit != head_sha:
        raise ReleaseError("Release manifest commit does not match checked-out HEAD")
    if event_sha is not None and (not re.fullmatch(COMMIT_PATTERN, event_sha) or commit != event_sha):
        raise ReleaseError("Release manifest commit does not match GITHUB_SHA")

    archive_names = [f"{PLUGIN_DIRECTORY}-{version}.zip", f"{PLUGIN_DIRECTORY}-{version}.tar.gz"]
    expected_assets = archive_names + ["SHA256SUMS"]
    if manifest.get("assets") != expected_assets:
        raise ReleaseError("Release assets must be the versioned ZIP, TAR.GZ and SHA256SUMS")
    if manifest.get("notes_file") != "release-notes.md":
        raise ReleaseError("Release notes must be release-notes.md from the changelog")

    assets = tuple(_artifact_file(directory, name) for name in expected_assets)
    notes_file = _artifact_file(directory, "release-notes.md")
    checksums: dict[str, str] = {}
    for line in assets[-1].read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([^/\\]+)", line)
        if not match or match[2] not in archive_names or match[2] in checksums:
            raise ReleaseError("SHA256SUMS contains an invalid, unexpected or duplicate entry")
        checksums[match[2]] = match[1]
    if set(checksums) != set(archive_names):
        raise ReleaseError("SHA256SUMS must contain both release archives")
    for asset in assets[:-1]:
        if _sha256(asset) != checksums[asset.name]:
            raise ReleaseError(f"Release archive checksum does not match: {asset.name}")

    return ReleasePlan(version, tag, commit, assets, notes_file)


def _repository_name(repository: str) -> str:
    if not isinstance(repository, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ReleaseError("GITHUB_REPOSITORY must identify one owner/repository")
    if any(part in {".", ".."} for part in repository.split("/")):
        raise ReleaseError("Invalid GitHub repository name")
    return repository


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    """Keep authenticated requests on their exact, canonical GitHub API URL."""

    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        raise ReleaseError("GitHub API redirected the request; use the repository's canonical name")


class GitHubAPI:
    """Read only the release and Git tag endpoints needed for publication."""

    def __init__(self, repository: str, token: str, opener=None):
        self.repository = _repository_name(repository)
        if not isinstance(token, str) or not token:
            raise ReleaseError("GH_TOKEN is required for release publication")
        self._token = token
        self._opener = opener if opener is not None else urllib.request.build_opener(_NoRedirects())

    def get(self, resource: str, missing_ok: bool = False) -> dict[str, Any] | None:
        permitted = (
            rf"(?:releases/tags/v{VERSION_PATTERN}|git/ref/tags/v{VERSION_PATTERN}|git/tags/{COMMIT_PATTERN})"
        )
        if not re.fullmatch(permitted, resource):
            raise ReleaseError("Unsupported GitHub API resource for the release publisher")
        url = f"{API_BASE}/repos/{self.repository}/{resource}"
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "redmine-ai-helper-dmsf-release",
            },
        )
        try:
            with self._opener.open(request, timeout=30) as response:
                result = json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 404 and missing_ok:
                return None
            raise ReleaseError(f"GitHub API returned HTTP {error.code} for {resource}") from None
        except urllib.error.URLError:
            raise ReleaseError(f"GitHub API request failed for {resource}") from None
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ReleaseError(f"GitHub API returned invalid JSON for {resource}") from None
        if not isinstance(result, dict):
            raise ReleaseError(f"GitHub API returned an unexpected response for {resource}")
        return result

    def release(self, tag: str) -> dict[str, Any] | None:
        return self.get(f"releases/tags/{tag}", missing_ok=True)

    def tag_commit(self, tag: str) -> str | None:
        reference = self.get(f"git/ref/tags/{tag}", missing_ok=True)
        if reference is None:
            return None
        seen = set()
        for _ in range(10):
            target = reference.get("object")
            if not isinstance(target, dict):
                raise ReleaseError(f"GitHub tag {tag} has no valid target")
            sha = target.get("sha")
            if not isinstance(sha, str) or not re.fullmatch(COMMIT_PATTERN, sha):
                raise ReleaseError(f"GitHub tag {tag} has an invalid target SHA")
            if target.get("type") == "commit":
                return sha
            if target.get("type") != "tag" or sha in seen:
                raise ReleaseError(f"GitHub tag {tag} does not resolve to a commit")
            seen.add(sha)
            reference = self.get(f"git/tags/{sha}")
        raise ReleaseError(f"GitHub tag {tag} exceeds the annotated-tag resolution limit")


def _published_release(release: dict[str, Any], tag: str) -> bool:
    if not isinstance(release, dict) or release.get("tag_name") != tag or type(release.get("draft")) is not bool:
        raise ReleaseError("GitHub returned inconsistent release metadata")
    if release["draft"]:
        raise ReleaseError(f"A draft release already exists for {tag}; inspect it before retrying")
    if not isinstance(release.get("published_at"), str) or not release["published_at"]:
        raise ReleaseError(f"Release {tag} is not confirmed published")
    return True


def publish_release(
    plan: ReleasePlan,
    repository: str,
    token: str,
    root: Path,
    api=None,
    runner=None,
) -> str:
    """Create one release or explicitly preserve an already published version."""
    repository = _repository_name(repository)
    if not isinstance(token, str) or not token:
        raise ReleaseError("GH_TOKEN is required for release publication")
    api = api if api is not None else GitHubAPI(repository, token)
    runner = runner if runner is not None else subprocess.run
    url = f"https://github.com/{repository}/releases/tag/{plan.tag}"

    existing = api.release(plan.tag)
    if existing is not None:
        _published_release(existing, plan.tag)
        print(f"Release {plan.tag} is already published; its tag and assets were left unchanged.")
        print(url)
        return "skipped"

    tagged_commit = api.tag_commit(plan.tag)
    if tagged_commit is not None and tagged_commit != plan.commit:
        raise ReleaseError(f"Tag {plan.tag} points to a different commit; it will not be moved")

    command = [
        "gh", "release", "create", plan.tag,
        *(str(asset) for asset in plan.assets),
        "--repo", repository,
        "--target", plan.commit,
        "--title", f"Redmine AI Helper DMSF Extension {plan.tag}",
        "--notes-file", str(plan.notes_file),
        "--latest",
    ]
    try:
        result = runner(command, cwd=root, capture_output=True, text=True)
    except FileNotFoundError:
        raise ReleaseError("GitHub CLI (gh) is required to publish release artifacts") from None
    if result.returncode != 0:
        detail = (result.stderr or "GitHub CLI returned no error detail").replace(token, "[REDACTED]")[:2000]
        raise ReleaseError(f"Release creation failed; inspect any remaining draft before retrying. {detail}")

    published = api.release(plan.tag)
    if published is None:
        raise ReleaseError("GitHub CLI completed, but the published release could not be verified")
    _published_release(published, plan.tag)
    if api.tag_commit(plan.tag) != plan.commit:
        raise ReleaseError("Published tag does not resolve to the tested commit; inspect the release")
    print(f"Published {plan.tag} from tested commit {plan.commit}.")
    print(url)
    return "published"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", default="dist", help="Directory produced by build_release.py")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    directory = Path(args.directory)
    if not directory.is_absolute():
        directory = root / directory

    try:
        repository = os.environ.get("GITHUB_REPOSITORY", "")
        token = os.environ.get("GH_TOKEN", "")
        _repository_name(repository)
        if not token:
            raise ReleaseError("GH_TOKEN is required for release publication")
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=root, capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise ReleaseError("Cannot identify the checked-out Git commit")
        plan = load_manifest(directory, result.stdout.strip(), os.environ.get("GITHUB_SHA"))
        publish_release(plan, repository, token, root)
    except ReleaseError as error:
        print(f"Release publication failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
