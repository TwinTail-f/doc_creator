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


@pytest.mark.integration
def test_parser_returns_correct_component_count(
    parser_20: ManifestParser,
    all_real_properties: list[Path],
) -> None:
    """parse() with all real files returns at least 5 component names."""
    components, _ = parser_20.parse(
        all_real_properties, component_names=[], filter_mode="exclude"
    )
    assert len(components) >= 5


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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
        (
            r
            for r in components[0].releases
            if r.version == "3.51.2" and r.channel == "fast"
        ),
        None,
    )
    assert fast_release is not None
    assert len(fast_release.profile_builds) >= 10


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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


@pytest.mark.business_logic
def test_parser_git_url_contains_tfs_collection_url(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """component.git_url starts with the configured TFS collection URL."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "apr.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    assert components[0].git_url.startswith(TFS_COLLECTION_URL)


@pytest.mark.business_logic
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


@pytest.mark.business_logic
def test_manifest_parser_skips_file_without_name(tmp_path: Path) -> None:
    """ManifestParser silently skips a .properties file that has no 'name' key."""
    path = write_props(tmp_path, "noname.properties", "description= test\n")
    components, warnings = ManifestParser(TARGET_PLATFORM).parse(
        [path], component_names=[], filter_mode="exclude"
    )
    assert len(components) == 0
    assert len(warnings) == 0


@pytest.mark.business_logic
def test_manifest_parser_missing_file_produces_warning() -> None:
    """ManifestParser records a warning and returns no components for a nonexistent file."""
    missing = Path("nonexistent.properties")
    components, warnings = ManifestParser(TARGET_PLATFORM).parse(
        [missing], component_names=[], filter_mode="exclude"
    )
    assert len(components) == 0
    assert len(warnings) == 1


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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


@pytest.mark.business_logic
def test_manifest_parser_missing_profiles_key_skips_version_pair(
    tmp_path: Path,
) -> None:
    """ManifestParser skips a version pair for which no matching profiles key exists."""
    content = (
        "name= libfoo\n" "versions.component= 1.0\n" "versions.platform= 2.0-tech\n"
    )
    path = write_props(tmp_path, "libfoo.properties", content)
    components, _ = ManifestParser(TARGET_PLATFORM).parse(
        [path], component_names=[], filter_mode="exclude"
    )
    assert len(components) == 0


@pytest.mark.business_logic
def test_manifest_parser_git_url_constructed_correctly(tmp_path: Path) -> None:
    """ManifestParser builds component.git_url starting with tfs_collection_url when set."""
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
    assert components[0].git_url.startswith(TFS_COLLECTION_URL)


@pytest.mark.business_logic
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


@pytest.mark.business_logic
def test_manifest_parser_exact_match_does_not_affect_similar_names(
    tmp_path: Path,
) -> None:
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


@pytest.mark.integration
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


@pytest.mark.business_logic
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
        (
            r
            for r in components[0].releases
            if r.version == "3.12.0" and r.channel == "fast"
        ),
        None,
    )
    assert fast_release is not None
    assert len(fast_release.profile_builds) == 1
    assert fast_release.profile_builds[0].profile_name == "mobile-windows-x86_64.jinja"


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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


@pytest.mark.business_logic
def test_parser_libnetfilter_queue_git_url_points_to_prg_quant(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """libnetfilter_queue component.git_url contains 'PRG_Quant' — the external team project."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "libnetfilter_queue.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    assert "PRG_Quant" in components[0].git_url


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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


# ===========================================================================
# BL-MP-01 … BL-MP-15  (Part 2 of the test plan)
# ---------------------------------------------------------------------------
# Local helper factories — use the real .properties key names understood by
# ManifestParser._build_releases / _parse_single_file.
# ---------------------------------------------------------------------------


def _write_manifest(tmp_path: Path, name: str, content: str) -> Path:
    """Write a .properties file to *tmp_path* and return its Path.

    Args:
        tmp_path: pytest ``tmp_path`` fixture directory.
        name: Base filename (without extension).
        content: Raw text content for the file.

    Returns:
        Absolute Path to the written file.
    """
    p = tmp_path / f"{name}.properties"
    p.write_text(content, encoding="utf-8")
    return p


def _minimal_manifest(
    comp_name: str = "mylib",
    comp_version: str = "1.0",
    plat_version: str = "2.2-fast",
    profiles: str = "hw-linux-x86_64",
    git_project: str = "MyProject",
    git_repo: str = "mylib",
) -> str:
    """Return a minimal, syntactically valid .properties string.

    Uses the real field names understood by ManifestParser:
    ``versions.component``, ``versions.platform``, ``profiles-{cv}-{pv}``,
    ``tfs_git_project``, ``git_repo_name``.

    Args:
        comp_name: Component name (``name`` property).
        comp_version: Component version string.
        plat_version: Platform version string, e.g. ``"2.2-fast"`` or ``"2.2"``.
        profiles: Comma-separated profile names for the release.
        git_project: TFS project name.
        git_repo: Git repository name.

    Returns:
        Multi-line string suitable for writing to a .properties file.
    """
    return (
        f"name={comp_name}\n"
        f"description=Test component\n"
        f"tfs_git_project={git_project}\n"
        f"git_repo_name={git_repo}\n"
        f"versions.component={comp_version}\n"
        f"versions.platform={plat_version}\n"
        f"profiles-{comp_version}-{plat_version}={profiles}\n"
    )


# ---------------------------------------------------------------------------
# BL-MP-01  channel suffix "fast"
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_channel_suffix_fast_extracted(tmp_path: Path) -> None:
    """Verify that a platform string ending with "-fast" yields channel="fast".

    Business Rule (BL-MP-01): The channel is the last hyphen-delimited segment
    of the platform string.  "2.2-fast" → channel="fast".

    Preconditions:
        - .properties file with ``versions.platform=2.2-fast``.
        - ManifestParser configured with ``target_platform="2.2"``.

    Steps:
        1. Write a minimal manifest and parse it.

    Expected Result:
        - Exactly 1 component is returned.
        - ``components[0].releases[0].channel == "fast"``.
    """
    f = _write_manifest(tmp_path, "mylib", _minimal_manifest(plat_version="2.2-fast"))
    parser = ManifestParser(target_platform="2.2", tfs_collection_url="http://tfs")
    components, _ = parser.parse([f], component_names=[], filter_mode="include")

    assert len(components) == 1
    assert components[0].releases[0].channel == "fast"


# ---------------------------------------------------------------------------
# BL-MP-02  channel suffix "slow"
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_channel_suffix_slow_extracted(tmp_path: Path) -> None:
    """Verify that a platform string ending with "-slow" yields channel="slow".

    Business Rule (BL-MP-02): Same rule as BL-MP-01 — the suffix after the last
    hyphen is the channel.  This test confirms the rule is not specific to "fast".

    Preconditions:
        - .properties file with ``versions.platform=2.2-slow``.

    Steps:
        1. Write manifest, parse with ``target_platform="2.2"``.

    Expected Result:
        - ``components[0].releases[0].channel == "slow"``.
    """
    content = _minimal_manifest(plat_version="2.2-slow")
    f = _write_manifest(tmp_path, "mylib", content)
    parser = ManifestParser(target_platform="2.2", tfs_collection_url="http://tfs")
    components, _ = parser.parse([f], component_names=[], filter_mode="include")

    assert components[0].releases[0].channel == "slow"


# ---------------------------------------------------------------------------
# BL-MP-03  no suffix → empty channel
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_channel_no_suffix_gives_empty_string(tmp_path: Path) -> None:
    """Verify that a platform string with no hyphen-suffix yields channel="".

    Business Rule (BL-MP-03): When the platform string contains no hyphen
    (e.g. "2.2" with no channel qualifier), the channel is the empty string.
    OptionsParser treats an empty channel as the global channel fallback.

    Preconditions:
        - .properties file with ``versions.platform=2.2`` (no suffix).

    Steps:
        1. Write manifest, parse with ``target_platform="2.2"``.

    Expected Result:
        - ``components[0].releases[0].channel == ""``.
    """
    content = _minimal_manifest(plat_version="2.2")
    # profiles key must also use the bare platform version
    content = (
        "name=mylib\ndescription=Test\ntfs_git_project=P\ngit_repo_name=r\n"
        "versions.component=1.0\nversions.platform=2.2\n"
        "profiles-1.0-2.2=hw-linux-x86_64\n"
    )
    f = _write_manifest(tmp_path, "mylib", content)
    parser = ManifestParser(target_platform="2.2", tfs_collection_url="http://tfs")
    components, _ = parser.parse([f], component_names=[], filter_mode="include")

    assert components[0].releases[0].channel == ""


# ---------------------------------------------------------------------------
# BL-MP-04  multiple hyphens — last segment is the channel
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_channel_multi_dash_last_segment_is_channel(tmp_path: Path) -> None:
    """Verify that for multi-hyphen platform strings, only the last segment is the channel.

    Business Rule (BL-MP-04): "2.2-extra-slow" → channel="slow".  Intermediate
    segments are treated as part of the platform identifier, not the channel.
    Version numbers embedded in the prefix must not appear in channel.

    Preconditions:
        - .properties file with ``versions.platform=2.2-extra-slow``.
        - ManifestParser configured with ``target_platform="2.2"``.

    Steps:
        1. Write manifest with the multi-hyphen platform string.
        2. Parse and inspect the resulting Release.

    Expected Result:
        - ``release.channel == "slow"``.
        - The string ``"2"`` is not present in ``release.channel``.
    """
    content = (
        "name=mylib\ndescription=Test\ntfs_git_project=P\ngit_repo_name=r\n"
        "versions.component=1.0\nversions.platform=2.2-extra-slow\n"
        "profiles-1.0-2.2-extra-slow=hw-linux-x86_64\n"
    )
    f = _write_manifest(tmp_path, "mylib", content)
    parser = ManifestParser(target_platform="2.2", tfs_collection_url="http://tfs")
    components, _ = parser.parse([f], component_names=[], filter_mode="include")

    release = components[0].releases[0]
    assert release.channel == "slow"
    assert "2" not in release.channel


# ---------------------------------------------------------------------------
# BL-MP-05  include filter — exact name match only
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_include_filter_exact_match_only(tmp_path: Path) -> None:
    """Verify that filter_mode="include" matches component names exactly.

    Business Rule (BL-MP-05): Only the component whose name is an exact member of
    ``component_names`` is included.  Substrings and similar names are excluded.
    "openssl-extra" must NOT be returned when the filter is ["openssl"].

    Preconditions:
        - Two .properties files: one for "openssl" and one for "openssl-extra".
        - Filter: ``component_names=["openssl"]``, ``filter_mode="include"``.

    Steps:
        1. Write both manifests and parse the directory.

    Expected Result:
        - Exactly 1 component returned.
        - ``components[0].name == "openssl"``.
    """
    for name in ["openssl", "openssl-extra"]:
        content = _minimal_manifest(
            comp_name=name, git_project="P", git_repo=name, plat_version="2.2-fast"
        )
        _write_manifest(tmp_path, name, content)

    parser = ManifestParser(target_platform="2.2")
    files = list(tmp_path.glob("*.properties"))
    components, _ = parser.parse(
        files, component_names=["openssl"], filter_mode="include"
    )

    assert len(components) == 1
    assert components[0].name == "openssl"


# ---------------------------------------------------------------------------
# BL-MP-06  exclude filter — exact name match only
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_exclude_filter_exact_match_only(tmp_path: Path) -> None:
    """Verify that filter_mode="exclude" excludes only the named component exactly.

    Business Rule (BL-MP-06): Only "openssl" is excluded; "openssl-extra" is kept
    because the filter compares names for exact equality, not substring membership.

    Preconditions:
        - Two .properties files: "openssl" and "openssl-extra".
        - Filter: ``component_names=["openssl"]``, ``filter_mode="exclude"``.

    Steps:
        1. Write both manifests and parse.

    Expected Result:
        - "openssl" is absent from the returned components.
        - "openssl-extra" is present.
    """
    for name in ["openssl", "openssl-extra"]:
        content = _minimal_manifest(
            comp_name=name, git_project="P", git_repo=name, plat_version="2.2-fast"
        )
        _write_manifest(tmp_path, name, content)

    parser = ManifestParser(target_platform="2.2")
    files = list(tmp_path.glob("*.properties"))
    components, _ = parser.parse(
        files, component_names=["openssl"], filter_mode="exclude"
    )

    names = {c.name for c in components}
    assert "openssl" not in names
    assert "openssl-extra" in names


# ---------------------------------------------------------------------------
# BL-MP-07  include + empty list = no filtering
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_include_empty_list_returns_all_components(tmp_path: Path) -> None:
    """Verify that filter_mode="include" with an empty names list returns all components.

    Business Rule (BL-MP-07): An empty ``component_names`` list in "include" mode
    means "include everything" — the filter is effectively disabled.  This is a
    deliberate design choice; to include nothing, pass a non-matching non-empty list.

    Preconditions:
        - Three .properties files: "libA", "libB", "libC".
        - Filter: ``component_names=[]``, ``filter_mode="include"``.

    Steps:
        1. Write all three manifests and parse with the empty include list.

    Expected Result:
        - All 3 components are returned.
    """
    for name in ["libA", "libB", "libC"]:
        content = _minimal_manifest(
            comp_name=name, git_project="P", git_repo=name, plat_version="2.2-fast"
        )
        _write_manifest(tmp_path, name, content)

    parser = ManifestParser(target_platform="2.2")
    files = list(tmp_path.glob("*.properties"))
    components, _ = parser.parse(files, component_names=[], filter_mode="include")

    assert len(components) == 3


# ---------------------------------------------------------------------------
# BL-MP-08  exclude + empty list = no filtering
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_exclude_empty_list_returns_all_components(tmp_path: Path) -> None:
    """Verify that filter_mode="exclude" with an empty names list returns all components.

    Business Rule (BL-MP-08): An empty ``component_names`` list in "exclude" mode
    means "exclude nothing" — all components from every manifest file are returned.

    Preconditions:
        - Two .properties files: "libA", "libB".
        - Filter: ``component_names=[]``, ``filter_mode="exclude"``.

    Steps:
        1. Write both manifests and parse.

    Expected Result:
        - Both components are returned (total count == 2).
    """
    for name in ["libA", "libB"]:
        content = _minimal_manifest(
            comp_name=name, git_project="P", git_repo=name, plat_version="2.2-fast"
        )
        _write_manifest(tmp_path, name, content)

    parser = ManifestParser(target_platform="2.2")
    files = list(tmp_path.glob("*.properties"))
    components, _ = parser.parse(files, component_names=[], filter_mode="exclude")

    assert len(components) == 2


# ---------------------------------------------------------------------------
# BL-MP-09  ProfileBuild skeletons created from profiles-* field
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_profile_builds_created_from_profiles_property(tmp_path: Path) -> None:
    """Verify that ManifestParser creates ProfileBuild skeletons for each profile name.

    Business Rule (BL-MP-09): The parser reads the ``profiles-{cv}-{pv}`` property
    and creates one ProfileBuild skeleton for each comma-separated profile name listed
    in that property.

    Preconditions:
        - Manifest with two profile names: "hw-linux-x86_64" and "hw-linux-armv8".

    Steps:
        1. Write manifest and parse.
        2. Inspect ``releases[0].profile_builds``.

    Expected Result:
        - Two ProfileBuilds are created.
        - Both profile names are present.
    """
    content = (
        "name=mylib\ndescription=Test\ntfs_git_project=P\ngit_repo_name=r\n"
        "versions.component=1.0\nversions.platform=2.2-fast\n"
        "profiles-1.0-2.2-fast=hw-linux-x86_64, hw-linux-armv8\n"
    )
    f = _write_manifest(tmp_path, "mylib", content)
    parser = ManifestParser(target_platform="2.2")
    components, _ = parser.parse([f], component_names=[], filter_mode="include")

    pbs = components[0].releases[0].profile_builds
    profile_names = {pb.profile_name for pb in pbs}
    assert "hw-linux-x86_64" in profile_names
    assert "hw-linux-armv8" in profile_names
    assert len(pbs) == 2


# ---------------------------------------------------------------------------
# BL-MP-10  all ProfileBuild skeletons have exists=False
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_profile_builds_all_have_exists_false(tmp_path: Path) -> None:
    """Verify that all ProfileBuild objects created by ManifestParser have exists=False.

    Business Rule (BL-MP-10): ProfileBuilds produced by ManifestParser are skeletons
    only.  Their ``exists`` flag is always ``False`` at this stage — package existence
    will be determined later by ConanEnrichStep querying Artifactory.

    Preconditions:
        - Manifest with two profiles: "hw-linux-x86_64" and "hw-linux-armv8".

    Steps:
        1. Parse manifest and iterate over all returned ProfileBuilds.

    Expected Result:
        - Every ProfileBuild has ``exists is False``.
    """
    content = (
        "name=mylib\ndescription=Test\ntfs_git_project=P\ngit_repo_name=r\n"
        "versions.component=1.0\nversions.platform=2.2-fast\n"
        "profiles-1.0-2.2-fast=hw-linux-x86_64, hw-linux-armv8\n"
    )
    f = _write_manifest(tmp_path, "mylib", content)
    parser = ManifestParser(target_platform="2.2")
    components, _ = parser.parse([f], component_names=[], filter_mode="include")

    for pb in components[0].releases[0].profile_builds:
        assert pb.exists is False


# ---------------------------------------------------------------------------
# BL-MP-11  all ProfileBuild skeletons have variants=[]
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_profile_builds_all_have_empty_variants(tmp_path: Path) -> None:
    """Verify that all ProfileBuild skeletons produced by ManifestParser have variants=[].

    Business Rule (BL-MP-11): ManifestParser does not query Conan or Artifactory,
    so it cannot populate ``variants``.  All newly created ProfileBuilds carry an
    empty variants list.  DataEnricher.apply_conan_results() fills this later.

    Preconditions:
        - Manifest with one profile: "hw-linux-x86_64".

    Steps:
        1. Parse manifest and inspect each ProfileBuild.

    Expected Result:
        - Every ProfileBuild has ``variants == []``.
    """
    content = _minimal_manifest(plat_version="2.2-fast")
    f = _write_manifest(tmp_path, "mylib", content)
    parser = ManifestParser(target_platform="2.2")
    components, _ = parser.parse([f], component_names=[], filter_mode="include")

    for pb in components[0].releases[0].profile_builds:
        assert pb.variants == []


# ---------------------------------------------------------------------------
# BL-MP-12  profile names exactly match the manifest field
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_profile_build_names_match_manifest_profile_list_exactly(
    tmp_path: Path,
) -> None:
    """Verify that ProfileBuild.profile_name values exactly equal the manifest entries.

    Business Rule (BL-MP-12): No name transformation (trimming aside) is applied to
    profile name strings.  The value recorded in ``ProfileBuild.profile_name`` must
    be identical to the token from the ``profiles-*`` property.

    Preconditions:
        - Manifest with two profiles: "hw-linux-x86_64-gcc12_3" and "hw-win-msvc2022".

    Steps:
        1. Parse manifest and collect profile_name values.

    Expected Result:
        - The name set is exactly ``{"hw-linux-x86_64-gcc12_3", "hw-win-msvc2022"}``.
    """
    content = (
        "name=mylib\ndescription=Test\ntfs_git_project=P\ngit_repo_name=r\n"
        "versions.component=1.0\nversions.platform=2.2-fast\n"
        "profiles-1.0-2.2-fast=hw-linux-x86_64-gcc12_3, hw-win-msvc2022\n"
    )
    f = _write_manifest(tmp_path, "mylib", content)
    parser = ManifestParser(target_platform="2.2")
    components, _ = parser.parse([f], component_names=[], filter_mode="include")

    names = {pb.profile_name for pb in components[0].releases[0].profile_builds}
    assert names == {"hw-linux-x86_64-gcc12_3", "hw-win-msvc2022"}


# ---------------------------------------------------------------------------
# BL-MP-13  git_url is set on Component (after model migration)
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_git_url_set_on_component_not_release(tmp_path: Path) -> None:
    """Verify that git_url is a Component-level field, not a Release-level field.

    Business Rule (BL-MP-13, post-migration): All releases of a component share the
    same source repository, so git_url belongs to Component.  ManifestParser must
    set ``component.git_url`` exactly once from the manifest's ``tfs_git_project``
    and ``git_repo_name`` fields.

    Preconditions:
        - Manifest with two releases (versions 1.0 and 2.0).
        - ``tfs_git_project=MyProject``, ``git_repo_name=mylib-repo``.

    Steps:
        1. Parse the manifest.
        2. Verify that ``comp.git_url`` contains the repository name.
        3. Verify that both releases are present (git_url is not per-release).

    Expected Result:
        - ``hasattr(comp, "git_url")`` is True.
        - ``"mylib-repo"`` appears in ``comp.git_url``.
        - ``len(comp.releases) == 2``.
    """
    content = (
        "name=mylib\ndescription=Test\n"
        "tfs_git_project=MyProject\ngit_repo_name=mylib-repo\n"
        "versions.component=1.0, 2.0\nversions.platform=2.2-fast\n"
        "profiles-1.0-2.2-fast=hw-linux-x86_64\n"
        "profiles-2.0-2.2-fast=hw-linux-x86_64\n"
    )
    f = _write_manifest(tmp_path, "mylib", content)
    parser = ManifestParser(target_platform="2.2", tfs_collection_url="http://tfs/col")
    components, _ = parser.parse([f], component_names=[], filter_mode="include")

    comp = components[0]
    assert hasattr(comp, "git_url"), "git_url must be a Component field after migration"
    assert "mylib-repo" in comp.git_url
    assert len(comp.releases) == 2


# ---------------------------------------------------------------------------
# BL-MP-14  git_url format is TFS Git URL
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_git_url_format_is_tfs_git_format(tmp_path: Path) -> None:
    """Verify that Component.git_url is formatted as a well-formed TFS Git URL.

    Business Rule (BL-MP-14): The URL follows the pattern
    ``{tfs_collection_url}/{git_project}/_git/{git_repo}`` with no duplicate or
    trailing slashes.

    Preconditions:
        - ``tfs_collection_url="http://tfs.example.com/DefaultCollection"``.
        - ``tfs_git_project=PlatformTeam``, ``git_repo_name=mylib``.

    Steps:
        1. Parse the manifest.
        2. Compare ``comp.git_url`` against the expected URL string.

    Expected Result:
        - ``comp.git_url == "http://tfs.example.com/DefaultCollection/PlatformTeam/_git/mylib"``.
    """
    content = (
        "name=mylib\ndescription=Test\n"
        "tfs_git_project=PlatformTeam\ngit_repo_name=mylib\n"
        "versions.component=1.0\nversions.platform=2.2-fast\n"
        "profiles-1.0-2.2-fast=hw-linux-x86_64\n"
    )
    f = _write_manifest(tmp_path, "mylib", content)
    parser = ManifestParser(
        target_platform="2.2",
        tfs_collection_url="http://tfs.example.com/DefaultCollection",
    )
    components, _ = parser.parse([f], component_names=[], filter_mode="include")

    expected_url = "http://tfs.example.com/DefaultCollection/PlatformTeam/_git/mylib"
    assert components[0].git_url == expected_url


# ---------------------------------------------------------------------------
# BL-MP-15  only target-platform releases are included
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_only_target_platform_releases_included(tmp_path: Path) -> None:
    """Verify that ManifestParser returns only releases matching the target platform.

    Business Rule (BL-MP-15): When ``target_platform="2.2"``, releases for
    platforms "2.1" and "2.3" must be silently ignored.  Only the release whose
    platform version starts with "2.2" (or equals "2.2") is returned.

    Preconditions:
        - Manifest lists three component+platform combinations:
          version 1.0 on platform 2.1-fast, version 2.0 on 2.2-fast,
          version 3.0 on 2.3-fast.
        - Parser configured with ``target_platform="2.2"``.

    Steps:
        1. Parse the manifest.
        2. Inspect ``components[0].releases``.

    Expected Result:
        - Exactly 1 release is present.
        - ``releases[0].version == "2.0"``.
    """
    content = (
        "name=mylib\ndescription=Test\ntfs_git_project=P\ngit_repo_name=r\n"
        "versions.component=1.0, 2.0, 3.0\n"
        "versions.platform=2.1-fast, 2.2-fast, 2.3-fast\n"
        "profiles-1.0-2.1-fast=hw-linux-x86_64\n"
        "profiles-2.0-2.2-fast=hw-linux-x86_64\n"
        "profiles-3.0-2.3-fast=hw-linux-x86_64\n"
    )
    f = _write_manifest(tmp_path, "mylib", content)
    parser = ManifestParser(target_platform="2.2")
    components, _ = parser.parse([f], component_names=[], filter_mode="include")

    assert len(components[0].releases) == 1
    assert components[0].releases[0].version == "2.0"
