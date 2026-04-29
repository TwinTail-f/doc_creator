"""Unit tests for autodoc.parser.parsers.manifest_parser.ManifestParser.

Covers: parse, _parse_single_file, _build_releases.
Real .properties files are read from resources_dir fixture.
Custom / edge-case content is written to tmp_path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autodoc.parser.parsers.manifest_parser import ManifestParser

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

TARGET_PLATFORM: str = "2.0"
CHANNEL_TECH: str = "tech"
NULL_PACKAGE_ID: str = "da39a3ee5e6b4b0d3255bfef95601890afd80709"

VALID_SINGLE_CONTENT: str = (
    "name= openssl\n"
    "description= TLS library\n"
    "versions.component= 3.0.0\n"
    "versions.platform= 2.0-tech\n"
    "profiles-3.0.0-2.0-tech= hw-linux-x86_64-gcc10_2, hw-linux-armv7-gcc10_2\n"
    "tfs_git_project= DEP_Components\n"
    "git_repo_name= contrib_openssl\n"
)

VALID_PATCHELF_CONTENT: str = (
    "name= patchelf\n"
    "description= ELF patcher\n"
    "versions.component= 1.0\n"
    "versions.platform= 2.0-tech\n"
    "profiles-1.0-2.0-tech= hw-linux-x86_64-gcc10_2\n"
    "tfs_git_project= DEP_Components\n"
    "git_repo_name= contrib_patchelf\n"
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def write_props(tmp_path: Path, filename: str, content: str) -> Path:
    """Write content to a .properties file in tmp_path and return the path."""
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return p


# ===========================================================================
# 2.1 — Happy path: single component, single release
# ===========================================================================


def test_manifest_parser_parse_single_valid_file(tmp_path: Path) -> None:
    """ManifestParser returns one component with two profile_builds for a valid file."""
    path = write_props(tmp_path, "openssl.properties", VALID_SINGLE_CONTENT)
    components, _ = ManifestParser(TARGET_PLATFORM).parse([path], excluded=[])
    assert len(components) == 1
    assert components[0].name == "openssl"
    assert len(components[0].releases[0].profile_builds) == 2


# ===========================================================================
# 2.2 — File without 'name' field is silently skipped
# ===========================================================================


def test_manifest_parser_skips_file_without_name(tmp_path: Path) -> None:
    """ManifestParser silently skips a .properties file that has no 'name' key."""
    path = write_props(tmp_path, "noname.properties", "description= test\n")
    components, warnings = ManifestParser(TARGET_PLATFORM).parse([path], excluded=[])
    assert len(components) == 0
    assert len(warnings) == 0


# ===========================================================================
# 2.3 — Excluded component is not returned
# ===========================================================================


def test_manifest_parser_excluded_component_not_returned(tmp_path: Path) -> None:
    """ManifestParser omits components whose name appears in the excluded list."""
    path = write_props(tmp_path, "patchelf.properties", VALID_PATCHELF_CONTENT)
    components, _ = ManifestParser(TARGET_PLATFORM).parse([path], excluded=["patchelf"])
    assert len(components) == 0


# ===========================================================================
# 2.4 — Platform version mismatch → no release created
# ===========================================================================


def test_manifest_parser_platform_mismatch_no_release(tmp_path: Path) -> None:
    """ManifestParser returns no components when all platform versions mismatch the target."""
    content = (
        "name= libfoo\n"
        "versions.component= 1.0\n"
        "versions.platform= 1.0-tech\n"
        "profiles-1.0-1.0-tech= hw-linux-x86_64-gcc10_2\n"
    )
    path = write_props(tmp_path, "libfoo.properties", content)
    components, _ = ManifestParser(TARGET_PLATFORM).parse([path], excluded=[])
    assert len(components) == 0


# ===========================================================================
# 2.5 — File that does not exist produces a warning
# ===========================================================================


def test_manifest_parser_missing_file_produces_warning() -> None:
    """ManifestParser records a warning and returns no components for a non-existent file."""
    missing = Path("nonexistent.properties")
    components, warnings = ManifestParser(TARGET_PLATFORM).parse([missing], excluded=[])
    assert len(components) == 0
    assert len(warnings) == 1


# ===========================================================================
# 2.6 — Multiple component versions → multiple releases
# ===========================================================================


def test_manifest_parser_multiple_component_versions_produce_multiple_releases(
    tmp_path: Path,
) -> None:
    """ManifestParser creates one release per matching component-version / platform pair."""
    content = (
        "name= patchelf\n"
        "versions.component= 0.16.1, 0.18.0\n"
        "versions.platform= 2.0-tech\n"
        "profiles-0.16.1-2.0-tech= hw-linux-x86_64-gcc10_2\n"
        "profiles-0.18.0-2.0-tech= hw-linux-x86_64-gcc10_2, hw-linux-armv7-gcc10_2\n"
    )
    path = write_props(tmp_path, "patchelf.properties", content)
    components, _ = ManifestParser(TARGET_PLATFORM).parse([path], excluded=[])
    assert len(components) == 1
    releases = components[0].releases
    assert len(releases) == 2
    release_018 = next(r for r in releases if r.version == "0.18.0")
    assert len(release_018.profile_builds) == 2


# ===========================================================================
# 2.7 — Channel is extracted from platform version suffix
# ===========================================================================


def test_manifest_parser_channel_extracted_from_platform_suffix(
    tmp_path: Path,
) -> None:
    """ManifestParser sets release.channel to the part after the first '-' in the platform version."""
    content = (
        "name= libfoo\n"
        "versions.component= 1.0\n"
        "versions.platform= 2.0-fast\n"
        "profiles-1.0-2.0-fast= hw-linux-x86_64-gcc10_2\n"
    )
    path = write_props(tmp_path, "libfoo.properties", content)
    components, _ = ManifestParser(TARGET_PLATFORM).parse([path], excluded=[])
    assert components[0].releases[0].channel == "fast"


# ===========================================================================
# 2.8 — Platform version without suffix → empty channel
# ===========================================================================


def test_manifest_parser_platform_without_suffix_empty_channel(
    tmp_path: Path,
) -> None:
    """ManifestParser sets release.channel to '' when the platform version has no '-' suffix."""
    content = (
        "name= libfoo\n"
        "versions.component= 1.0\n"
        "versions.platform= 2.0\n"
        "profiles-1.0-2.0= hw-linux-x86_64-gcc10_2\n"
    )
    path = write_props(tmp_path, "libfoo.properties", content)
    components, _ = ManifestParser(TARGET_PLATFORM).parse([path], excluded=[])
    assert components[0].releases[0].channel == ""


# ===========================================================================
# 2.9 — git_url is constructed from tfs_git_project and git_repo_name
# ===========================================================================


def test_manifest_parser_git_url_constructed_correctly(tmp_path: Path) -> None:
    """ManifestParser builds release.git_url as '<project>/_git/<repo>'."""
    content = (
        "name= openssl\n"
        "versions.component= 1.0\n"
        "versions.platform= 2.0-tech\n"
        "profiles-1.0-2.0-tech= hw-linux-x86_64-gcc10_2\n"
        "tfs_git_project= DEP_Components\n"
        "git_repo_name= contrib_openssl\n"
    )
    path = write_props(tmp_path, "openssl.properties", content)
    components, _ = ManifestParser(TARGET_PLATFORM).parse([path], excluded=[])
    assert components[0].releases[0].git_url == "DEP_Components/_git/contrib_openssl"


# ===========================================================================
# 2.10 — Missing profiles key for a version pair → no release
# ===========================================================================


def test_manifest_parser_missing_profiles_key_skips_version_pair(
    tmp_path: Path,
) -> None:
    """ManifestParser skips a version pair that has no matching profiles key."""
    content = (
        "name= libfoo\n" "versions.component= 1.0\n" "versions.platform= 2.0-tech\n"
    )
    path = write_props(tmp_path, "libfoo.properties", content)
    components, _ = ManifestParser(TARGET_PLATFORM).parse([path], excluded=[])
    assert len(components) == 0


# ===========================================================================
# 2.11 — Multiple files parsed → results accumulated
# ===========================================================================


def test_manifest_parser_multiple_files_accumulated(tmp_path: Path) -> None:
    """ManifestParser accumulates components from multiple valid files."""
    path_a = write_props(tmp_path, "openssl.properties", VALID_SINGLE_CONTENT)
    path_b = write_props(tmp_path, "patchelf.properties", VALID_PATCHELF_CONTENT)
    components, _ = ManifestParser(TARGET_PLATFORM).parse([path_a, path_b], excluded=[])
    assert len(components) == 2


# ===========================================================================
# 2.12 — Real openssl.properties parses correctly (uses resources_dir)
# ===========================================================================


def test_manifest_parser_parses_real_openssl_file(resources_dir: Path) -> None:
    """ManifestParser correctly parses the real openssl.properties resource file."""
    props_file = resources_dir / "manifests" / "openssl.properties"
    components, warnings = ManifestParser(TARGET_PLATFORM).parse(
        [props_file], excluded=[]
    )
    names = [c.name for c in components]
    assert "openssl" in names
