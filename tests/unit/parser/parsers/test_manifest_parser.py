"""Unit tests for autodoc.parser.parsers.manifest_parser.ManifestParser.

Real .properties files are loaded from the resources/manifests/ fixture directory.
Inline hand-crafted property strings are used only for edge-case / invalid-input tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autodoc.parser.parsers.manifest_parser import ManifestParser

TARGET_PLATFORM: str = "2.0"
TFS_COLLECTION_URL: str = "https://tfs.example.com"


def write_props(tmp_path: Path, filename: str, content: str) -> Path:
    """Write content to a .properties file in tmp_path and return the path."""
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def all_real_properties(real_manifests_dir: Path) -> list[Path]:
    """Sorted list of all real .properties files in resources/manifests/."""
    return sorted(real_manifests_dir.glob("*.properties"))


@pytest.fixture
def parser_20() -> ManifestParser:
    """ManifestParser configured for platform 2.0 with a fake TFS collection URL."""
    return ManifestParser(
        target_platform=TARGET_PLATFORM,
        tfs_collection_url=TFS_COLLECTION_URL,
    )


# ---------------------------------------------------------------------------
# Real-data tests
# ---------------------------------------------------------------------------


def test_parser_returns_correct_component_count(
    parser_20: ManifestParser,
    all_real_properties: list[Path],
) -> None:
    """parse() with all real files returns at least 5 component names."""
    components, _ = parser_20.parse(
        all_real_properties, component_names=[], filter_mode="exclude"
    )
    assert len(components) >= 5


def test_parser_patchelf_two_versions_same_channel(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """patchelf has exactly 2 releases, both channel=='tech', versions 0.16.1 and 0.18.0."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "patchelf.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    assert len(components) == 1
    comp = components[0]
    assert comp.name == "patchelf"
    assert len(comp.releases) == 2
    assert {r.channel for r in comp.releases} == {"tech"}
    assert {r.version for r in comp.releases} == {"0.16.1", "0.18.0"}


