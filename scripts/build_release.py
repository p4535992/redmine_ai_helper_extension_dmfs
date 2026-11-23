#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 p4535992 and contributors.

"""Build verified release archives from the repository's exact committed HEAD."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import subprocess
import sys
import tarfile
import zipfile


PLUGIN_DIRECTORY = "redmine_ai_helper_extension_dmfs"
REQUIRED_FILES = {
    "init.rb",
    "version.rb",
    "LICENSE",
    "LICENSES/redmine_ai_helper-MIT.txt",
    "README.md",
}
STABLE_VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")


class ReleaseBuildError(Exception):
    """A release input or output failed a packaging contract."""


def git_bytes(repository: Path, *arguments: str) -> bytes:
    """Run a read-only Git command without a shell or remote access."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as error:
        raise ReleaseBuildError("The git executable is required") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode("utf-8", errors="replace").strip()
        raise ReleaseBuildError(f"Git {' '.join(arguments)} failed: {detail}") from error
    return result.stdout


def parse_version(source: str) -> str:
    """Read one literal VERSION assignment; never execute the Ruby file."""
    declarations = re.findall(r"(?m)^[ \t]*VERSION[ \t]*=", source)
    assignments = re.findall(
        r'''(?m)^[ \t]*VERSION[ \t]*=[ \t]*(["'])([^"'\r\n]+)\1[ \t]*(?:\#[^\r\n]*)?$''',
        source,
    )
    if len(declarations) != 1 or len(assignments) != 1:
        raise ReleaseBuildError("version.rb must contain exactly one literal VERSION assignment")
    version = assignments[0][1]
    if not STABLE_VERSION.fullmatch(version):
        raise ReleaseBuildError("VERSION must be a stable X.Y.Z version without leading zeroes")
    return version


def changelog_section(changelog: str, version: str) -> str:
    """Select exactly the requested level-two version heading and its body."""
    headings = list(re.finditer(r"(?m)^##[ \t]+([^\r\n]+)[ \t]*$", changelog))
    expected = re.compile(re.escape(version) + r"(?:[ \t]+[—–-][ \t]+.+)?")
    matches = [index for index, heading in enumerate(headings) if expected.fullmatch(heading.group(1).strip())]
    if len(matches) != 1:
        raise ReleaseBuildError(f"CHANGELOG.md must contain exactly one '## {version}' section")
    index = matches[0]
    end = headings[index + 1].start() if index + 1 < len(headings) else len(changelog)
    body = changelog[headings[index].end():end].strip()
    if not body:
        raise ReleaseBuildError(f"CHANGELOG.md section {version} is empty")
    return body


def release_changes(changelog: str, version: str, *, fallback: bool = False) -> str:
    """Use matching release notes or the Unreleased notes for a labeled source snapshot."""
    if not fallback:
        return changelog_section(changelog, version)
    headings = re.findall(r"(?m)^##[ \t]+([^\r\n]+)[ \t]*$", changelog)
    numbered = re.compile(re.escape(version) + r"(?:[ \t]+[—–-][ \t]+.+)?")
    if any(numbered.fullmatch(heading.strip()) for heading in headings):
        return changelog_section(changelog, version)
    if any(heading.strip() == "Unreleased" for heading in headings):
        return "Changes listed as Unreleased in the selected source:\n\n" + changelog_section(changelog, "Unreleased")
    return "Source snapshot from the selected Git commit; no matching release changelog entry."


def tracked_files(repository: Path) -> set[str]:
    """Enumerate the committed regular files, rejecting unbundled Git submodules."""
    paths = set()
    for record in git_bytes(repository, "ls-tree", "-rz", "--full-tree", "HEAD").split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, object_type, _sha = metadata.decode("ascii").split()
        path = raw_path.decode("utf-8")
        if object_type != "blob" or mode not in {"100644", "100755"}:
            raise ReleaseBuildError(f"Only regular tracked files can be packaged: {path}")
        paths.add(path)
    missing = REQUIRED_FILES - paths
    if missing:
        raise ReleaseBuildError("Required tracked release files are missing: " + ", ".join(sorted(missing)))
    return paths


def archive_relative_path(name: str, *, directory: bool) -> str | None:
    """Require one fixed root and paths safe to extract on supported systems."""
    trimmed = name[:-1] if name.endswith("/") else name
    parts = trimmed.split("/")
    if "\\" in name or any(part in {"", ".", ".."} for part in parts):
        raise ReleaseBuildError(f"Unsafe archive path: {name!r}")
    if parts[0] != PLUGIN_DIRECTORY:
        raise ReleaseBuildError(f"Unexpected archive root: {name!r}")
    if len(parts) == 1:
        if not directory:
            raise ReleaseBuildError("The archive root must be a directory")
        return None
    return "/".join(parts[1:])


def validate_zip(payload: bytes, expected_files: set[str]) -> None:
    paths = set()
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            if archive.testzip() is not None:
                raise ReleaseBuildError("ZIP integrity verification failed")
            for item in archive.infolist():
                mode = item.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise ReleaseBuildError(f"ZIP symbolic links are unsupported: {item.filename}")
                relative = archive_relative_path(item.filename, directory=item.is_dir())
                if item.is_dir():
                    continue
                if relative in paths:
                    raise ReleaseBuildError(f"Duplicate ZIP entry: {relative}")
                paths.add(relative)
                if relative in REQUIRED_FILES and item.file_size == 0:
                    raise ReleaseBuildError(f"Required ZIP entry is empty: {relative}")
    except zipfile.BadZipFile as error:
        raise ReleaseBuildError("Invalid ZIP archive") from error
    if paths != expected_files:
        raise ReleaseBuildError("ZIP contents do not exactly match the committed tracked files")


