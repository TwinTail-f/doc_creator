"""
Юнит-тесты для autodoc/parser/fetchers/base.py.

Охватывает датакласс FetchResult и двухфазный инвариант BaseTFSFetcher.
"""

from typing import Any

import pytest

from autodoc.parser.fetchers.base_tfs_fetcher import BaseTFSFetcher
from autodoc.parser.fetchers.models.fetch_result import FetchResult
from autodoc.parser.pipeline.context import PipelineContext


class _ConcreteFetcher(BaseTFSFetcher):
    """Минимальный конкретный подкласс BaseTFSFetcher для тестирования инвариантов базового класса."""

    def _configure(self, ctx: PipelineContext) -> None:
        """Сохраняет TFS-клиент из контекста (стандартный шаблон BaseTFSFetcher)."""
        self._tfs = ctx.tfs_client

    def _fetch(self, *args: Any, **kwargs: Any) -> FetchResult:
        """Возвращает пустой результат."""
        return FetchResult(value=[])


@pytest.mark.contract
def test_fetch_result_default_warnings_empty() -> None:
    """FetchResult.warnings по умолчанию является пустым списком, если не задан."""
    result: FetchResult = FetchResult(value="x")

    assert result.warnings == []


@pytest.mark.contract
def test_base_fetcher_fetch_before_configure_raises() -> None:
    """Вызов fetch() до configure() нарушает двухфазный инвариант и выбрасывает AssertionError."""
    fetcher = _ConcreteFetcher()
    with pytest.raises(AssertionError, match="configure"):
        fetcher.fetch()
