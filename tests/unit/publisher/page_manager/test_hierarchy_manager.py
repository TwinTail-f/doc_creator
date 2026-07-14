"""Unit-тесты для PageHierarchyManager.

Покрывает:
- ensure_hierarchy_exists выполняет ровно два вызова create_page (если страницы ещё не существуют).
- Первый вызов использует root_parent_id и component_name как заголовок.
- Второй вызов использует ID, возвращённый первым вызовом, как родителя.
- Заголовок второго вызова — "<comp_name> <release_version>".
- Возвращаемое значение — это ID из второго вызова.
- Оба вызова получают корректный ключ space.
"""

from __future__ import annotations

import pytest

from autodoc.exceptions import ConfluenceError
from autodoc.publisher.clients.models.page_result import PageResult
from autodoc.publisher.page_manager.hierarchy_manager import PageHierarchyManager
from tests.unit.publisher.conftest import FakeConfluenceClient

SPACE: str = "TEST"
ROOT_PAGE_ID: str = "root-001"
COMP_NAME: str = "openssl"
RELEASE_VERSION: str = "1.0.0"
COMP_PAGE_ID: str = "comp-page-001"
VERSION_PAGE_ID: str = "ver-page-001"

_COMP_RESPONSE = PageResult(id=COMP_PAGE_ID, version=1, status="created", message="")
_VERSION_RESPONSE = PageResult(id=VERSION_PAGE_ID, version=1, status="created", message="")


def _make_manager(client: FakeConfluenceClient) -> PageHierarchyManager:
    """
    Конструирует PageHierarchyManager с предварительно настроенным FakeConfluenceClient.

    Ни одна из страниц ещё не существует (resolve_existing_page_id по умолчанию
    возвращает None, так как ни одна страница не зарегистрирована), поэтому
    ensure_hierarchy_exists() обязан вызвать create_page() и для страницы
    компонента, и для страницы версии.

    Args:
        client: FakeConfluenceClient, которому будут заданы create_responses.

    Returns:
        PageHierarchyManager, обёрнутый вокруг переданного клиента.
    """
    client.create_responses = [_COMP_RESPONSE, _VERSION_RESPONSE]
    return PageHierarchyManager(client)


def _create_calls(client: FakeConfluenceClient) -> list[dict]:
    """
    Фильтрует записанные вызовы клиента, оставляя только записи create_page.

    Args:
        client: FakeConfluenceClient, из которого читается история вызовов.

    Returns:
        Список словарей с записями вызовов, где method == "create_page".
    """
    return [c for c in client.calls if c["method"] == "create_page"]


