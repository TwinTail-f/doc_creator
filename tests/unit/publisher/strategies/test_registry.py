"""
Тесты для autodoc.publisher.strategies.registry.

Стратегия тестирования:
- create_strategy()/available_strategies() проверяются напрямую, без моков —
  реестр представляет собой чистое сопоставление строк классам стратегий.
"""

from pathlib import Path

import pytest

from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.strategies.passports_strategy import PassportsStrategy
from autodoc.publisher.strategies.registry import STRATEGIES, available_strategies, create_strategy
from tests.unit.publisher.conftest import FakeConfluenceClient
from tests.unit.publisher.strategies.conftest import FakeDocumentBuilder

_SPACE: str = "TEST"
_ROOT_PAGE_ID: str = "root-001"


@pytest.mark.contract
def test_create_strategy_unknown_type_raises_value_error() -> None:
    """create_strategy() с нераспознанным strategy_type выбрасывает ValueError."""
    with pytest.raises(ValueError):
        create_strategy("not_a_real_strategy")


@pytest.mark.contract
def test_create_strategy_passports_returns_passports_strategy_instance(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
) -> None:
    """create_strategy('passports', ...) собирает и возвращает экземпляр PassportsStrategy."""
    strategy = create_strategy(
        "passports",
        confluence_client=publisher_confluence_client,
        document_builder=publisher_document_builder,
        parsed_data=publisher_parsed_result,
        space=_SPACE,
        root_page_id=_ROOT_PAGE_ID,
        data_dir=tmp_path,
    )
    assert isinstance(strategy, PassportsStrategy)


@pytest.mark.contract
def test_available_strategies_matches_registered_strategy_types() -> None:
    """
    available_strategies() содержит ровно те ключи, что зарегистрированы в STRATEGIES.

    Сравниваем с самим STRATEGIES, а не с захардкоженным списком имён и уж
    тем более не с числом: список стратегий не статичен, появятся новые —
    этот тест продолжит быть верным без единой правки. Актуальный список
    стратегий смотреть в STRATEGIES (autodoc/publisher/strategies/registry.py).
    """
    assert set(available_strategies()) == set(STRATEGIES)


@pytest.mark.contract
@pytest.mark.parametrize(
    "strategy_type, expected_is_single_page",
    [
        pytest.param("release", True, id="release"),
        pytest.param("profile_centric", True, id="profile_centric"),
        pytest.param("passports", False, id="passports"),
        pytest.param("kit_fixed", True, id="kit_fixed"),
        pytest.param("kit_latest", True, id="kit_latest"),
    ],
)
def test_is_single_page_flag_matches_strategy_kind(
    strategy_type: str, expected_is_single_page: bool
) -> None:
    """IS_SINGLE_PAGE верно проставлен для каждой зарегистрированной стратегии."""
    assert STRATEGIES[strategy_type].IS_SINGLE_PAGE is expected_is_single_page


@pytest.mark.contract
@pytest.mark.parametrize(
    "strategy_type",
    [
        pytest.param("kit_fixed", id="kit_fixed"),
        pytest.param("kit_latest", id="kit_latest"),
    ],
)
def test_create_strategy_kit_pages_return_correct_instance_type(
    strategy_type: str,
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
) -> None:
    """
    create_strategy('kit_fixed'|'kit_latest', ...) собирает экземпляр
    зарегистрированного класса стратегии.
    """
    strategy = create_strategy(
        strategy_type,
        confluence_client=publisher_confluence_client,
        document_builder=publisher_document_builder,
        parsed_data=publisher_parsed_result,
        space=_SPACE,
        page_title="Test",
        template_name="embedding_kit.jinja2",
        parent_id="parent-001",
        data_dir=tmp_path,
    )
    assert isinstance(strategy, STRATEGIES[strategy_type])
