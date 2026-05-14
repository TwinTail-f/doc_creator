"""Юнит-тесты для autodoc/parser/steps/manifest_step.py."""

import pytest

from autodoc.models.component import Component
from autodoc.parser.fetchers.models.fetch_result import FetchResult
from autodoc.parser.steps.manifest_step import ManifestStep


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------


def test_manifest_step_populates_ctx_components(
    parser_pipeline_context,
    manifest_component,
    make_fake_fetcher,
) -> None:
    """Успешный путь: ctx.components заполняется из результата fetcher."""
    fake = make_fake_fetcher(value=[manifest_component])
    step = ManifestStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert parser_pipeline_context.components == [manifest_component]


_EMPTY_NO_WARNINGS: list[str] = []
_EMPTY_WITH_WARNING: list[str] = ["something failed"]


@pytest.mark.parametrize(
    "warnings",
    [_EMPTY_NO_WARNINGS, _EMPTY_WITH_WARNING],
    ids=["no-warnings", "with-warning"],
)
def test_manifest_step_empty_result_does_not_raise(
    parser_pipeline_context,
    make_fake_fetcher,
    warnings: list[str],
) -> None:
    """ManifestStep must not raise when the fetcher returns zero components.

    Covers both the no-warning and warning-present variants.
    Warnings are logged internally — PipelineContext has no .warnings field.
    """
    fake = make_fake_fetcher(value=[], warnings=warnings)
    step = ManifestStep(fetcher=fake)
    step.execute(parser_pipeline_context)  # must not raise
    assert parser_pipeline_context.components == []


def test_manifest_step_calls_configure_before_fetch(
    parser_pipeline_context,
    manifest_component,
    make_fake_fetcher,
) -> None:
    """configure() вызывается на fetcher до завершения execute()."""
    fake = make_fake_fetcher(value=[manifest_component])
    step = ManifestStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert fake.configure_called is True


def test_manifest_step_has_name() -> None:
    """ManifestStep.name задан и не пуст."""
    assert ManifestStep.name != ""


def test_manifest_step_is_critical() -> None:
    """ManifestStep является критичным шагом пайплайна."""
    assert ManifestStep.is_critical is True


# ---------------------------------------------------------------------------
# New tests: UC-M-1/3/5 step-level coverage
# ---------------------------------------------------------------------------



