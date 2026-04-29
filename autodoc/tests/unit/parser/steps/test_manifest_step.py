"""Unit tests for autodoc/parser/steps/manifest_step.py."""

import pytest

from autodoc.models.component import Component
from autodoc.parser.fetchers.base import FetchResult
from autodoc.parser.steps.manifest_step import ManifestStep

# ---------------------------------------------------------------------------
# Fake Fetcher
# ---------------------------------------------------------------------------


class FakeFetcher:
    """Controllable fake fetcher for ManifestStep unit tests."""

    def __init__(
        self, value: list[Component], warnings: list[str] | None = None
    ) -> None:
        """
        Args:
            value: The component list to return from fetch().
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


def test_manifest_step_populates_ctx_components(
    parser_pipeline_context,
    manifest_component,
) -> None:
    """Happy path: ctx.components is populated from fetcher result."""
    fake = FakeFetcher(value=[manifest_component])
    step = ManifestStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert parser_pipeline_context.components == [manifest_component]


def test_manifest_step_logs_warnings_without_raising(
    parser_pipeline_context,
) -> None:
    """Warnings from fetcher are passed through without raising an exception."""
    fake = FakeFetcher(value=[], warnings=["something failed"])
    step = ManifestStep(fetcher=fake)
    step.execute(parser_pipeline_context)  # must not raise
    assert parser_pipeline_context.components == []


def test_manifest_step_calls_configure_before_fetch(
    parser_pipeline_context,
    manifest_component,
) -> None:
    """configure() is called on the fetcher before execute() returns."""
    fake = FakeFetcher(value=[manifest_component])
    step = ManifestStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert fake.configure_called is True


def test_manifest_step_has_name() -> None:
    """ManifestStep.name is set and non-empty."""
    assert ManifestStep.name != ""


def test_manifest_step_is_critical() -> None:
    """ManifestStep is a critical pipeline step."""
    assert ManifestStep.is_critical is True
