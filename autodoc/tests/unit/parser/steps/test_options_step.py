"""Unit tests for autodoc/parser/steps/options_step.py."""

import pytest

from autodoc.models.types import OptionsMap
from autodoc.parser.fetchers.base import FetchResult
from autodoc.parser.steps.options_step import OptionsResolveStep

# ---------------------------------------------------------------------------
# Fake Fetcher
# ---------------------------------------------------------------------------


class FakeFetcher:
    """Controllable fake fetcher for OptionsResolveStep unit tests."""

    def __init__(self, value: OptionsMap, warnings: list[str] | None = None) -> None:
        """
        Args:
            value: The options map to return from fetch().
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


def test_options_step_stores_options_map_in_intermediate(
    parser_pipeline_context,
) -> None:
    """ctx.intermediate['options_map'] is populated with the fetcher result."""
    expected: OptionsMap = {("comp", "1.0", "tech"): {"1": ""}}
    fake = FakeFetcher(value=expected)
    step = OptionsResolveStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert parser_pipeline_context.intermediate["options_map"] == expected


def test_options_step_applies_options_to_components(
    parser_pipeline_context,
    manifest_component,
) -> None:
    """DataEnricher.apply_options is called: matching component release gets build_option_sets."""
    parser_pipeline_context.components = [manifest_component]
    # Key must match the fixture: name="openssl", version="1.0.0", channel="tech"
    options_map: OptionsMap = {("openssl", "1.0.0", "tech"): {"1": "shared=True"}}
    fake = FakeFetcher(value=options_map)
    step = OptionsResolveStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert parser_pipeline_context.components[0].releases[0].build_option_sets != []


def test_options_step_is_not_critical() -> None:
    """OptionsResolveStep is a non-critical pipeline step."""
    assert OptionsResolveStep.is_critical is False
