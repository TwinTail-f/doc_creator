"""
Тесты для autodoc.publisher.strategies.release_strategy.ReleasePageStrategy.

Стратегия тестирования:
- ReleasePageStrategy делегирует работу _publish_single_page (проверяется по результату).
- PassportPageRegistry.load() мокается, когда include_passport_links=True.
- FakeConfluenceClient / FakeDocumentBuilder обеспечивают детерминированный ввод-вывод.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from autodoc.exceptions import ConfluenceError
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.page_manager.passport_registry import PassportPageRegistry
from autodoc.publisher.strategies.registry import create_strategy
from autodoc.publisher.strategies.release_strategy import ReleasePageStrategy
from autodoc.publisher.converters.full_release_converter import FullReleaseConverter
from tests.unit.publisher.conftest import (
    FakeConfluenceClient,
    FakeDocumentBuilder,
)

_SPACE: str = "TEST"
_PAGE_TITLE: str = "Platform 2.0 Release Docs"
_TEMPLATE_NAME: str = "release_doc.jinja2"
_PARENT_ID: str = "parent-001"


def make_release_strategy(
    client: FakeConfluenceClient,
    builder: FakeDocumentBuilder,
    data: ParsedResult,
    tmp_path: Path,
    include_passport_links: bool = True,
) -> ReleasePageStrategy:
    """Создаёт ReleasePageStrategy с разумными значениями по умолчанию для юнит-тестов."""
    return ReleasePageStrategy(
        confluence_client=client,
        document_builder=builder,
        parsed_data=data,
        space=_SPACE,
        page_title=_PAGE_TITLE,
        template_name=_TEMPLATE_NAME,
        parent_id=_PARENT_ID,
        include_passport_links=include_passport_links,
        data_dir=tmp_path,
    )


# ReleasePageStrategy.execute()
@pytest.mark.infrastructure
def test_release_strategy_execute_calls_publish_single_page(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """execute() в конечном счёте вызывает client.publish_page с корректным заголовком."""
    mocker.patch.object(PassportPageRegistry, "load", return_value={})
    strategy = make_release_strategy(
        publisher_confluence_client,
        publisher_document_builder,
        publisher_parsed_result,
        tmp_path,
    )
    strategy.execute()
    publish_calls = [
        c for c in publisher_confluence_client.calls if c["method"] == "publish_page"
    ]
    assert len(publish_calls) == 1
    assert publish_calls[0]["title"] == _PAGE_TITLE


@pytest.mark.business_logic
def test_release_strategy_execute_returns_success_report(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """Успешный execute() возвращает report.success=True и pages_published=1."""
    mocker.patch.object(PassportPageRegistry, "load", return_value={})
    strategy = make_release_strategy(
        publisher_confluence_client,
        publisher_document_builder,
        publisher_parsed_result,
        tmp_path,
    )
    report = strategy.execute()
    assert report.success is True
    assert report.pages_published == 1


@pytest.mark.business_logic
def test_release_strategy_loads_registry_when_include_links_true(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """Когда include_passport_links=True, PassportPageRegistry.load() вызывается один раз."""
    mock_load = mocker.patch.object(PassportPageRegistry, "load", return_value={})
    strategy = make_release_strategy(
        publisher_confluence_client,
        publisher_document_builder,
        publisher_parsed_result,
        tmp_path,
        include_passport_links=True,
    )
    strategy.execute()
    mock_load.assert_called_once()


@pytest.mark.business_logic
def test_release_strategy_skips_registry_load_when_include_links_false(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """Когда include_passport_links=False, PassportPageRegistry.load() никогда не вызывается."""
    mock_load = mocker.patch.object(PassportPageRegistry, "load", return_value={})
    strategy = make_release_strategy(
        publisher_confluence_client,
        publisher_document_builder,
        publisher_parsed_result,
        tmp_path,
        include_passport_links=False,
    )
    strategy.execute()
    mock_load.assert_not_called()


@pytest.mark.business_logic
def test_release_strategy_execute_returns_failure_on_client_error(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """Если publish_page выбрасывает ConfluenceError, report.success равен False."""
    mocker.patch.object(PassportPageRegistry, "load", return_value={})

    def raise_confluence_error(*args: Any, **kwargs: Any) -> None:
        raise ConfluenceError("connection refused")

    publisher_confluence_client.publish_page = raise_confluence_error

    strategy = make_release_strategy(
        publisher_confluence_client,
        publisher_document_builder,
        publisher_parsed_result,
        tmp_path,
    )
    report = strategy.execute()
    assert report.success is False


# Фабрика и подключение конвертера
@pytest.mark.contract
def test_release_make_converter_creates_full_release_converter(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
) -> None:
    """create_strategy('release', ...) подключает FullReleaseConverter с переданным include_passport_links."""
    strategy = create_strategy(
        "release",
        confluence_client=publisher_confluence_client,
        document_builder=publisher_document_builder,
        parsed_data=publisher_parsed_result,
        space=_SPACE,
        page_title=_PAGE_TITLE,
        template_name=_TEMPLATE_NAME,
        data_dir=tmp_path,
        include_passport_links=False,
    )
    assert isinstance(strategy._converter, FullReleaseConverter)
    assert strategy._converter._include_passport_links is False


@pytest.mark.business_logic
def test_links_injected_into_view_model_from_registry(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """
    BL-RS-04
    Бизнес-правило: после загрузки реестра ссылки на паспорта внедряются в
    view-model, чтобы шаблон мог отрендерить кликабельные ссылки на каждую страницу паспорта.

    Предусловия:
        - PassportPageRegistry.load возвращает непустой pages_map для 'openssl'.
        - Захватывающий builder записывает все view_model, переданные в build().

    Шаги:
        1. Патчим registry.load, чтобы он возвращал pages_map с openssl/1.0.0.
        2. Используем CapturingBuilder вместо стандартного FakeDocumentBuilder.
        3. Вызываем execute() с include_passport_links=True.

    Ожидаемый результат:
        builder.build() вызывается ровно один раз.
        view_model для компонента 'openssl' содержит непустую запись
        'passport_versions', полученную из реестра.
    """
    pages_map = {
        "openssl": {
            "1.0.0": {
                "page_id": "123",
                "page_title": "Документация openssl 1.0.0",
                "version": 1,
            }
        }
    }
    mocker.patch.object(PassportPageRegistry, "load", return_value=pages_map)

    captured_view_models: list[dict] = []

    class CapturingBuilder:
        def build(self, template_name: str, view_model: dict) -> str:
            captured_view_models.append(view_model)
            return "<html>test</html>"

    strategy = ReleasePageStrategy(
        confluence_client=publisher_confluence_client,
        document_builder=CapturingBuilder(),
        parsed_data=publisher_parsed_result,
        space=_SPACE,
        page_title=_PAGE_TITLE,
        template_name=_TEMPLATE_NAME,
        parent_id=_PARENT_ID,
        include_passport_links=True,
        data_dir=tmp_path,
    )
    strategy.execute()

    assert len(captured_view_models) == 1, "builder.build() должен быть вызван ровно один раз"
    view = captured_view_models[0]
    openssl_view = next(
        (c for c in view.get("components", []) if c.get("name") == "openssl"),
        None,
    )
    assert openssl_view is not None, "компонент openssl должен присутствовать в view_model"
    passport_versions = openssl_view.get("passport_versions", {})
    assert (
        len(passport_versions) > 0
    ), "passport_versions должен быть внедрён из реестра, когда include_passport_links=True"
