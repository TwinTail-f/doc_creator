"""Unit tests for autodoc.parser.parsers.options_parser.OptionsParser.

Covers: select_ci_prefix, parse_file (real JSON files), pick_options.
Real JSON option files are loaded from the resources/options/ fixture directory.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autodoc.parser.parsers.options_parser import OptionsParser

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

CI_PREFIX_V2: str = "/ci-2.0/"
CI_PREFIX_V16: str = "/ci-1.6/"

PATH_V2_TECH: str = "/repo/ci-2.0/tech/options.json"
PATH_V16_TECH: str = "/repo/ci-1.6/tech/options.json"
PATH_OTHER: str = "/repo/other/options.json"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def options_dir(resources_dir: Path) -> Path:
    """Path to resources/options/ directory containing real JSON option files."""
    return resources_dir / "options"


# ===========================================================================
# select_ci_prefix: /ci-2.0/ preferred over /ci-1.6/
# ===========================================================================


@pytest.mark.business_logic
def test_select_ci_prefix_picks_ci_20_over_16() -> None:
    """select_ci_prefix returns '/ci-2.0/' when both v2 and v1.6 paths are present."""
    paths = [
        "/conan/ci-2.0/options.json",
        "/conan/ci-1.6/options.json",
    ]
    result = OptionsParser.select_ci_prefix(paths)
    assert result == CI_PREFIX_V2


@pytest.mark.business_logic
def test_select_ci_prefix_uses_ci_16_alone() -> None:
    """select_ci_prefix returns '/ci-1.6/' when only ci-1.6 paths are present."""
    paths = ["/conan/ci-1.6/options.json"]
    result = OptionsParser.select_ci_prefix(paths)
    assert result == CI_PREFIX_V16


@pytest.mark.infrastructure
def test_select_ci_prefix_no_match_returns_empty_string() -> None:
    """select_ci_prefix returns '' when no known CI directory is found."""
    result = OptionsParser.select_ci_prefix([PATH_OTHER])
    assert result == ""


@pytest.mark.infrastructure
def test_select_ci_prefix_empty_list_returns_empty_string() -> None:
    """select_ci_prefix returns '' for an empty input list."""
    result = OptionsParser.select_ci_prefix([])
    assert result == ""


# ===========================================================================
# parse_file — real content
# ===========================================================================


@pytest.mark.integration
def test_parse_file_apr_single_option(options_dir: Path) -> None:
    """parse_file on apr_options.json returns a 1-entry dict with 'apr:shared=True'."""
    text = (options_dir / "apr_options.json").read_text(encoding="utf-8")
    channel, cleaned = OptionsParser.parse_file(
        text,
        opt_path="/conan/ci-1.6/options.json",
        ci_prefix=CI_PREFIX_V16,
    )
    # Global file (no sub-directory after ci-prefix) -> channel is None
    assert channel is None
    assert cleaned == {"1": "apr:shared=True"}


@pytest.mark.integration
def test_parse_file_sqlite3_fast_five_options(options_dir: Path) -> None:
    """parse_file on sqlite3_fast_options.json returns a 5-entry dict; key '5' contains 'with_icu'."""
    text = (options_dir / "sqlite3_fast_options.json").read_text(encoding="utf-8")
    channel, cleaned = OptionsParser.parse_file(
        text,
        opt_path="/conan/ci-2.0/fast/options.json",
        ci_prefix=CI_PREFIX_V2,
    )
    assert channel == "fast"
    assert len(cleaned) == 5
    assert "with_icu" in cleaned["5"]


@pytest.mark.integration
def test_parse_file_sqlite3_slow_twelve_options(options_dir: Path) -> None:
    """parse_file on sqlite3_slow_options.json returns a 12-entry dict; key '12' contains 'with_icu'."""
    text = (options_dir / "sqlite3_slow_options.json").read_text(encoding="utf-8")
    channel, cleaned = OptionsParser.parse_file(
        text,
        opt_path="/conan/ci-1.6/slow/options.json",
        ci_prefix=CI_PREFIX_V16,
    )
    assert channel == "slow"
    assert len(cleaned) == 12
    assert "with_icu" in cleaned["12"]


@pytest.mark.integration
def test_parse_file_icu_fast_two_options(options_dir: Path) -> None:
    """parse_file on icu_fast_options.json returns a 2-entry dict; '2' == 'icu:mobile=True'."""
    text = (options_dir / "icu_fast_options.json").read_text(encoding="utf-8")
    channel, cleaned = OptionsParser.parse_file(
        text,
        opt_path="/conan/ci-1.6/fast/options.json",
        ci_prefix=CI_PREFIX_V16,
    )
    assert channel == "fast"
    assert len(cleaned) == 2
    assert cleaned["2"] == "icu:mobile=True"


@pytest.mark.integration
def test_parse_file_nlohmann_single_empty_option(options_dir: Path) -> None:
    """parse_file on nlohmann_json_options.json returns {'1': ''} for a header-only component."""
    text = (options_dir / "nlohmann_json_options.json").read_text(encoding="utf-8")
    channel, cleaned = OptionsParser.parse_file(
        text,
        opt_path="/conan/ci-2.0/options.json",
        ci_prefix=CI_PREFIX_V2,
    )
    assert cleaned == {"1": ""}


# ===========================================================================
# parse_file — edge cases (inline data)
# ===========================================================================


@pytest.mark.infrastructure
def test_parse_file_invalid_json_returns_empty() -> None:
    """parse_file returns (None, {}) when the JSON text cannot be parsed."""
    result = OptionsParser.parse_file(
        "NOT JSON",
        opt_path=PATH_V2_TECH,
        ci_prefix=CI_PREFIX_V2,
    )
    assert result == (None, {})


@pytest.mark.infrastructure
def test_parse_file_empty_json_object() -> None:
    """parse_file returns an empty options dict for '{}' without raising."""
    channel, cleaned = OptionsParser.parse_file(
        "{}",
        opt_path=PATH_V2_TECH,
        ci_prefix=CI_PREFIX_V2,
    )
    assert cleaned == {}


@pytest.mark.infrastructure
def test_parse_file_no_channel_segment_returns_none() -> None:
    """parse_file returns channel=None when the path has no sub-directory after the CI prefix."""
    channel, _ = OptionsParser.parse_file(
        '{"1": "shared=True"}',
        opt_path="/repo/ci-2.0/options.json",
        ci_prefix=CI_PREFIX_V2,
    )
    assert channel is None


@pytest.mark.infrastructure
def test_parse_file_strips_whitespace_from_values() -> None:
    """parse_file strips leading/trailing whitespace from each option value."""
    _, cleaned = OptionsParser.parse_file(
        '{"1": "  shared=True  "}',
        opt_path=PATH_V2_TECH,
        ci_prefix=CI_PREFIX_V2,
    )
    assert cleaned["1"] == "shared=True"


@pytest.mark.infrastructure
def test_parse_file_non_string_values_excluded() -> None:
    """parse_file skips entries whose value is not a string (e.g. integers)."""
    _, cleaned = OptionsParser.parse_file(
        '{"1": "shared=True", "count": 42}',
        opt_path=PATH_V2_TECH,
        ci_prefix=CI_PREFIX_V2,
    )
    assert "1" in cleaned
    assert "count" not in cleaned


# ===========================================================================
# pick_options — channel selection
# ===========================================================================


@pytest.mark.business_logic
def test_pick_options_selects_channel_specific_over_global() -> None:
    """pick_options returns the channel-specific entry when it exists, ignoring global."""
    repo_data = {
        "global": {"1": ""},
        "channels": {"fast": {"1": "", "2": "x=True"}},
    }
    result = OptionsParser.pick_options(repo_data, "fast")
    assert result == {"1": "", "2": "x=True"}


@pytest.mark.business_logic
def test_pick_options_falls_back_to_global_when_no_channel_match() -> None:
    """pick_options returns the global entry when the requested channel is absent."""
    repo_data = {
        "global": {"1": "apr:shared=True"},
        "channels": {},
    }
    result = OptionsParser.pick_options(repo_data, "tech")
    assert result == {"1": "apr:shared=True"}


@pytest.mark.business_logic
def test_pick_options_returns_default_when_no_data() -> None:
    """pick_options returns {'1': ''} when repo_data is empty."""
    result = OptionsParser.pick_options({}, "fast")
    assert result == {"1": ""}


@pytest.mark.business_logic
def test_pick_options_empty_channel_uses_global() -> None:
    """pick_options falls back to global when channel is an empty string."""
    data: dict = {"channels": {"tech": {"1": "x"}}, "global": {"1": "y"}}
    result = OptionsParser.pick_options(data, "")
    assert result == {"1": "y"}


# ===========================================================================
# parse_file: real openssl_options.json (kept for regression)
# ===========================================================================


@pytest.mark.integration
def test_options_parser_parses_real_openssl_options(resources_dir: Path) -> None:
    """OptionsParser.parse_file reads the real openssl options.json and returns the correct mapping."""
    options_file = resources_dir / "options" / "openssl_options.json"
    text = options_file.read_text(encoding="utf-8")
    channel, cleaned = OptionsParser.parse_file(
        text, opt_path="/ci-2.0/trusted/options.json", ci_prefix=CI_PREFIX_V2
    )
    assert channel == "trusted"
    assert "1" in cleaned
    assert cleaned["1"] == ""
    assert "2" in cleaned
    assert cleaned["2"] == "openssl:shared=True"


@pytest.mark.integration
def test_options_parser_parses_zlib_single_empty_option(resources_dir: Path) -> None:
    """OptionsParser.parse_file handles a file with a single empty option without error."""
    options_file = resources_dir / "options" / "zlib_options.json"
    text = options_file.read_text(encoding="utf-8")
    channel, cleaned = OptionsParser.parse_file(
        text, opt_path="/ci-2.0/fast/options.json", ci_prefix=CI_PREFIX_V2
    )
    assert channel == "fast"
    assert "1" in cleaned
    assert cleaned["1"] == ""


# ===========================================================================
# UC-O-1: Only ci-1.6 present (fallback) OR only ci-2.0 present
# ===========================================================================


@pytest.mark.business_logic
def test_select_ci_prefix_uses_ci_20_alone() -> None:
    """select_ci_prefix returns '/ci-2.0/' when only ci-2.0 paths are present (no ci-1.6)."""
    paths = ["/conan/ci-2.0/options.json"]
    result = OptionsParser.select_ci_prefix(paths)
    assert result == CI_PREFIX_V2


@pytest.mark.integration
def test_parse_file_patchelf_ci16_flat_global(options_dir: Path) -> None:
    """patchelf uses ci-1.6/options.json (no channel sub-dir); channel is None, 1 entry."""
    text = (options_dir / "patchelf_options.json").read_text(encoding="utf-8")
    channel, cleaned = OptionsParser.parse_file(
        text,
        opt_path="/conan/ci-1.6/options.json",
        ci_prefix=CI_PREFIX_V16,
    )
    assert channel is None
    assert cleaned == {"1": ""}


@pytest.mark.business_logic
def test_pick_options_tech_channel_falls_back_to_global_ci16() -> None:
    """pick_options with channel='tech' and no 'tech' key returns the global entry (patchelf case)."""
    repo_data = {
        "global": {"1": ""},
        "channels": {},
    }
    result = OptionsParser.pick_options(repo_data, "tech")
    assert result == {"1": ""}


# ===========================================================================
# UC-O-2: ci-2.0 / ci-1.6 with channel sub-directories (fast/slow)
# ===========================================================================


@pytest.mark.business_logic
def test_pick_options_sqlite3_fast_selected_over_slow() -> None:
    """pick_options with channel='fast' picks fast entry, not slow, when both are present."""
    repo_data = {
        "global": None,
        "channels": {
            "fast": {"1": "", "2": "sqlite3:enable_json1=True"},
            "slow": {"1": "", "2": "sqlite3:shared=True"},
        },
    }
    result = OptionsParser.pick_options(repo_data, "fast")
    assert "enable_json1" in result["2"]
    assert "shared" not in result["2"]


@pytest.mark.infrastructure
def test_parse_file_channel_extracted_from_ci20_path() -> None:
    """parse_file correctly extracts 'fast' channel from a /ci-2.0/fast/options.json path."""
    channel, _ = OptionsParser.parse_file(
        '{"1": ""}',
        opt_path="/conan/ci-2.0/fast/options.json",
        ci_prefix=CI_PREFIX_V2,
    )
    assert channel == "fast"


@pytest.mark.infrastructure
def test_parse_file_channel_extracted_from_ci16_path() -> None:
    """parse_file correctly extracts 'slow' channel from a /ci-1.6/slow/options.json path."""
    channel, _ = OptionsParser.parse_file(
        '{"1": ""}',
        opt_path="/conan/ci-1.6/slow/options.json",
        ci_prefix=CI_PREFIX_V16,
    )
    assert channel == "slow"


# ===========================================================================
# UC-O-3: Flat options.json (no channel sub-directory)
# ===========================================================================


@pytest.mark.business_logic
def test_pick_options_apr_global_returned_for_any_channel() -> None:
    """pick_options returns global options for apr regardless of which channel is requested.

    apr only has a flat ci-1.6/options.json (no per-channel split), so the same
    option set {'1': 'apr:shared=True'} must be returned for 'fast', 'slow', or 'tech'.
    """
    repo_data = {
        "global": {"1": "apr:shared=True"},
        "channels": {},
    }
    for channel in ("fast", "slow", "tech", ""):
        result = OptionsParser.pick_options(repo_data, channel)
        assert result == {"1": "apr:shared=True"}, f"failed for channel={channel!r}"


@pytest.mark.integration
def test_parse_file_nlohmann_ci20_flat_returns_none_channel(options_dir: Path) -> None:
    """nlohmann_json ci-2.0/options.json (flat) returns channel=None and single empty entry."""
    text = (options_dir / "nlohmann_json_options.json").read_text(encoding="utf-8")
    channel, cleaned = OptionsParser.parse_file(
        text,
        opt_path="/conan/ci-2.0/options.json",
        ci_prefix=CI_PREFIX_V2,
    )
    assert channel is None
    assert len(cleaned) == 1
    assert cleaned.get("1") == ""


# ===========================================================================
# Edge-case tests for robustness
# ===========================================================================


@pytest.mark.business_logic
def test_select_ci_prefix_with_channel_subdirs_present() -> None:
    """select_ci_prefix works correctly when paths include channel subdirectory structure."""
    paths = [
        "/conan/ci-2.0/fast/options.json",
        "/conan/ci-2.0/slow/options.json",
    ]
    result = OptionsParser.select_ci_prefix(paths)
    assert result == CI_PREFIX_V2


@pytest.mark.business_logic
def test_pick_options_missing_global_key_returns_default() -> None:
    """pick_options returns {'1': ''} when repo_data has channels but no 'global' key."""
    repo_data = {"channels": {"fast": {"1": "x=True"}}}
    result = OptionsParser.pick_options(repo_data, "slow")
    assert result == {"1": ""}


@pytest.mark.infrastructure
def test_parse_file_ci16_with_mixed_ci20_paths() -> None:
    """select_ci_prefix ignores ci-1.6 paths when ci-2.0 paths are also present."""
    paths = [
        "/conan/ci-2.0/fast/options.json",
        "/conan/ci-1.6/options.json",
    ]
    result = OptionsParser.select_ci_prefix(paths)
    assert result == CI_PREFIX_V2


# ===========================================================================
# BL-OP-01  (Part 2 of the test plan)
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_ci20_preferred_over_ci16_when_both_present() -> None:
    """Verify that ci-2.0 is selected when both ci-2.0 and ci-1.6 paths are present.

    Business Rule (BL-OP-01): When a component's Artifactory repository contains
    options files in both ``/ci-2.0/`` and ``/ci-1.6/`` directories, the parser must
    select the ci-2.0 variant as the newer, authoritative format.  The ordering of
    paths in the input list must not affect this decision — priority is enforced by
    the ``_CI_PRIORITY`` constant defined in the module.

    Preconditions:
        - Path list contains one path with "/ci-1.6/" and one with "/ci-2.0/",
          in that order (ci-1.6 listed first).

    Steps:
        1. Call ``OptionsParser.select_ci_prefix(paths)``.

    Expected Result:
        - Return value is ``"/ci-2.0/"``.
    """
    paths = [
        "/components/mylib/ci-1.6/global/options.json",
        "/components/mylib/ci-2.0/global/options.json",
    ]

    selected = OptionsParser.select_ci_prefix(paths)

    assert selected == "/ci-2.0/"
