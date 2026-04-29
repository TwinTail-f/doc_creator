"""
Юнит-тесты для autodoc/parser/fetchers/base.py.

Охватывает датакласс FetchResult и двухфазный инвариант BaseTFSFetcher.
"""

from typing import Any

from autodoc.parser.fetchers.base import BaseTFSFetcher, FetchResult
from autodoc.parser.pipeline.context import PipelineContext

# ---------------------------------------------------------------------------
# Минимальный конкретный подкласс, используемый только в этих тестах
# ---------------------------------------------------------------------------


class _ConcreteFetcher(BaseTFSFetcher):
    """Минимальный конкретный подкласс BaseTFSFetcher для тестирования инвариантов базового класса."""

    def configure(self, ctx: PipelineContext) -> None:
        """Сохраняет TFS-клиент из контекста (стандартный шаблон BaseTFSFetcher)."""
        self._tfs = ctx.tfs_client

    def fetch(self, *args: Any, **kwargs: Any) -> FetchResult:
        """Возвращает пустой результат; не используется в тестах базового класса."""
        return FetchResult(value=[])


# ---------------------------------------------------------------------------
# FetchResult хранит value и warnings
# ---------------------------------------------------------------------------


def test_fetch_result_holds_value_and_warnings() -> None:
    """FetchResult предоставляет переданные value и список warnings."""
    result: FetchResult = FetchResult(value=[1, 2], warnings=["w1"])

    assert result.value == [1, 2]
    assert result.warnings == ["w1"]


# ---------------------------------------------------------------------------
# warnings в FetchResult по умолчанию — пустой список
# ---------------------------------------------------------------------------


def test_fetch_result_default_warnings_empty() -> None:
    """FetchResult.warnings по умолчанию является пустым списком, если не задан."""
    result: FetchResult = FetchResult(value="x")

    assert result.warnings == []


# ---------------------------------------------------------------------------
# BaseTFSFetcher: _tfs равен None до вызова configure
# ---------------------------------------------------------------------------


def test_base_tfs_fetcher_tfs_is_none_before_configure() -> None:
    """Атрибут _tfs равен None сразу после создания, до вызова configure()."""
    fetcher = _ConcreteFetcher()

    assert fetcher._tfs is None
