"""Unit tests for autodoc.parser.parsers.options_parser.OptionsParser.

Covers: select_ci_prefix, parse_file, pick_options.
Real options JSON files are read from resources_dir fixture.
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

JSON_TWO_OPTIONS: str = '{"1": "shared=True", "2": "shared=False"}'
JSON_ONE_PADDED: str = '{"1": "  shared=True  "}'
JSON_MIXED_TYPES: str = '{"1": "shared=True", "count": 42}'
JSON_INVALID: str = "not-json"


# ===========================================================================
# 3.1 — select_ci_prefix: /ci-2.0/ preferred over /ci-1.6/
# ===========================================================================


def test_select_ci_prefix_prefers_v2() -> None:
    """select_ci_prefix returns '/ci-2.0/' when both v2 and v1.6 paths are present."""
    paths = [PATH_V2_TECH, PATH_V16_TECH]
    result = OptionsParser.select_ci_prefix(paths)
    assert result == CI_PREFIX_V2


# ===========================================================================
# 3.2 — select_ci_prefix: only /ci-1.6/ present
# ===========================================================================


def test_select_ci_prefix_falls_back_to_v1_6() -> None:
    """select_ci_prefix returns '/ci-1.6/' when only v1.6 paths are present."""
    paths = ["/repo/ci-1.6/tech/options.json"]
    result = OptionsParser.select_ci_prefix(paths)
    assert result == CI_PREFIX_V16


# ===========================================================================
# 3.3 — select_ci_prefix: no match → empty string
# ===========================================================================


def test_select_ci_prefix_no_match_returns_empty_string() -> None:
    """select_ci_prefix returns '' when no recognised CI directory is found."""
    result = OptionsParser.select_ci_prefix([PATH_OTHER])
    assert result == ""


# ===========================================================================
# 3.4 — select_ci_prefix: empty list → empty string
# ===========================================================================


def test_select_ci_prefix_empty_list_returns_empty_string() -> None:
    """select_ci_prefix returns '' for an empty input list."""
    result = OptionsParser.select_ci_prefix([])
    assert result == ""


# ===========================================================================
# 3.5 — parse_file: valid JSON extracts channel name
# ===========================================================================


def test_parse_file_valid_json_extracts_channel() -> None:
    """parse_file correctly extracts the channel segment from the path."""
    channel, cleaned = OptionsParser.parse_file(
        JSON_TWO_OPTIONS,
        opt_path=PATH_V2_TECH,
        ci_prefix=CI_PREFIX_V2,
    )
    assert channel == "tech"
    assert cleaned == {"1": "shared=True", "2": "shared=False"}


# ===========================================================================
# 3.6 — parse_file: no sub-segment after prefix → channel is None
# ===========================================================================


def test_parse_file_no_channel_segment_returns_none() -> None:
    """parse_file returns channel=None when the path has no subdirectory after the prefix."""
    channel, _ = OptionsParser.parse_file(
        JSON_TWO_OPTIONS,
        opt_path="/repo/ci-2.0/options.json",
        ci_prefix=CI_PREFIX_V2,
    )
    assert channel is None


# ===========================================================================
# 3.7 — parse_file: invalid JSON → empty dict and None channel
# ===========================================================================


def test_parse_file_invalid_json_returns_empty() -> None:
    """parse_file returns (None, {}) when the JSON text cannot be parsed."""
    result = OptionsParser.parse_file(
        JSON_INVALID,
        opt_path=PATH_V2_TECH,
        ci_prefix=CI_PREFIX_V2,
    )
    assert result == (None, {})


# ===========================================================================
# 3.8 — parse_file: strips whitespace from string values
# ===========================================================================


def test_parse_file_strips_whitespace_from_values() -> None:
    """parse_file strips leading/trailing whitespace from each option string value."""
    _, cleaned = OptionsParser.parse_file(
        JSON_ONE_PADDED,
        opt_path=PATH_V2_TECH,
        ci_prefix=CI_PREFIX_V2,
    )
    assert cleaned["1"] == "shared=True"


# ===========================================================================
# 3.9 — parse_file: non-string values are excluded
# ===========================================================================


def test_parse_file_non_string_values_excluded() -> None:
    """parse_file omits entries whose value is not a string (e.g. integers)."""
    _, cleaned = OptionsParser.parse_file(
        JSON_MIXED_TYPES,
        opt_path=PATH_V2_TECH,
        ci_prefix=CI_PREFIX_V2,
    )
    assert "1" in cleaned
    assert "count" not in cleaned


# ===========================================================================
# 3.10 — pick_options: channel-specific options returned when channel matches
# ===========================================================================


def test_pick_options_returns_channel_specific() -> None:
    """pick_options returns channels[channel] when the channel key exists."""
    data: dict = {"channels": {"tech": {"1": "shared=True"}}, "global": {"1": ""}}
    result = OptionsParser.pick_options(data, "tech")
    assert result == {"1": "shared=True"}


# ===========================================================================
# 3.11 — pick_options: falls back to global when channel not found
# ===========================================================================


def test_pick_options_falls_back_to_global() -> None:
    """pick_options returns the 'global' entry when the requested channel is absent."""
    data: dict = {"channels": {}, "global": {"1": "shared=False"}}
    result = OptionsParser.pick_options(data, "tech")
    assert result == {"1": "shared=False"}


# ===========================================================================
# 3.12 — pick_options: falls back to {"1": ""} when both missing
# ===========================================================================


def test_pick_options_defaults_to_empty_option_set() -> None:
    """pick_options returns {'1': ''} when neither channels nor global is present."""
    result = OptionsParser.pick_options({}, "tech")
    assert result == {"1": ""}


# ===========================================================================
# 3.13 — pick_options: empty channel string uses global
# ===========================================================================


def test_pick_options_empty_channel_uses_global() -> None:
    """pick_options falls back to global when channel is an empty string."""
    data: dict = {"channels": {"tech": {"1": "x"}}, "global": {"1": "y"}}
    result = OptionsParser.pick_options(data, "")
    assert result == {"1": "y"}


# ===========================================================================
# 3.14 — Real openssl_options.json parses correctly (uses resources_dir)
# ===========================================================================


def test_options_parser_parses_real_openssl_options(resources_dir: Path) -> None:
    """OptionsParser.parse_file reads a real options.json and returns correct mapping."""
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


# ===========================================================================
# 3.15 — Real zlib_options.json: single empty option (uses resources_dir)
# ===========================================================================


def test_options_parser_parses_zlib_single_empty_option(resources_dir: Path) -> None:
    """OptionsParser.parse_file handles a file with one empty-string option without error."""
    options_file = resources_dir / "options" / "zlib_options.json"
    text = options_file.read_text(encoding="utf-8")
    channel, cleaned = OptionsParser.parse_file(
        text, opt_path="/ci-2.0/fast/options.json", ci_prefix=CI_PREFIX_V2
    )
    assert channel == "fast"
    assert "1" in cleaned
    assert cleaned["1"] == ""
