"""
Unit tests for autodoc/parser/conan/profile_overrides.py.

Covers ProfileSettingsOverrides: from_file(), resolve(), is_empty(),
empty(), and multi-entry merge behaviour.
"""

import json
from pathlib import Path

import pytest

from autodoc.parser.conan.profile_overrides import ProfileSettingsOverrides

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SINGLE_OVERRIDE: dict = {
    "overrides": [
        {
            "profiles": ["crypto_default.jinja"],
            "settings": {"os": "Linux"},
        }
    ]
}


def _write_json(tmp_path: Path, content: dict) -> Path:
    """Write a dict as JSON to a temp file and return the path."""
    p = tmp_path / "overrides.json"
    p.write_text(json.dumps(content), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# 3.1
# ---------------------------------------------------------------------------


def test_profile_overrides_from_file_loads_correctly(tmp_path: Path) -> None:
    """from_file() with a valid JSON file resolves the exact profile name correctly."""
    path = _write_json(tmp_path, _SINGLE_OVERRIDE)
    overrides = ProfileSettingsOverrides.from_file(path)

    assert overrides.resolve("crypto_default.jinja") == {"os": "Linux"}


# ---------------------------------------------------------------------------
# 3.2
# ---------------------------------------------------------------------------


def test_profile_overrides_from_file_missing_file_returns_empty() -> None:
    """from_file() with a nonexistent path returns an empty instance."""
    overrides = ProfileSettingsOverrides.from_file(Path("/nonexistent/path.json"))

    assert overrides.is_empty() is True


# ---------------------------------------------------------------------------
# 3.3
# ---------------------------------------------------------------------------


def test_profile_overrides_from_file_invalid_json_returns_empty(tmp_path: Path) -> None:
    """from_file() with malformed JSON content returns an empty instance."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_bytes(b"not-json")

    overrides = ProfileSettingsOverrides.from_file(bad_file)

    assert overrides.is_empty() is True


# ---------------------------------------------------------------------------
# 3.4
# ---------------------------------------------------------------------------


def test_profile_overrides_resolve_exact_match(tmp_path: Path) -> None:
    """resolve() with the exact profile name as listed in config returns settings."""
    data = {
        "overrides": [
            {
                "profiles": ["hw-linux-x86_64.jinja"],
                "settings": {"compiler": "gcc"},
            }
        ]
    }
    path = _write_json(tmp_path, data)
    overrides = ProfileSettingsOverrides.from_file(path)

    result = overrides.resolve("hw-linux-x86_64.jinja")

    assert result == {"compiler": "gcc"}


# ---------------------------------------------------------------------------
# 3.5
# ---------------------------------------------------------------------------


def test_profile_overrides_resolve_basename_fallback(tmp_path: Path) -> None:
    """resolve() falls back to basename match when full path is used as profile name.

    The source code performs a basename (Path.name) lookup as a secondary step.
    A profile stored as 'hw-linux-x86_64.jinja' should be found when queried
    via '/some/path/to/hw-linux-x86_64.jinja'.
    """
    data = {
        "overrides": [
            {
                "profiles": ["hw-linux-x86_64.jinja"],
                "settings": {"compiler": "gcc"},
            }
        ]
    }
    path = _write_json(tmp_path, data)
    overrides = ProfileSettingsOverrides.from_file(path)

    # Use a full path whose basename matches the stored profile name
    result = overrides.resolve("/some/path/to/hw-linux-x86_64.jinja")

    assert result == {"compiler": "gcc"}


# ---------------------------------------------------------------------------
# 3.6
# ---------------------------------------------------------------------------


def test_profile_overrides_resolve_no_match_returns_empty_dict(tmp_path: Path) -> None:
    """resolve() with an unknown profile name returns an empty dict."""
    path = _write_json(tmp_path, _SINGLE_OVERRIDE)
    overrides = ProfileSettingsOverrides.from_file(path)

    result = overrides.resolve("unknown-profile.jinja")

    assert result == {}


# ---------------------------------------------------------------------------
# 3.7
# ---------------------------------------------------------------------------


def test_profile_overrides_empty_instance_is_empty() -> None:
    """ProfileSettingsOverrides.empty() produces an instance where is_empty() is True."""
    assert ProfileSettingsOverrides.empty().is_empty() is True


# ---------------------------------------------------------------------------
# 3.8
# ---------------------------------------------------------------------------


def test_profile_overrides_non_empty_is_not_empty(tmp_path: Path) -> None:
    """is_empty() returns False when overrides have been loaded from a valid file."""
    path = _write_json(tmp_path, _SINGLE_OVERRIDE)
    overrides = ProfileSettingsOverrides.from_file(path)

    assert overrides.is_empty() is False


# ---------------------------------------------------------------------------
# 3.9
# ---------------------------------------------------------------------------


def test_profile_overrides_multiple_entries_merged(tmp_path: Path) -> None:
    """Two entries for the same profile name are merged into a single settings dict."""
    data = {
        "overrides": [
            {
                "profiles": ["hw-linux-x86_64.jinja"],
                "settings": {"os": "Linux"},
            },
            {
                "profiles": ["hw-linux-x86_64.jinja"],
                "settings": {"compiler": "gcc"},
            },
        ]
    }
    path = _write_json(tmp_path, data)
    overrides = ProfileSettingsOverrides.from_file(path)

    result = overrides.resolve("hw-linux-x86_64.jinja")

    assert result.get("os") == "Linux"
    assert result.get("compiler") == "gcc"