def test_parser_nlohmann_json_multiple_releases(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """nlohmann_json has at least 2 releases; one channel=='slow', one channel=='fast'."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "nlohmann_json.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    assert len(components) == 1
    releases = components[0].releases
    assert len(releases) >= 2
    channels = {r.channel for r in releases}
    assert "slow" in channels
    assert "fast" in channels


def test_parser_apr_single_release_fast_channel(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """apr has exactly 1 release with version=='1.7.6' and channel=='fast'."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "apr.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    assert len(components) == 1
    assert components[0].name == "apr"
    assert len(components[0].releases) == 1
    rel = components[0].releases[0]
    assert rel.version == "1.7.6"
    assert rel.channel == "fast"


def test_parser_libnetfilter_queue_prg_quant_project(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """libnetfilter_queue component has git_project=='PRG_Quant' (non-standard project)."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "libnetfilter_queue.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    assert len(components) == 1
    assert components[0].git_project == "PRG_Quant"


def test_parser_sqlite3_many_profiles(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """sqlite3 release 3.51.2/fast has at least 10 profile_builds."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "sqlite3.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    assert len(components) == 1
    fast_release = next(
        (r for r in components[0].releases if r.version == "3.51.2" and r.channel == "fast"),
        None,
    )
    assert fast_release is not None
    assert len(fast_release.profile_builds) >= 10


def test_parser_profile_builds_populated_as_skeletons(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """Every ProfileBuild from parsing has exists=False and variants==[] (bare skeletons)."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "apr.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    for comp in components:
        for rel in comp.releases:
            for pb in rel.profile_builds:
                assert pb.exists is False
                assert pb.variants == []


def test_parser_filter_mode_include(
    parser_20: ManifestParser,
    all_real_properties: list[Path],
) -> None:
    """parse() with filter_mode='include' and component_names=['apr'] returns only apr."""
    components, _ = parser_20.parse(
        all_real_properties, component_names=["apr"], filter_mode="include"
    )
    assert len(components) == 1
    assert components[0].name == "apr"


def test_parser_filter_mode_exclude(
    parser_20: ManifestParser,
    all_real_properties: list[Path],
) -> None:
    """parse() with filter_mode='exclude' and component_names=['apr'] omits apr from results."""
    components, _ = parser_20.parse(
        all_real_properties, component_names=["apr"], filter_mode="exclude"
    )
    names = [c.name for c in components]
    assert "apr" not in names


def test_parser_git_url_contains_tfs_collection_url(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """release.git_url starts with the configured TFS collection URL."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "apr.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    for rel in components[0].releases:
        assert rel.git_url.startswith(TFS_COLLECTION_URL)


def test_parser_invalid_properties_skipped_with_warning(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
    tmp_path: Path,
) -> None:
    """A garbage text file alongside valid ones still yields valid components from good files."""
    bad_file = write_props(tmp_path, "garbage.properties", "not valid properties!!!")
    good_file = real_manifests_dir / "apr.properties"
    components, _ = parser_20.parse(
        [good_file, bad_file], component_names=[], filter_mode="exclude"
    )
    names = [c.name for c in components]
    assert "apr" in names
    assert len(components) >= 1


# ---------------------------------------------------------------------------
# Edge-case / invalid-input tests (inline strings appropriate)
# ---------------------------------------------------------------------------


def test_manifest_parser_skips_file_without_name(tmp_path: Path) -> None:
    """ManifestParser silently skips a .properties file that has no 'name' key."""
    path = write_props(tmp_path, "noname.properties", "description= test\n")
    components, warnings = ManifestParser(TARGET_PLATFORM).parse(
        [path], component_names=[], filter_mode="exclude"
    )
    assert len(components) == 0
    assert len(warnings) == 0


def test_manifest_parser_missing_file_produces_warning() -> None:
    """ManifestParser records a warning and returns no components for a nonexistent file."""
    missing = Path("nonexistent.properties")
    components, warnings = ManifestParser(TARGET_PLATFORM).parse(
        [missing], component_names=[], filter_mode="exclude"
    )
    assert len(components) == 0
    assert len(warnings) == 1


def test_manifest_parser_platform_mismatch_no_release(tmp_path: Path) -> None:
    """ManifestParser returns no components when all platform versions mismatch the target."""
    content = (
        "name= libfoo\n"
        "versions.component= 1.0\n"
        "versions.platform= 1.0-tech\n"
        "profiles-1.0-1.0-tech= hw-linux-x86_64-gcc10_2\n"
    )
    path = write_props(tmp_path, "libfoo.properties", content)
    components, _ = ManifestParser(TARGET_PLATFORM).parse(
        [path], component_names=[], filter_mode="exclude"
    )
    assert len(components) == 0


def test_manifest_parser_channel_extracted_from_platform_suffix(tmp_path: Path) -> None:
    """ManifestParser sets release.channel to the part after the first '-' in the platform version."""
    content = (
        "name= libfoo\n"
        "versions.component= 1.0\n"
        "versions.platform= 2.0-fast\n"
        "profiles-1.0-2.0-fast= hw-linux-x86_64-gcc10_2\n"
    )
    path = write_props(tmp_path, "libfoo.properties", content)
    components, _ = ManifestParser(TARGET_PLATFORM).parse(
        [path], component_names=[], filter_mode="exclude"
    )
    assert components[0].releases[0].channel == "fast"


def test_manifest_parser_platform_without_suffix_empty_channel(tmp_path: Path) -> None:
    """ManifestParser sets release.channel to '' when the platform version has no '-' suffix."""
    content = (
        "name= libfoo\n"
        "versions.component= 1.0\n"
        "versions.platform= 2.0\n"
        "profiles-1.0-2.0= hw-linux-x86_64-gcc10_2\n"
    )
    path = write_props(tmp_path, "libfoo.properties", content)
    components, _ = ManifestParser(TARGET_PLATFORM).parse(
        [path], component_names=[], filter_mode="exclude"
    )
    assert components[0].releases[0].channel == ""


def test_manifest_parser_missing_profiles_key_skips_version_pair(tmp_path: Path) -> None:
    """ManifestParser skips a version pair for which no matching profiles key exists."""
    content = (
        "name= libfoo\n"
        "versions.component= 1.0\n"
        "versions.platform= 2.0-tech\n"
    )
    path = write_props(tmp_path, "libfoo.properties", content)
    components, _ = ManifestParser(TARGET_PLATFORM).parse(
        [path], component_names=[], filter_mode="exclude"
    )
    assert len(components) == 0


def test_manifest_parser_git_url_constructed_correctly(tmp_path: Path) -> None:
    """ManifestParser builds release.git_url starting with tfs_collection_url when set."""
    content = (
        "name= openssl\n"
        "versions.component= 1.0\n"
        "versions.platform= 2.0-tech\n"
        "profiles-1.0-2.0-tech= hw-linux-x86_64-gcc10_2\n"
        "tfs_git_project= DEP_Components\n"
        "git_repo_name= contrib_openssl\n"
    )
    path = write_props(tmp_path, "openssl.properties", content)
    components, _ = ManifestParser(
        TARGET_PLATFORM, tfs_collection_url=TFS_COLLECTION_URL
    ).parse([path], component_names=[], filter_mode="exclude")
    assert components[0].releases[0].git_url.startswith(TFS_COLLECTION_URL)


def test_manifest_parser_include_mode_empty_list_returns_all(tmp_path: Path) -> None:
    """filter_mode='include' with an empty components list returns ALL components.

    Intentional no-filter semantics: empty include == filter not active == return all.
    See the source comment in manifest_parser.py. If this changes, update both.
    """
    path_a = write_props(
        tmp_path,
        "openssl.properties",
        "name= openssl\nversions.component= 1.0\nversions.platform= 2.0-tech\nprofiles-1.0-2.0-tech= hw-linux-x86_64-gcc10_2\n",
    )
    path_b = write_props(
        tmp_path,
        "libfoo.properties",
        "name= libfoo\nversions.component= 1.0\nversions.platform= 2.0-tech\nprofiles-1.0-2.0-tech= hw-linux-x86_64-gcc10_2\n",
    )
    components, _ = ManifestParser(TARGET_PLATFORM).parse(
        [path_a, path_b], component_names=[], filter_mode="include"
    )
    assert len(components) == 2


def test_manifest_parser_exact_match_does_not_affect_similar_names(tmp_path: Path) -> None:
    """Exact-match filtering: excluding 'sqlite3' must not affect 'sqlite3_ext'."""
    sqlite3_content = (
        "name= sqlite3\n"
        "versions.component= 3.43.0\n"
        "versions.platform= 2.0-tech\n"
        "profiles-3.43.0-2.0-tech= hw-linux-x86_64-gcc10_2\n"
    )
    sqlite3_ext_content = (
        "name= sqlite3_ext\n"
        "versions.component= 3.43.0\n"
        "versions.platform= 2.0-tech\n"
        "profiles-3.43.0-2.0-tech= hw-linux-x86_64-gcc10_2\n"
    )
    path_a = write_props(tmp_path, "sqlite3.properties", sqlite3_content)
    path_b = write_props(tmp_path, "sqlite3_ext.properties", sqlite3_ext_content)
    components, _ = ManifestParser(TARGET_PLATFORM).parse(
        [path_a, path_b], component_names=["sqlite3"], filter_mode="exclude"
    )
    assert len(components) == 1
    assert components[0].name == "sqlite3_ext"


def test_manifest_parser_parses_real_openssl_file(resources_dir: Path) -> None:
    """ManifestParser correctly parses the real openssl.properties resource file."""
    props_file = resources_dir / "manifests" / "openssl.properties"
    components, warnings = ManifestParser(TARGET_PLATFORM).parse(
        [props_file], component_names=[], filter_mode="exclude"
    )
    names = [c.name for c in components]
    assert "openssl" in names


# ---------------------------------------------------------------------------
# UC-M-1: Header-only component, single fast channel
# ---------------------------------------------------------------------------


def test_parser_nlohmann_json_fast_release_has_one_profile(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """nlohmann_json release 3.12.0/fast has exactly 1 profile_build (mobile-windows-x86_64)."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "nlohmann_json.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    fast_release = next(
        (r for r in components[0].releases if r.version == "3.12.0" and r.channel == "fast"),
        None,
    )
    assert fast_release is not None
    assert len(fast_release.profile_builds) == 1
    assert fast_release.profile_builds[0].profile_name == "mobile-windows-x86_64.jinja"


def test_parser_nlohmann_json_profile_builds_are_skeletons(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """All nlohmann_json profile_builds have exists=False and variants==[] after manifest parsing."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "nlohmann_json.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    for rel in components[0].releases:
        for pb in rel.profile_builds:
            assert pb.exists is False
            assert pb.variants == []


# ---------------------------------------------------------------------------
# UC-M-2: Component built purely in one channel (fast)
# ---------------------------------------------------------------------------


def test_parser_apr_has_no_slow_release(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """apr has no release with channel=='slow'; only fast is present."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "apr.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    slow_releases = [r for r in components[0].releases if r.channel == "slow"]
    assert slow_releases == []


def test_parser_apr_profile_count_fast(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """apr 1.7.6/fast has exactly 4 profile_builds
    (crypto_default_gcc_x86_64, hw-linux-x86_64-gcc10_2,
     windows-x86_64-vs2022-mt, windows-x86-vs2022-mt)."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "apr.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    rel = components[0].releases[0]
    assert len(rel.profile_builds) == 4
    profile_names = {pb.profile_name for pb in rel.profile_builds}
    assert "hw-linux-x86_64-gcc10_2" in profile_names
    assert "windows-x86_64-vs2022-mt" in profile_names


# ---------------------------------------------------------------------------
# UC-M-3: Component with two versions in one channel (tech)
# ---------------------------------------------------------------------------


def test_parser_patchelf_both_versions_have_same_profiles(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """Both patchelf releases share the same set of profile names (6 profiles each)."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "patchelf.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    releases = components[0].releases
    profile_sets = [
        frozenset(pb.profile_name for pb in rel.profile_builds) for rel in releases
    ]
    assert profile_sets[0] == profile_sets[1]
    assert len(profile_sets[0]) == 6


def test_parser_patchelf_no_fast_or_slow_channel(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """patchelf has no releases with channel 'fast' or 'slow' — only 'tech'."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "patchelf.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    non_tech = [r for r in components[0].releases if r.channel != "tech"]
    assert non_tech == []


# ---------------------------------------------------------------------------
# UC-M-4: Standard component built in two channels (fast + slow)
# ---------------------------------------------------------------------------


def test_parser_sqlite3_has_both_fast_and_slow_releases(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """sqlite3 produces exactly 2 releases for platform 2.0: one fast, one slow."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "sqlite3.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    assert len(components) == 1
    channels = {r.channel for r in components[0].releases}
    assert channels == {"fast", "slow"}
    assert len(components[0].releases) == 2


def test_parser_sqlite3_slow_release_version_and_profiles(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """sqlite3 slow release is version 3.34.1 and has hw-linux-* profiles only."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "sqlite3.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    slow_rel = next(r for r in components[0].releases if r.channel == "slow")
    assert slow_rel.version == "3.34.1"
    assert len(slow_rel.profile_builds) >= 2
    profile_names = {pb.profile_name for pb in slow_rel.profile_builds}
    assert any("hw-linux" in p or "instrumented" in p for p in profile_names)


def test_parser_sqlite3_fast_and_slow_different_versions(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """sqlite3 fast and slow releases carry different component versions."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "sqlite3.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    versions = {r.version for r in components[0].releases}
    assert len(versions) == 2


# ---------------------------------------------------------------------------
# UC-M-5: Component from another team's TFS repository (read-only access)
# ---------------------------------------------------------------------------


def test_parser_libnetfilter_queue_git_url_points_to_prg_quant(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """libnetfilter_queue git_url contains 'PRG_Quant' — the external team project."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "libnetfilter_queue.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    assert any("PRG_Quant" in r.git_url for r in components[0].releases)


def test_parser_libnetfilter_queue_single_slow_release_for_platform_20(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """libnetfilter_queue has exactly 1 release for platform 2.0 (slow channel)."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "libnetfilter_queue.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    assert len(components[0].releases) == 1
    assert components[0].releases[0].channel == "slow"
    assert components[0].releases[0].version == "1.0.5"


def test_parser_libnetfilter_queue_slow_has_hw_linux_profiles(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """libnetfilter_queue 1.0.5/slow has 4 hw-linux profile_builds."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "libnetfilter_queue.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    pb_names = {pb.profile_name for pb in components[0].releases[0].profile_builds}
    assert "hw-linux-armv7-gcc10_2" in pb_names
    assert "hw-linux-armv8-gcc10_2" in pb_names
    assert "hw-linux-x86_64-gcc10_2" in pb_names
    assert "linux-x86_64-gcc10_2-instrumented" in pb_names
