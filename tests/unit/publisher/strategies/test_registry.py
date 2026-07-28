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
from autodoc.publisher.strategies.registry import available_strategies, create_strategy
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
def test_all_three_strategy_types_registered() -> None:
    """available_strategies() включает 'release', 'profile_centric' и 'passports'."""
    strategies = available_strategies()
    assert "release" in strategies
    assert "profile_centric" in strategies
    assert "passports" in strategies
