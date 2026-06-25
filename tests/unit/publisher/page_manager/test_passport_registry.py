"""Unit tests for PassportPageRegistry.

Covers:
- save() writes JSON to data_dir/passport_pages.json.
- save() creates the parent directory when it does not exist.
- save() produces valid JSON that round-trips through load().
- save() on OSError does not raise — only logs.
- load() returns {} when the file is missing.
- load() returns a dict on a valid file.
- load() returns {} on malformed JSON.
- load() returns {} on OSError from read_text.
- inject_links() adds passport_versions keyed by version.
- inject_links() includes only versions present in the component's releases.
- inject_links() is a no-op when the view_model lacks a 'components' key.
- inject_links() is a no-op when passport_pages is empty.
- inject_links_for_profiles() sets passport_link on matched component entries.
- inject_links_for_profiles() leaves passport_link as None for unknown components.
- inject_links_for_profiles() is a no-op when the view_model lacks a 'profiles' key.
- inject_links_for_profiles() is a no-op when passport_pages is empty.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from autodoc.publisher.page_manager.passport_registry import PassportPageRegistry

# ---------------------------------------------------------------------------
# Fixtures helpers
# ---------------------------------------------------------------------------

_PAGES_MAP: dict[str, Any] = {
    "openssl": {"1.0.0": {"page_id": "p1", "page_title": "openssl 1.0.0", "version": 1}}
}

_REGISTRY_FILE: str = "passport_pages.json"

SPACE: str = "TEST"
PAGE_ID: str = "p-001"


def _make_registry(data_dir: Path) -> PassportPageRegistry:
    """Creates a PassportPageRegistry using the given data_dir."""
    return PassportPageRegistry(data_dir=data_dir)


# ---------------------------------------------------------------------------
# save() tests
# ---------------------------------------------------------------------------


@pytest.mark.infrastructure
def test_save_creates_file_in_data_dir(tmp_path: Path) -> None:
    """save() writes passport_pages.json into data_dir."""
    registry = _make_registry(tmp_path)

    registry.save(_PAGES_MAP)

    assert (tmp_path / _REGISTRY_FILE).exists()


@pytest.mark.infrastructure
def test_save_creates_parent_directory_if_missing(tmp_path: Path) -> None:
    """save() creates data_dir when it does not yet exist."""
    data_dir = tmp_path / "new_subdir"
    registry = _make_registry(data_dir)

    registry.save(_PAGES_MAP)

    assert data_dir.exists()


@pytest.mark.infrastructure
def test_save_writes_valid_json(tmp_path: Path) -> None:
    """save() writes content that can be parsed as valid JSON."""
    registry = _make_registry(tmp_path)

    registry.save(_PAGES_MAP)

    raw = (tmp_path / _REGISTRY_FILE).read_text(encoding="utf-8")
    parsed = json.loads(raw)
    assert parsed == _PAGES_MAP


@pytest.mark.infrastructure
def test_save_on_os_error_does_not_raise(tmp_path: Path, mocker: pytest.MonkeyPatch) -> None:
    """save() swallows OSError and does not propagate the exception."""
    registry = _make_registry(tmp_path)
    mocker.patch("pathlib.Path.write_text", side_effect=OSError("disk full"))

    # Must not raise
    registry.save(_PAGES_MAP)


# ---------------------------------------------------------------------------
# load() tests
# ---------------------------------------------------------------------------


@pytest.mark.infrastructure
def test_load_returns_empty_dict_if_file_missing(tmp_path: Path) -> None:
    """load() returns {} when passport_pages.json does not exist."""
    registry = _make_registry(tmp_path)

    result = registry.load()

    assert result == {}


@pytest.mark.infrastructure
def test_load_returns_dict_on_valid_file(tmp_path: Path) -> None:
    """load() deserialises and returns the stored dict."""
    (tmp_path / _REGISTRY_FILE).write_text(
        json.dumps(_PAGES_MAP, ensure_ascii=False), encoding="utf-8"
    )
    registry = _make_registry(tmp_path)

    result = registry.load()

    assert result == _PAGES_MAP


@pytest.mark.infrastructure
def test_load_returns_empty_dict_on_invalid_json(tmp_path: Path) -> None:
    """load() returns {} when the file contains malformed JSON."""
    (tmp_path / _REGISTRY_FILE).write_text("not valid json", encoding="utf-8")
    registry = _make_registry(tmp_path)

    result = registry.load()

    assert result == {}


@pytest.mark.infrastructure
def test_load_returns_empty_dict_on_os_error(tmp_path: Path, mocker: pytest.MonkeyPatch) -> None:
    """load() returns {} when read_text raises OSError."""
    (tmp_path / _REGISTRY_FILE).write_text("{}", encoding="utf-8")
    registry = _make_registry(tmp_path)
    mocker.patch("pathlib.Path.read_text", side_effect=OSError("permission denied"))

    result = registry.load()

    assert result == {}


@pytest.mark.infrastructure
def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    """A value saved by save() is faithfully returned by load()."""
    pages_map: dict[str, Any] = {
        "openssl": {"1.0.0": {"page_id": "p1", "page_title": "T", "version": 1}}
    }
    registry = _make_registry(tmp_path)

    registry.save(pages_map)
    loaded = registry.load()

    assert loaded == pages_map


# ---------------------------------------------------------------------------
# inject_links() tests
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_inject_links_adds_passport_versions_to_component(tmp_path: Path) -> None:
    """inject_links() sets passport_versions on a matched component."""
    view_model: dict[str, Any] = {
        "components": [{"name": "openssl", "releases": [{"version": "1.0.0"}]}]
    }
    passport_pages: dict[str, Any] = {"openssl": {"1.0.0": {"page_id": PAGE_ID}}}

    PassportPageRegistry.inject_links(view_model, passport_pages)

    assert view_model["components"][0]["passport_versions"]["1.0.0"]["page_id"] == PAGE_ID


@pytest.mark.business_logic
def test_inject_links_skips_versions_not_in_releases(tmp_path: Path) -> None:
    """inject_links() includes only versions present in the component's releases."""
    view_model: dict[str, Any] = {
        "components": [{"name": "openssl", "releases": [{"version": "1.0.0"}]}]
    }
    passport_pages: dict[str, Any] = {
        "openssl": {
            "1.0.0": {"page_id": "p1"},
            "2.0.0": {"page_id": "p2"},
        }
    }

    PassportPageRegistry.inject_links(view_model, passport_pages)

    passport_versions = view_model["components"][0]["passport_versions"]
    assert "1.0.0" in passport_versions
    assert "2.0.0" not in passport_versions


