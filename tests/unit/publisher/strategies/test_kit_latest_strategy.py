"""
Тесты для autodoc.publisher.strategies.kit_latest_strategy.KitLatestPageStrategy.

Стратегия тестирования: зеркалит test_kit_fixed_strategy.py — общий
инфраструктурный контракт (execute/публикация/паспорта) идентичен, отличия
проверяются в тесте на форму ссылок (wildcard include_prerelease).
"""

from pathlib import Path
from typing import Any

import pytest
from pytest_mock import MockerFixture

from autodoc.exceptions import ConfluenceError
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.page_manager.passport_registry import PassportPageRegistry
from autodoc.publisher.strategies.kit_latest_strategy import KitLatestPageStrategy
from autodoc.publisher.strategies.registry import create_strategy
from tests.unit.publisher.conftest import FakeConfluenceClient
from tests.unit.publisher.strategies.conftest import FakeDocumentBuilder

_SPACE: str = "TEST"
_PAGE_TITLE: str = "Встраивание последних версий компонентов платформы"
_TEMPLATE_NAME: str = "embedding_kit.jinja2"
_PARENT_ID: str = "parent-001"


def make_kit_latest_strategy(
    client: FakeConfluenceClient,
    builder: FakeDocumentBuilder,
    data: ParsedResult,
    tmp_path: Path,
) -> KitLatestPageStrategy:
    """Создаёт KitLatestPageStrategy с разумными значениями по умолчанию для юнит-тестов."""
    return KitLatestPageStrategy(
        confluence_client=client,
        document_builder=builder,
        parsed_data=data,
        space=_SPACE,
        page_title=_PAGE_TITLE,
        template_name=_TEMPLATE_NAME,
        parent_id=_PARENT_ID,
        data_dir=tmp_path,
    )


@pytest.mark.business_logic
def test_execute_calls_publish_single_page(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_multi_component_result: ParsedResult,
    tmp_path: Path,
) -> None:
    """execute() в конечном счёте вызывает client.publish_page с корректным заголовком."""
    strategy = make_kit_latest_strategy(
        publisher_confluence_client,
        publisher_document_builder,
        publisher_multi_component_result,
        tmp_path,
    )
    strategy.execute()
    publish_calls = [c for c in publisher_confluence_client.calls if c["method"] == "publish_page"]
    assert len(publish_calls) == 1
    assert publish_calls[0]["title"] == _PAGE_TITLE


@pytest.mark.business_logic
def test_execute_returns_success_report(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_multi_component_result: ParsedResult,
    tmp_path: Path,
) -> None:
    """Успешный execute() возвращает report.success=True и pages_published=1."""
    strategy = make_kit_latest_strategy(
        publisher_confluence_client,
        publisher_document_builder,
        publisher_multi_component_result,
        tmp_path,
    )
    report = strategy.execute()
    assert report.success is True
    assert report.pages_published == 1


@pytest.mark.business_logic
def test_execute_returns_failure_on_client_error(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_multi_component_result: ParsedResult,
    tmp_path: Path,
) -> None:
    """Если publish_page выбрасывает ConfluenceError, report.success равен False."""

    def raise_confluence_error(*args: Any, **kwargs: Any) -> None:
        raise ConfluenceError("connection refused")

    publisher_confluence_client.publish_page = raise_confluence_error

    strategy = make_kit_latest_strategy(
        publisher_confluence_client,
        publisher_document_builder,
        publisher_multi_component_result,
        tmp_path,
    )
    report = strategy.execute()
    assert report.success is False


@pytest.mark.contract
def test_include_passport_links_always_false_even_if_requested(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_multi_component_result: ParsedResult,
    tmp_path: Path,
) -> None:
    """Явная попытка передать include_passport_links=True игнорируется — у этой
    страницы нет понятия ссылок на паспорта."""
    strategy = KitLatestPageStrategy(
        confluence_client=publisher_confluence_client,
        document_builder=publisher_document_builder,
        parsed_data=publisher_multi_component_result,
        space=_SPACE,
        page_title=_PAGE_TITLE,
        template_name=_TEMPLATE_NAME,
        parent_id=_PARENT_ID,
        include_passport_links=True,
        data_dir=tmp_path,
    )
    assert strategy._include_passport_links is False


@pytest.mark.contract
def test_passport_registry_load_never_called(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_multi_component_result: ParsedResult,
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    """execute() не обращается к PassportPageRegistry.load() — этой странице
    паспорта не нужны."""
    mock_load = mocker.patch.object(PassportPageRegistry, "load", return_value={})
    strategy = make_kit_latest_strategy(
        publisher_confluence_client,
        publisher_document_builder,
        publisher_multi_component_result,
        tmp_path,
    )
    strategy.execute()
    assert mock_load.call_count == 0


@pytest.mark.contract
def test_make_converter_creates_kit_latest_converter(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_multi_component_result: ParsedResult,
    tmp_path: Path,
) -> None:
    """create_strategy('kit_latest', ...) подключает KitLatestConverter — view_model
    имеет форму channels/version_column_title, а не components (как у release)."""
    strategy = create_strategy(
        "kit_latest",
        confluence_client=publisher_confluence_client,
        document_builder=publisher_document_builder,
        parsed_data=publisher_multi_component_result,
        space=_SPACE,
        page_title=_PAGE_TITLE,
        template_name=_TEMPLATE_NAME,
        parent_id=_PARENT_ID,
        data_dir=tmp_path,
    )
    strategy.execute()

    assert publisher_document_builder.last_call is not None
    view_model = publisher_document_builder.last_call["view_model"]
    assert "channels" in view_model, "форма view_model должна соответствовать KitLatestConverter"
    assert view_model["version_column_title"] == "Последняя сборка"


@pytest.mark.business_logic
def test_view_model_contains_wildcard_references_not_pinned_versions(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_multi_component_result: ParsedResult,
    tmp_path: Path,
) -> None:
    """Отрендеренный view_model содержит литеральный диапазон [,include_prerelease],
    а не точную версию из ParsedResult (это отличает kit_latest от kit_fixed)."""
    strategy = make_kit_latest_strategy(
        publisher_confluence_client,
        publisher_document_builder,
        publisher_multi_component_result,
        tmp_path,
    )
    strategy.execute()

    view_model = publisher_document_builder.last_call["view_model"]
    all_references = [ref for ch in view_model["channels"] for ref in ch["references"]]
    assert "openssl/[,include_prerelease]@platform-2.0/tech" in all_references
    assert "zlib/[,include_prerelease]@platform-2.0/tech" in all_references
    assert not any("1.0.0" in ref or "1.2.11" in ref for ref in all_references)
