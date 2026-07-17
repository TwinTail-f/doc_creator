"""
Юнит-тесты для autodoc/publisher/page_manager/passport_link_injector.py.

Покрывает как happy-path вставки ссылок, так и «дешёвые» ветки continue/return
для компонентов и версий, отсутствующих в реестре паспортов.
"""

from typing import Any

import pytest

from autodoc.publisher.page_manager.passport_link_injector import (
    inject_links,
    inject_links_for_profiles,
)


@pytest.mark.business_logic
def test_inject_links_for_profiles_sets_link_for_known_component() -> None:
    """inject_links_for_profiles проставляет passport_link для компонента,
    найденного в реестре паспортов."""
    view_model: dict[str, Any] = {
        "space": "TEST",
        "profiles": [
            {"channels": {"fast": [{"name": "mylib", "version": "1.0"}]}},
        ],
    }
    passport_pages = {"mylib": {"1.0": {"page_id": "42"}}}

    inject_links_for_profiles(view_model, passport_pages)

    comp = view_model["profiles"][0]["channels"]["fast"][0]
    assert comp["passport_link"] == "/spaces/TEST/pages/42"


@pytest.mark.business_logic
def test_inject_links_for_profiles_sets_none_for_unknown_component() -> None:
    """inject_links_for_profiles оставляет passport_link=None (и переходит к следующему
    компоненту через continue) для компонента, отсутствующего в реестре паспортов."""
    view_model: dict[str, Any] = {
        "space": "TEST",
        "profiles": [
            {"channels": {"fast": [{"name": "unknown-lib", "version": "1.0"}]}},
        ],
    }

    inject_links_for_profiles(view_model, {"other-lib": {"1.0": {"page_id": "1"}}})

    comp = view_model["profiles"][0]["channels"]["fast"][0]
    assert comp["passport_link"] is None


@pytest.mark.business_logic
def test_inject_links_for_profiles_noop_when_registry_empty() -> None:
    """inject_links_for_profiles ничего не делает (не мутирует view_model), если реестр пуст."""
    view_model: dict[str, Any] = {
        "space": "TEST",
        "profiles": [{"channels": {"fast": [{"name": "mylib", "version": "1.0"}]}}],
    }

    inject_links_for_profiles(view_model, {})

    comp = view_model["profiles"][0]["channels"]["fast"][0]
    assert "passport_link" not in comp


@pytest.mark.business_logic
def test_inject_links_adds_passport_versions_for_known_component() -> None:
    """inject_links добавляет passport_versions с URL для компонента, найденного в реестре,
    сохраняя остальные поля записи реестра (например, page_id) через слияние словарей."""
    view_model: dict[str, Any] = {
        "space": "TEST",
        "components": [
            {"name": "mylib", "releases": [{"version": "1.0"}]},
        ],
    }
    passport_pages = {"mylib": {"1.0": {"page_id": "42"}}}

    inject_links(view_model, passport_pages)

    entry = view_model["components"][0]["passport_versions"]["1.0"]
    assert entry["url"] == "/spaces/TEST/pages/42"
    assert entry["page_id"] == "42"


@pytest.mark.business_logic
def test_inject_links_skips_versions_not_in_component_releases() -> None:
    """inject_links включает в passport_versions только те версии реестра,
    которые присутствуют среди релизов компонента в view-model."""
    view_model: dict[str, Any] = {
        "space": "TEST",
        "components": [{"name": "mylib", "releases": [{"version": "1.0"}]}],
    }
    passport_pages: dict[str, Any] = {
        "mylib": {
            "1.0": {"page_id": "p1"},
            "2.0": {"page_id": "p2"},
        }
    }

    inject_links(view_model, passport_pages)

    passport_versions = view_model["components"][0]["passport_versions"]
    assert "1.0" in passport_versions
    assert "2.0" not in passport_versions


@pytest.mark.business_logic
def test_inject_links_skips_component_not_in_registry() -> None:
    """inject_links пропускает компонент через continue, если его имени нет в реестре
    паспортов вовсе, — ключ passport_versions для него не добавляется."""
    view_model: dict[str, Any] = {
        "space": "TEST",
        "components": [
            {"name": "unknown-lib", "releases": [{"version": "1.0"}]},
        ],
    }

    inject_links(view_model, {"other-lib": {"1.0": {"page_id": "1"}}})

    comp = view_model["components"][0]
    assert "passport_versions" not in comp


@pytest.mark.business_logic
def test_inject_links_noop_when_components_key_absent() -> None:
    """inject_links ничего не делает, если в view_model нет ключа 'components'."""
    view_model: dict[str, Any] = {"space": "TEST"}

    inject_links(view_model, {"mylib": {"1.0": {"page_id": "1"}}})

    assert view_model == {"space": "TEST"}


@pytest.mark.business_logic
def test_inject_links_noop_when_passport_pages_empty() -> None:
    """inject_links ничего не делает, если реестр паспортов пуст."""
    view_model: dict[str, Any] = {
        "space": "TEST",
        "components": [{"name": "mylib", "releases": [{"version": "1.0"}]}],
    }

    inject_links(view_model, {})

    assert "passport_versions" not in view_model["components"][0]


@pytest.mark.business_logic
def test_inject_links_for_profiles_sets_none_when_page_id_missing() -> None:
    """inject_links_for_profiles оставляет passport_link=None, если найденная
    запись реестра лишена page_id."""
    view_model: dict[str, Any] = {
        "space": "TEST",
        "profiles": [
            {"channels": {"fast": [{"name": "mylib", "version": "1.0"}]}},
        ],
    }
    passport_pages = {"mylib": {"1.0": {"page_id": None}}}

    inject_links_for_profiles(view_model, passport_pages)

    comp = view_model["profiles"][0]["channels"]["fast"][0]
    assert comp["passport_link"] is None


@pytest.mark.business_logic
def test_inject_links_for_profiles_noop_when_profiles_key_absent() -> None:
    """inject_links_for_profiles ничего не делает, если в view_model нет ключа 'profiles'."""
    view_model: dict[str, Any] = {"space": "TEST", "components": []}
    passport_pages = {"mylib": {"1.0": {"page_id": "1"}}}

    inject_links_for_profiles(view_model, passport_pages)

    assert view_model == {"space": "TEST", "components": []}