@pytest.mark.business_logic
def test_inject_links_noop_if_no_components_key() -> None:
    """inject_links() does nothing and does not raise when 'components' is absent."""
    view_model: dict[str, Any] = {"other_key": "value"}
    passport_pages: dict[str, Any] = {"openssl": {"1.0.0": {"page_id": PAGE_ID}}}

    PassportPageRegistry.inject_links(view_model, passport_pages)

    assert "components" not in view_model


@pytest.mark.business_logic
def test_inject_links_noop_if_passport_pages_empty() -> None:
    """inject_links() does nothing when passport_pages is empty."""
    view_model: dict[str, Any] = {
        "components": [{"name": "openssl", "releases": [{"version": "1.0.0"}]}]
    }

    PassportPageRegistry.inject_links(view_model, {})

    assert "passport_versions" not in view_model["components"][0]


# ---------------------------------------------------------------------------
# inject_links_for_profiles() tests
# ---------------------------------------------------------------------------


def _make_profile_view_model(comp_name: str, version: str, space: str = SPACE) -> dict[str, Any]:
    """Builds a minimal profile-centric view model for inject_links_for_profiles tests."""
    return {
        "space": space,
        "profiles": [
            {"channels": {"tech": [{"name": comp_name, "version": version, "passport_link": None}]}}
        ],
    }


@pytest.mark.business_logic
def test_inject_links_for_profiles_sets_passport_link() -> None:
    """inject_links_for_profiles() sets passport_link to the expected Confluence path."""
    view_model = _make_profile_view_model("openssl", "1.0.0")
    passport_pages: dict[str, Any] = {"openssl": {"1.0.0": {"page_id": PAGE_ID}}}

    PassportPageRegistry.inject_links_for_profiles(view_model, passport_pages)

    comp = view_model["profiles"][0]["channels"]["tech"][0]
    assert comp["passport_link"] == f"/spaces/{SPACE}/pages/{PAGE_ID}"


@pytest.mark.business_logic
def test_inject_links_for_profiles_sets_none_if_comp_missing() -> None:
    """inject_links_for_profiles() sets passport_link to None when comp not in registry."""
    view_model = _make_profile_view_model("unknown_lib", "1.0.0")
    passport_pages: dict[str, Any] = {"openssl": {"1.0.0": {"page_id": PAGE_ID}}}

    PassportPageRegistry.inject_links_for_profiles(view_model, passport_pages)

    comp = view_model["profiles"][0]["channels"]["tech"][0]
    assert comp["passport_link"] is None


@pytest.mark.business_logic
def test_inject_links_for_profiles_noop_if_no_profiles_key() -> None:
    """inject_links_for_profiles() does not raise when 'profiles' key is absent."""
    view_model: dict[str, Any] = {"space": SPACE, "components": []}
    passport_pages: dict[str, Any] = {"openssl": {"1.0.0": {"page_id": PAGE_ID}}}

    PassportPageRegistry.inject_links_for_profiles(view_model, passport_pages)

    assert "profiles" not in view_model


@pytest.mark.business_logic
def test_inject_links_for_profiles_noop_if_empty_passport_pages() -> None:
    """inject_links_for_profiles() does nothing when passport_pages is empty."""
    view_model = _make_profile_view_model("openssl", "1.0.0")
    original_link = view_model["profiles"][0]["channels"]["tech"][0]["passport_link"]

    PassportPageRegistry.inject_links_for_profiles(view_model, {})

    comp = view_model["profiles"][0]["channels"]["tech"][0]
    assert comp["passport_link"] == original_link


# ---------------------------------------------------------------------------
# Part-3 BL additions: BL-REG-09, BL-REG-10
# ---------------------------------------------------------------------------


@pytest.mark.infrastructure
def test_load_returns_empty_on_missing_file(tmp_path: Path) -> None:
    """
    BL-REG-09
    Business Rule: missing registry file → {}, not an exception (first run).

    Preconditions:
        - data_dir exists but passport_pages.json is not present.

    Steps:
        1. Instantiate PassportPageRegistry with data_dir pointing to an empty directory.
        2. Call registry.load().

    Expected Result:
        load() returns {} without raising FileNotFoundError or any other exception.
        This allows ReleasePageStrategy to run even when PassportsStrategy
        has never been executed before.
    """
    registry = PassportPageRegistry(data_dir=tmp_path)
    # File is intentionally absent — first run scenario

    result = registry.load()

    assert (
        result == {}
    ), f"load() must return an empty dict when the file is missing, got: {result!r}"