@pytest.mark.business_logic
def test_ensure_hierarchy_calls_publish_page_twice(
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """ensure_hierarchy_exists выполняет ровно два вызова create_page, если ни одна страница ещё не существует."""
    manager = _make_manager(publisher_confluence_client)

    manager.ensure_hierarchy_exists(SPACE, ROOT_PAGE_ID, COMP_NAME, RELEASE_VERSION)

    assert len(_create_calls(publisher_confluence_client)) == 2


@pytest.mark.business_logic
def test_ensure_hierarchy_first_call_uses_root_as_parent(
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """Первый вызов create_page должен использовать ROOT_PAGE_ID как parent_id и COMP_NAME как title."""
    manager = _make_manager(publisher_confluence_client)

    manager.ensure_hierarchy_exists(SPACE, ROOT_PAGE_ID, COMP_NAME, RELEASE_VERSION)

    first_call = _create_calls(publisher_confluence_client)[0]
    assert first_call["parent_id"] == ROOT_PAGE_ID
    assert first_call["title"] == COMP_NAME


@pytest.mark.business_logic
def test_ensure_hierarchy_second_call_uses_comp_id_as_parent(
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """Второй вызов create_page должен использовать ID, возвращённый первым вызовом, как parent_id."""
    manager = _make_manager(publisher_confluence_client)

    manager.ensure_hierarchy_exists(SPACE, ROOT_PAGE_ID, COMP_NAME, RELEASE_VERSION)

    second_call = _create_calls(publisher_confluence_client)[1]
    assert second_call["parent_id"] == COMP_PAGE_ID


@pytest.mark.business_logic
def test_ensure_hierarchy_second_call_title_is_comp_version(
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """Заголовок второго вызова create_page должен быть '<comp_name> <release_version>'."""
    manager = _make_manager(publisher_confluence_client)

    manager.ensure_hierarchy_exists(SPACE, ROOT_PAGE_ID, COMP_NAME, RELEASE_VERSION)

    second_call = _create_calls(publisher_confluence_client)[1]
    assert second_call["title"] == f"{COMP_NAME} {RELEASE_VERSION}"


@pytest.mark.business_logic
def test_ensure_hierarchy_returns_version_page_id(
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """Возвращаемое значение должно быть ID из второго ответа create_page."""
    manager = _make_manager(publisher_confluence_client)

    result = manager.ensure_hierarchy_exists(SPACE, ROOT_PAGE_ID, COMP_NAME, RELEASE_VERSION)

    assert result == VERSION_PAGE_ID


@pytest.mark.business_logic
def test_ensure_hierarchy_passes_space_to_both_calls(
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """Оба вызова create_page должны получать один и тот же ключ space."""
    manager = _make_manager(publisher_confluence_client)

    manager.ensure_hierarchy_exists(SPACE, ROOT_PAGE_ID, COMP_NAME, RELEASE_VERSION)

    calls = _create_calls(publisher_confluence_client)
    assert calls[0]["space"] == SPACE
    assert calls[1]["space"] == SPACE


@pytest.mark.business_logic
def test_component_page_created_under_root_parent(
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """страница компонента создаётся с parent_id = root_parent_id."""
    publisher_confluence_client.create_responses = [
        PageResult(id="1000", version=1, status="created", message=""),
        PageResult(id="1001", version=1, status="created", message=""),
    ]
    manager = PageHierarchyManager(publisher_confluence_client)

    manager.ensure_hierarchy_exists(
        space="DEV",
        root_parent_id="ROOT_PAGE",
        component_name="mylib",
        release_version="1.0.0",
    )

    calls = _create_calls(publisher_confluence_client)
    assert len(calls) >= 1, "Должен быть выполнен хотя бы один вызов create_page (страница компонента)"
    assert calls[0]["parent_id"] == "ROOT_PAGE", (
        f"Первый вызов create_page должен использовать root_parent_id='ROOT_PAGE', "
        f"получено parent_id='{calls[0]['parent_id']}'"
    )


@pytest.mark.business_logic
def test_version_page_created_under_component_page(
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """страница релиза создаётся с parent_id = id(страницы компонента)."""
    component_page_id = "COMP_PAGE_ID"
    publisher_confluence_client.create_responses = [
        PageResult(id=component_page_id, version=1, status="created", message=""),
        PageResult(id="VERSION_PAGE_ID", version=1, status="created", message=""),
    ]
    manager = PageHierarchyManager(publisher_confluence_client)

    manager.ensure_hierarchy_exists(
        space="DEV",
        root_parent_id="ROOT",
        component_name="mylib",
        release_version="1.0.0",
    )

    version_calls = [c for c in _create_calls(publisher_confluence_client) if "1.0.0" in c["title"]]
    assert len(version_calls) >= 1, "Должна быть создана страница релиза"
    assert version_calls[0]["parent_id"] == component_page_id, (
        f"Страница релиза должна быть дочерней для страницы компонента '{component_page_id}', "
        f"получено parent_id='{version_calls[0]['parent_id']}'"
    )


@pytest.mark.business_logic
def test_returns_version_page_id_not_component_page_id(
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """ensure_hierarchy_exists возвращает ID страницы РЕЛИЗА, а не страницы компонента."""
    component_page_id = "COMP_PAGE_42"
    version_page_id = "VERSION_PAGE_99"
    publisher_confluence_client.create_responses = [
        PageResult(id=component_page_id, version=1, status="created", message=""),
        PageResult(id=version_page_id, version=1, status="created", message=""),
    ]
    manager = PageHierarchyManager(publisher_confluence_client)

    returned_id = manager.ensure_hierarchy_exists(
        space="DEV",
        root_parent_id="ROOT",
        component_name="mylib",
        release_version="1.0.0",
    )

    assert returned_id == version_page_id, (
        f"Должен быть возвращён ID страницы релиза '{version_page_id}', получено '{returned_id}'"
    )


@pytest.mark.business_logic
def test_ensure_hierarchy_reuses_existing_pages_without_recreating(
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """если страницы уже существуют, create_page повторно не вызывается."""
    publisher_confluence_client.register_page(title=COMP_NAME, page_id=COMP_PAGE_ID)
    publisher_confluence_client.register_page(
        title=f"{COMP_NAME} {RELEASE_VERSION}", page_id=VERSION_PAGE_ID
    )
    manager = PageHierarchyManager(publisher_confluence_client)

    result = manager.ensure_hierarchy_exists(SPACE, ROOT_PAGE_ID, COMP_NAME, RELEASE_VERSION)

    assert result == VERSION_PAGE_ID, "Должен быть возвращён ID уже существующей страницы версии"
    assert _create_calls(publisher_confluence_client) == [], (
        "create_page не должен вызываться, если страница уже разрешена через resolve_existing_page_id"
    )


@pytest.mark.business_logic
def test_version_page_title_format(
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """заголовок страницы релиза имеет формат '{comp_name} {release_version}'."""
    publisher_confluence_client.create_responses = [
        PageResult(id="page-id-1", version=1, status="created", message=""),
        PageResult(id="page-id-2", version=1, status="created", message=""),
    ]
    manager = PageHierarchyManager(publisher_confluence_client)

    manager.ensure_hierarchy_exists(
        space="DEV",
        root_parent_id="ROOT",
        component_name="openssl",
        release_version="3.0.1",
    )

    created_titles = [c["title"] for c in _create_calls(publisher_confluence_client)]
    assert any(
        "openssl" in t and "3.0.1" in t for t in created_titles
    ), f"Заголовок релиза должен содержать 'openssl' и '3.0.1', записанные заголовки: {created_titles}"


@pytest.mark.infrastructure
def test_ensure_hierarchy_propagates_confluence_error_from_create(
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """ConfluenceError из create_page должна распространяться вызывающему коду без подавления."""

    def _raise_confluence_error(*args: object, **kwargs: object) -> PageResult:
        raise ConfluenceError("Не удалось создать страницу")

    publisher_confluence_client.create_page = _raise_confluence_error
    manager = PageHierarchyManager(publisher_confluence_client)

    with pytest.raises(ConfluenceError):
        manager.ensure_hierarchy_exists(SPACE, ROOT_PAGE_ID, COMP_NAME, RELEASE_VERSION)
