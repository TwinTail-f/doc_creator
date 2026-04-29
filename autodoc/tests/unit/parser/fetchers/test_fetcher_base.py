"""
Unit tests for autodoc/parser/fetchers/base.py.

Covers FetchResult data class and the BaseTFSFetcher two-phase invariant.
"""

from typing import Any

from autodoc.parser.fetchers.base import BaseTFSFetcher, FetchResult
from autodoc.parser.pipeline.context import PipelineContext

# ---------------------------------------------------------------------------
# Minimal concrete subclass used only in these tests
# ---------------------------------------------------------------------------


class _ConcreteFetcher(BaseTFSFetcher):
    """Minimal concrete BaseTFSFetcher subclass for testing the base class invariants."""

    def configure(self, ctx: PipelineContext) -> None:
        """Store the TFS client from context (standard BaseTFSFetcher pattern)."""
        self._tfs = ctx.tfs_client

    def fetch(self, *args: Any, **kwargs: Any) -> FetchResult:
        """Return an empty result; not exercised in base-class tests."""
        return FetchResult(value=[])


# ---------------------------------------------------------------------------
# 3.1 — FetchResult holds value and warnings
# ---------------------------------------------------------------------------


def test_fetch_result_holds_value_and_warnings() -> None:
    """FetchResult exposes the provided value and warnings list."""
    result: FetchResult = FetchResult(value=[1, 2], warnings=["w1"])

    assert result.value == [1, 2]
    assert result.warnings == ["w1"]


# ---------------------------------------------------------------------------
# 3.2 — FetchResult default warnings is empty list
# ---------------------------------------------------------------------------


def test_fetch_result_default_warnings_empty() -> None:
    """FetchResult.warnings defaults to an empty list when not supplied."""
    result: FetchResult = FetchResult(value="x")

    assert result.warnings == []


# ---------------------------------------------------------------------------
# 3.3 — BaseTFSFetcher: _tfs is None before configure is called
# ---------------------------------------------------------------------------


def test_base_tfs_fetcher_tfs_is_none_before_configure() -> None:
    """_tfs attribute is None immediately after construction, before configure()."""
    fetcher = _ConcreteFetcher()

    assert fetcher._tfs is None
