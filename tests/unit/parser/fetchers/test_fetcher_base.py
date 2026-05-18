"""
Юнит-тесты для autodoc/parser/fetchers/base.py.

Охватывает датакласс FetchResult и двухфазный инвариант BaseTFSFetcher.
"""

from typing import Any

import pytest

from autodoc.parser.fetchers.base_tfs_fetcher import BaseTFSFetcher
from autodoc.parser.fetchers.models.fetch_result import FetchResult
from autodoc.parser.pipeline.context import PipelineContext

# ---------------------------------------------------------------------------
# Минимальный конкретный подкласс, используемый только в этих тестах
# ---------------------------------------------------------------------------


class _ConcreteFetcher(BaseTFSFetcher):
    """Минимальный конкретный подкласс BaseTFSFetcher для тестирования инвариантов базового класса."""

    def configure(self, ctx: PipelineContext) -> None:
        """Сохраняет TFS-клиент из контекста (стандартный шаблон BaseTFSFetcher)."""
        self._tfs = ctx.tfs_client
        self._configured = True

    def fetch(self, *args: Any, **kwargs: Any) -> FetchResult:
        """Проверяет что configure() вызван, затем возвращает пустой результат."""
        self._assert_configured()
        return FetchResult(value=[])


# ---------------------------------------------------------------------------
# FetchResult хранит value и warnings
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_fetch_result_holds_value_and_warnings() -> None:
    """FetchResult предоставляет переданные value и список warnings."""
    result: FetchResult = FetchResult(value=[1, 2], warnings=["w1"])

    assert result.value == [1, 2]
    assert result.warnings == ["w1"]


# ---------------------------------------------------------------------------
# warnings в FetchResult по умолчанию — пустой список
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_fetch_result_default_warnings_empty() -> None:
    """FetchResult.warnings по умолчанию является пустым списком, если не задан."""
    result: FetchResult = FetchResult(value="x")

    assert result.warnings == []


# ---------------------------------------------------------------------------
# BaseTFSFetcher: _tfs равен None до вызова configure
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_base_tfs_fetcher_tfs_is_none_before_configure() -> None:
    """Атрибут _tfs равен None сразу после создания, до вызова configure()."""
    fetcher = _ConcreteFetcher()

    assert fetcher._tfs is None


# ---------------------------------------------------------------------------
# T3.8 — configure() → fetch() ordering contract
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_base_fetcher_fetch_before_configure_raises() -> None:
    """Calling fetch() before configure() must raise RuntimeError.

    The two-phase protocol is enforced at the base class level to prevent
    misconfigured fetchers from silently returning empty or stale data.
    """
    fetcher = _ConcreteFetcher()
    with pytest.raises(RuntimeError, match="configure"):
        fetcher.fetch()
