"""
Unit-тесты для PageHierarchyManager.

Покрывает:
- ensure_hierarchy_exists выполняет ровно два вызова create_page (если страницы ещё не существуют).
- Первый вызов использует root_parent_id и component_name как заголовок.
- Второй вызов использует ID, возвращённый первым вызовом, как родителя.
- Заголовок второго вызова — "<comp_name> <release_version>".
- Возвращаемое значение — это ID из второго вызова.
- Оба вызова получают корректный ключ space.
"""

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


@pytest.fixture
def hierarchy_manager(publisher_confluence_client: FakeConfluenceClient) -> PageHierarchyManager:
    """
    PageHierarchyManager с предварительно настроенным FakeConfluenceClient.

    Ни одна из страниц ещё не существует (resolve_existing_page_id по умолчанию
    возвращает None, так как ни одна страница не зарегистрирована), поэтому
    ensure_hierarchy_exists() обязан вызвать create_page() и для страницы
    компонента, и для страницы версии.
    """
    publisher_confluence_client.create_responses = [_COMP_RESPONSE, _VERSION_RESPONSE]
    return PageHierarchyManager(publisher_confluence_client)


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
def test_ensure_hierarchy_creates_component_then_version_page(
    hierarchy_manager: PageHierarchyManager,
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """
    ensure_hierarchy_exists() создаёт ровно две страницы (компонент, затем версию).

    Первый вызов create_page использует ROOT_PAGE_ID как parent_id и COMP_NAME
    как title. Второй вызов использует ID, возвращённый первым вызовом, как
    parent_id, и заголовок '<comp_name> <release_version>'. Оба вызова
    получают один и тот же space. Возвращаемое значение — ID из второго ответа.
    """
    result = hierarchy_manager.ensure_hierarchy_exists(
        SPACE, ROOT_PAGE_ID, COMP_NAME, RELEASE_VERSION
    )

    calls = _create_calls(publisher_confluence_client)
    assert len(calls) == 2

    first_call, second_call = calls
    assert first_call["parent_id"] == ROOT_PAGE_ID
    assert first_call["title"] == COMP_NAME
    assert first_call["space"] == SPACE

    assert second_call["parent_id"] == COMP_PAGE_ID
    assert second_call["title"] == f"{COMP_NAME} {RELEASE_VERSION}"
    assert second_call["space"] == SPACE

    assert result == VERSION_PAGE_ID


@pytest.mark.business_logic
def test_ensure_hierarchy_reuses_existing_pages_without_recreating(
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """Если страницы уже существуют, create_page повторно не вызывается."""
    publisher_confluence_client.register_page(title=COMP_NAME, page_id=COMP_PAGE_ID)
    publisher_confluence_client.register_page(
        title=f"{COMP_NAME} {RELEASE_VERSION}", page_id=VERSION_PAGE_ID
    )
    manager = PageHierarchyManager(publisher_confluence_client)

    result = manager.ensure_hierarchy_exists(SPACE, ROOT_PAGE_ID, COMP_NAME, RELEASE_VERSION)

    assert result == VERSION_PAGE_ID, "Должен быть возвращён ID уже существующей страницы версии"
    assert (
        _create_calls(publisher_confluence_client) == []
    ), "create_page не должен вызываться, если страница уже разрешена через resolve_existing_page_id"


@pytest.mark.infrastructure  # было contract — это делегирование ошибки, не совместимость протокола
@pytest.mark.parametrize(
    ("failing_method", "error_message"),
    [
        pytest.param(
            "resolve_existing_page_id", "Не удалось найти страницу", id="resolve_existing_page_id"
        ),
        pytest.param("create_page", "Не удалось создать страницу", id="create_page"),
    ],
)
def test_ensure_hierarchy_propagates_confluence_error(
    publisher_confluence_client: FakeConfluenceClient,
    failing_method: str,
    error_message: str,
) -> None:
    """ConfluenceError от клиента распространяется вызывающему коду без подавления."""

    def _raise_confluence_error(*args: object, **kwargs: object) -> object:
        raise ConfluenceError(error_message)

    setattr(publisher_confluence_client, failing_method, _raise_confluence_error)
    manager = PageHierarchyManager(publisher_confluence_client)

    with pytest.raises(ConfluenceError):
        manager.ensure_hierarchy_exists(SPACE, ROOT_PAGE_ID, COMP_NAME, RELEASE_VERSION)
