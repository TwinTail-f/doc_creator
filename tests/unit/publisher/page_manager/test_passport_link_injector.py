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
@pytest.mark.parametrize(
    "component_name, passport_pages, expected_link",
    [
        pytest.param(
            "mylib",
            {"mylib": {"1.0": {"page_id": "42"}}},
            "/spaces/TEST/pages/42",
            id="known-component-with-page-id",
        ),
        pytest.param(
            "unknown-lib",
            {"other-lib": {"1.0": {"page_id": "1"}}},
            None,
            id="unknown-component",
        ),
        pytest.param(
            "mylib",
            {"mylib": {"1.0": {"page_id": None}}},
            None,
            id="known-component-missing-page-id",
        ),
    ],
)
def test_inject_links_for_profiles_sets_passport_link(
    component_name: str,
    passport_pages: dict[str, Any],
    expected_link: str | None,
) -> None:
    """inject_links_for_profiles проставляет passport_link в зависимости от того,
    найден ли компонент/версия в реестре паспортов и задан ли у записи page_id."""
    view_model: dict[str, Any] = {
        "space": "TEST",
        "profiles": [
            {"channels": {"fast": [{"name": component_name, "version": "1.0"}]}},
        ],
    }

    inject_links_for_profiles(view_model, passport_pages)

    comp = view_model["profiles"][0]["channels"]["fast"][0]
    assert comp["passport_link"] == expected_link


@pytest.mark.business_logic
def test_inject_links_for_profiles_noop_when_registry_empty() -> None:
    """inject_links_for_profiles не мутирует view_model, если реестр паспортов пуст."""
    view_model: dict[str, Any] = {
        "space": "TEST",
        "profiles": [{"channels": {"fast": [{"name": "mylib", "version": "1.0"}]}}],
    }

    inject_links_for_profiles(view_model, {})

    assert view_model == {
        "space": "TEST",
        "profiles": [{"channels": {"fast": [{"name": "mylib", "version": "1.0"}]}}],
    }


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
    """inject_links не мутирует view_model, если реестр паспортов пуст."""
    view_model: dict[str, Any] = {
        "space": "TEST",
        "components": [{"name": "mylib", "releases": [{"version": "1.0"}]}],
    }

    inject_links(view_model, {})

    assert view_model == {
        "space": "TEST",
        "components": [{"name": "mylib", "releases": [{"version": "1.0"}]}],
    }


@pytest.mark.business_logic
def test_inject_links_for_profiles_noop_when_profiles_key_absent() -> None:
    """inject_links_for_profiles ничего не делает, если в view_model нет ключа 'profiles'."""
    view_model: dict[str, Any] = {"space": "TEST", "components": []}
    passport_pages = {"mylib": {"1.0": {"page_id": "1"}}}

    inject_links_for_profiles(view_model, passport_pages)

    assert view_model == {"space": "TEST", "components": []}
