"""
Тесты для autodoc.publisher.strategies.kit_fixed_strategy.KitFixedPageStrategy.

Стратегия тестирования:
- KitFixedPageStrategy делегирует работу _publish_single_page (проверяется по результату).
- В отличие от ReleasePageStrategy/ProfileCentricPageStrategy, здесь нет реестра
  паспортов — KitFixedConverter.wants_passport_links всегда False и не читает
  PassportPageRegistry, это тоже часть контракта и проверяется явно.
- FakeConfluenceClient / FakeDocumentBuilder обеспечивают детерминированный ввод-вывод.
"""

from pathlib import Path
from typing import Any

import pytest
from pytest_mock import MockerFixture

from autodoc.exceptions import ConfluenceError
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.page_manager.passport_registry import PassportPageRegistry
from autodoc.publisher.strategies.kit_fixed_strategy import KitFixedPageStrategy
from autodoc.publisher.strategies.registry import create_strategy
from tests.unit.publisher.conftest import FakeConfluenceClient
from tests.unit.publisher.strategies.conftest import FakeDocumentBuilder

_SPACE: str = "TEST"
_PAGE_TITLE: str = "Комплект для встраивания компонентов platform"
_TEMPLATE_NAME: str = "embedding_kit.jinja2"
_PARENT_ID: str = "parent-001"


def make_kit_fixed_strategy(
    client: FakeConfluenceClient,
    builder: FakeDocumentBuilder,
    data: ParsedResult,
    tmp_path: Path,
) -> KitFixedPageStrategy:
    """Создаёт KitFixedPageStrategy с разумными значениями по умолчанию для юнит-тестов."""
    return KitFixedPageStrategy(
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
    strategy = make_kit_fixed_strategy(
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
    strategy = make_kit_fixed_strategy(
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

    strategy = make_kit_fixed_strategy(
        publisher_confluence_client,
        publisher_document_builder,
        publisher_multi_component_result,
        tmp_path,
    )
    report = strategy.execute()
    assert report.success is False


@pytest.mark.contract
def test_include_passport_links_kwarg_has_no_effect(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_multi_component_result: ParsedResult,
    tmp_path: Path,
) -> None:
    """Явная попытка передать include_passport_links=True тихо отбрасывается —
    у KitFixedConverter нет понятия ссылок на паспорта (wants_passport_links
    всегда False), сколько бы это ни просил вызывающий."""
    strategy = KitFixedPageStrategy(
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
    assert strategy._converter.wants_passport_links is False


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
    strategy = make_kit_fixed_strategy(
        publisher_confluence_client,
        publisher_document_builder,
        publisher_multi_component_result,
        tmp_path,
    )
    strategy.execute()
    assert mock_load.call_count == 0


@pytest.mark.contract
def test_make_converter_creates_kit_fixed_converter(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_multi_component_result: ParsedResult,
    tmp_path: Path,
) -> None:
    """create_strategy('kit_fixed', ...) подключает KitFixedConverter — view_model
    имеет форму channels/version_column_title, а не components (как у release)."""
    strategy = create_strategy(
        "kit_fixed",
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
    assert "channels" in view_model, "форма view_model должна соответствовать KitFixedConverter"
    assert view_model["version_column_title"] == "Фиксированная версия"


@pytest.mark.business_logic
def test_view_model_contains_exact_conan_references_from_data(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_multi_component_result: ParsedResult,
    tmp_path: Path,
) -> None:
    """Отрендеренный view_model содержит точные Conan-ссылки из ParsedResult (не
    диапазоны/wildcard'ы — это отличает kit_fixed от kit_latest)."""
    strategy = make_kit_fixed_strategy(
        publisher_confluence_client,
        publisher_document_builder,
        publisher_multi_component_result,
        tmp_path,
    )
    strategy.execute()

    view_model = publisher_document_builder.last_call["view_model"]
    all_references = [ref for ch in view_model["channels"] for ref in ch["references"]]
    assert "openssl/1.0.0@platform/2.0-tech" in all_references
    assert "zlib/1.2.11@platform/2.0-tech" in all_references
