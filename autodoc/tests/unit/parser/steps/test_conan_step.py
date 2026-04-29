"""Unit tests for autodoc/parser/steps/conan_step.py."""

import pytest

from autodoc.models.conan_result import ConanEnrichmentResult
from autodoc.parser.fetchers.base import FetchResult
from autodoc.parser.steps.conan_step import ConanEnrichStep

# ---------------------------------------------------------------------------
# Sentinel empty result used across tests
# ---------------------------------------------------------------------------

EMPTY_CONAN_RESULT: ConanEnrichmentResult = ConanEnrichmentResult(
    release_data={}, profile_data={}, errors={}
)


# ---------------------------------------------------------------------------
# Fake Fetcher
# ---------------------------------------------------------------------------


class FakeFetcher:
    """Controllable fake fetcher for ConanEnrichStep unit tests."""

    def __init__(
        self,
        value: ConanEnrichmentResult,
        warnings: list[str] | None = None,
    ) -> None:
        """
        Args:
            value: The ConanEnrichmentResult to return from fetch().
            warnings: Optional list of warning strings.
        """
        self.value = value
        self.warnings = warnings or []
        self.configure_called: bool = False
        self.fetch_called: bool = False

    def configure(self, ctx: object) -> None:
        """Record that configure was called."""
        self.configure_called = True

    def fetch(self, *args: object, **kwargs: object) -> FetchResult:
        """Return controlled FetchResult."""
        self.fetch_called = True
        return FetchResult(value=self.value, warnings=self.warnings)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_conan_step_stores_conan_report_in_intermediate(
    parser_pipeline_context,
) -> None:
    """ctx.intermediate['conan_report'] is populated after execute."""
    fake = FakeFetcher(value=EMPTY_CONAN_RESULT)
    step = ConanEnrichStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert "conan_report" in parser_pipeline_context.intermediate


def test_conan_step_is_not_critical() -> None:
    """ConanEnrichStep is a non-critical pipeline step."""
    assert ConanEnrichStep.is_critical is False


def test_conan_step_warnings_do_not_raise(
    parser_pipeline_context,
) -> None:
    """Warnings from the fetcher do not cause an exception."""
    fake = FakeFetcher(value=EMPTY_CONAN_RESULT, warnings=["conan timeout"])
    step = ConanEnrichStep(fetcher=fake)
    step.execute(parser_pipeline_context)  # must not raise