def validate_tar(payload: bytes, expected_files: set[str]) -> None:
    paths = set()
    try:
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as archive:
            for item in archive:
                if not item.isfile() and not item.isdir():
                    raise ReleaseBuildError(f"Unsupported TAR entry type: {item.name}")
                relative = archive_relative_path(item.name, directory=item.isdir())
                if item.isdir():
                    continue
                if relative in paths:
                    raise ReleaseBuildError(f"Duplicate TAR entry: {relative}")
                paths.add(relative)
                if relative in REQUIRED_FILES and item.size == 0:
                    raise ReleaseBuildError(f"Required TAR entry is empty: {relative}")
    except tarfile.TarError as error:
        raise ReleaseBuildError("Invalid TAR archive") from error
    if paths != expected_files:
        raise ReleaseBuildError("TAR contents do not exactly match the committed tracked files")


def resolve_output_directory(repository: Path, requested: Path, source_files: set[str]) -> Path:
    output = (requested if requested.is_absolute() else repository / requested).resolve()
    if output == repository or output in repository.parents:
        raise ReleaseBuildError("The output directory must not be the repository root or one of its parents")
    if output.is_relative_to(repository):
        first_component = output.relative_to(repository).parts[0]
        source_roots = {path.split("/", 1)[0] for path in source_files}
        if first_component == ".git" or first_component in source_roots:
            raise ReleaseBuildError("The output directory must not be inside tracked source or Git metadata")
    if output.exists() and not output.is_dir():
        raise ReleaseBuildError("The requested output directory is an existing file")
    return output


def build_release(repository: Path, requested_output: Path = Path("dist"), release_version: str | None = None) -> dict:
    repository = repository.resolve()
    actual_root = Path(git_bytes(repository, "rev-parse", "--show-toplevel").decode("utf-8").strip()).resolve()
    if actual_root != repository:
        raise ReleaseBuildError("Run the builder with the root of the plugin repository")
    commit = git_bytes(repository, "rev-parse", "HEAD").decode("ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit):
        raise ReleaseBuildError("Git HEAD did not resolve to a complete commit ID")

    source_version = parse_version(git_bytes(repository, "show", "HEAD:version.rb").decode("utf-8"))
    if release_version is not None and (
        not isinstance(release_version, str) or not STABLE_VERSION.fullmatch(release_version)
    ):
        raise ReleaseBuildError("Requested release version must be numeric X.Y.Z without v or suffix")
    version = source_version if release_version is None else release_version
    changelog = git_bytes(repository, "show", "HEAD:CHANGELOG.md").decode("utf-8")
    changes = release_changes(changelog, version, fallback=release_version is not None)
    source_files = tracked_files(repository)
    output = resolve_output_directory(repository, requested_output, source_files)

    prefix = f"--prefix={PLUGIN_DIRECTORY}/"
    zip_payload = git_bytes(repository, "archive", "--format=zip", prefix, "HEAD")
    tar_payload = git_bytes(repository, "archive", "--format=tar", prefix, "HEAD")
    validate_zip(zip_payload, source_files)
    validate_tar(tar_payload, source_files)
    gzip_buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=gzip_buffer, mtime=0) as compressor:
        compressor.write(tar_payload)
    compressed_payload = gzip_buffer.getvalue()

    basename = f"{PLUGIN_DIRECTORY}-{version}"
    archives = {f"{basename}.zip": zip_payload, f"{basename}.tar.gz": compressed_payload}
    checksums = "".join(f"{hashlib.sha256(payload).hexdigest()}  {name}\n" for name, payload in archives.items())
    source_version_note = (
        f"Source version.rb: {source_version}. The installable archive is an unmodified "
        f"snapshot of the selected commit; the release label is {version}.\n\n"
        if version != source_version else ""
    )
    notes = (
        f"# Redmine AI Helper DMSF Extension {version}\n\n{source_version_note}{changes}\n\n"
        "## Validation scope\n\n"
        "The release workflow publishes after the standalone tests and syntax checks pass. "
        "Those checks use isolated dependency doubles; real Redmine/DMSF installations, "
        "storage backends, Xapian indexes and AI model providers are not covered. "
        "Validate the plugin on the intended installation before production use.\n"
    )
    manifest = {
        "version": version,
        "source_version": source_version,
        "tag": version,
        "commit": commit,
        "assets": [*archives, "SHA256SUMS"],
        "notes_file": "release-notes.md",
    }
    outputs = {
        **archives,
        "SHA256SUMS": checksums.encode("utf-8"),
        "release-notes.md": notes.encode("utf-8"),
        "release.json": (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    }

    # Validate every existing output before writing anything. Identical reruns
    # are allowed; a different commit/version must never silently replace assets.
    for name, payload in outputs.items():
        destination = output / name
        if destination.is_symlink():
            raise ReleaseBuildError(f"Refusing symbolic-link output: {destination}")
        if destination.exists() and (not destination.is_file() or destination.read_bytes() != payload):
            raise ReleaseBuildError(f"Refusing to overwrite different existing output: {destination}")

    output.mkdir(parents=True, exist_ok=True)
    for name, payload in outputs.items():
        destination = output / name
        if not destination.exists():
            with destination.open("xb") as stream:
                stream.write(payload)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("dist"),
        help="output directory (default: dist under the repository root)",
    )
    parser.add_argument("--version", type=str, default=None,
                        help="Numeric GitHub release X.Y.Z label (does not rewrite the source)")
    arguments = parser.parse_args()
    try:
        manifest = build_release(Path(__file__).resolve().parents[1],
                                 arguments.output_dir, release_version=arguments.version)
    except (ReleaseBuildError, OSError, UnicodeError) as error:
        print(f"Release build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
