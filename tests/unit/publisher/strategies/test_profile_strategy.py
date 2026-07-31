"""
Тесты для autodoc.publisher.strategies.profile_strategy.ProfileCentricStrategy.

Стратегия тестирования:
- ProfileCentricStrategy делегирует работу _publish_single_page (проверяется по результату).
- PassportPageRegistry.load() мокается, когда include_passport_links=True.
- FakeConfluenceClient / FakeDocumentBuilder обеспечивают детерминированный ввод-вывод.
"""

from pathlib import Path
from typing import Any

import pytest
from pytest_mock import MockerFixture

from autodoc.exceptions import ConfluenceError
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.page_manager.passport_registry import PassportPageRegistry
from autodoc.publisher.strategies.profile_strategy import ProfileCentricStrategy
from tests.unit.publisher.conftest import FakeConfluenceClient
from tests.unit.publisher.strategies.conftest import FakeDocumentBuilder

_SPACE: str = "TEST"
_PAGE_TITLE: str = "Platform 2.0 Profile-Centric Docs"
_TEMPLATE_NAME: str = "profile_centric.jinja2"
_PARENT_ID: str = "parent-001"


def make_profile_strategy(
    client: FakeConfluenceClient,
    builder: FakeDocumentBuilder,
    data: ParsedResult,
    tmp_path: Path,
    include_passport_links: bool = True,
) -> ProfileCentricStrategy:
    """Создаёт ProfileCentricStrategy с разумными значениями по умолчанию для юнит-тестов."""
    return ProfileCentricStrategy(
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


# ProfileCentricStrategy.execute()
@pytest.mark.business_logic
def test_profile_centric_strategy_execute_returns_success_report(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    """Успешный execute() возвращает report.success=True и pages_published=1."""
    mocker.patch.object(PassportPageRegistry, "load", return_value={})
    strategy = make_profile_strategy(
        publisher_confluence_client,
        publisher_document_builder,
        publisher_parsed_result,
        tmp_path,
    )
    report = strategy.execute()
    assert report.success is True
    assert report.pages_published == 1


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "include_passport_links, expected_load_calls",
    [
        pytest.param(True, 1, id="include-links-true-loads-registry"),
        pytest.param(False, 0, id="include-links-false-skips-registry"),
    ],
)
def test_profile_centric_strategy_loads_registry_iff_include_links_true(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
    mocker: MockerFixture,
    include_passport_links: bool,
    expected_load_calls: int,
) -> None:
    """PassportPageRegistry.load() вызывается ровно тогда, когда include_passport_links=True."""
    mock_load = mocker.patch.object(PassportPageRegistry, "load", return_value={})
    strategy = make_profile_strategy(
        publisher_confluence_client,
        publisher_document_builder,
        publisher_parsed_result,
        tmp_path,
        include_passport_links=include_passport_links,
    )
    strategy.execute()
    assert mock_load.call_count == expected_load_calls


@pytest.mark.business_logic
def test_profile_centric_strategy_execute_calls_publish_page(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    """execute() вызывает ровно один publish_page с ожидаемым заголовком."""
    mocker.patch.object(PassportPageRegistry, "load", return_value={})
    strategy = make_profile_strategy(
        publisher_confluence_client,
        publisher_document_builder,
        publisher_parsed_result,
        tmp_path,
    )
    strategy.execute()
    publish_calls = [c for c in publisher_confluence_client.calls if c["method"] == "publish_page"]
    assert len(publish_calls) == 1
    assert publish_calls[0]["title"] == _PAGE_TITLE


@pytest.mark.business_logic
def test_profile_centric_strategy_execute_returns_failure_on_client_error(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    """Если publish_page выбрасывает ConfluenceError, report.success равен False."""
    mocker.patch.object(PassportPageRegistry, "load", return_value={})

    def raise_confluence_error(*args: Any, **kwargs: Any) -> None:
        raise ConfluenceError("timeout")

    publisher_confluence_client.publish_page = raise_confluence_error

    strategy = make_profile_strategy(
        publisher_confluence_client,
        publisher_document_builder,
        publisher_parsed_result,
        tmp_path,
    )
    report = strategy.execute()
    assert report.success is False


@pytest.mark.business_logic
def test_profile_links_injected_into_view_model_from_registry(
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
    mocker: MockerFixture,
    publisher_capturing_document_builder: Any,
) -> None:
    """
    Правило: после загрузки реестра паспортов ссылки на паспорта внедряются в
    view-model профиль-центричной документации через inject_links_for_profiles,
    чтобы шаблон мог отрендерить кликабельную ссылку для каждого компонента.
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

    strategy = ProfileCentricStrategy(
        confluence_client=FakeConfluenceClient(),
        document_builder=publisher_capturing_document_builder,
        parsed_data=publisher_parsed_result,
        space=_SPACE,
        page_title=_PAGE_TITLE,
        template_name=_TEMPLATE_NAME,
        parent_id=_PARENT_ID,
        include_passport_links=True,
        data_dir=tmp_path,
    )
    strategy.execute()

    captured_view_models = publisher_capturing_document_builder.captured_view_models
    assert len(captured_view_models) == 1, "builder.build() должен быть вызван ровно один раз"
    view = captured_view_models[0]
    profile = next(
        (p for p in view.get("profiles", []) if p.get("profile_name") == "hw-linux-x86_64-gcc10"),
        None,
    )
    assert profile is not None, "профиль hw-linux-x86_64-gcc10 должен присутствовать в view_model"
    openssl_comp = next(
        (c for c in profile.get("channels", {}).get("tech", []) if c.get("name") == "openssl"),
        None,
    )
    assert openssl_comp is not None, "компонент openssl должен присутствовать в канале tech"
    assert (
        openssl_comp.get("passport_link") is not None
    ), "passport_link должен быть внедрён из реестра, когда include_passport_links=True"
