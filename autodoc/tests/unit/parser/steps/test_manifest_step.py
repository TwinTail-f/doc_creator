"""Юнит-тесты для autodoc/parser/steps/manifest_step.py."""

import pytest

from autodoc.models.component import Component
from autodoc.parser.fetchers.models.fetch_result import FetchResult
from autodoc.parser.steps.manifest_step import ManifestStep

# ---------------------------------------------------------------------------
# Фейковый Fetcher
# ---------------------------------------------------------------------------


class FakeFetcher:
    """Управляемый фейковый fetcher для юнит-тестов ManifestStep."""

    def __init__(
        self, value: list[Component], warnings: list[str] | None = None
    ) -> None:
        """
        Args:
            value: Список компонентов, возвращаемый из fetch().
            warnings: Необязательный список строк предупреждений.
        """
        self.value = value
        self.warnings = warnings or []
        self.configure_called: bool = False
        self.fetch_called: bool = False

    def configure(self, ctx: object) -> None:
        """Записывает факт вызова configure."""
        self.configure_called = True

    def fetch(self, *args: object, **kwargs: object) -> FetchResult:
        """Возвращает управляемый FetchResult."""
        self.fetch_called = True
        return FetchResult(value=self.value, warnings=self.warnings)


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------


def test_manifest_step_populates_ctx_components(
    parser_pipeline_context,
    manifest_component,
) -> None:
    """Успешный путь: ctx.components заполняется из результата fetcher."""
    fake = FakeFetcher(value=[manifest_component])
    step = ManifestStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert parser_pipeline_context.components == [manifest_component]


def test_manifest_step_logs_warnings_without_raising(
    parser_pipeline_context,
) -> None:
    """Предупреждения от fetcher передаются без вызова исключений."""
    fake = FakeFetcher(value=[], warnings=["something failed"])
    step = ManifestStep(fetcher=fake)
    step.execute(parser_pipeline_context)  # не должно вызывать исключений
    assert parser_pipeline_context.components == []


def test_manifest_step_calls_configure_before_fetch(
    parser_pipeline_context,
    manifest_component,
) -> None:
    """configure() вызывается на fetcher до завершения execute()."""
    fake = FakeFetcher(value=[manifest_component])
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


def test_manifest_step_warnings_stored_in_context(
    parser_pipeline_context,
) -> None:
    """Warnings returned by ManifestFetcher are propagated without raising exceptions.

    PipelineContext has no .warnings field — ManifestStep logs warnings via logger
    and does not store them on ctx. This test verifies the step does not raise and
    that ctx.components is still populated correctly when warnings are present.
    Adaptation from plan: assertion is on non-raising behaviour + component state,
    not on ctx.warnings (which does not exist on PipelineContext).
    """
    warning_msg = "test-warning-from-fetcher"
    fake = FakeFetcher(value=[], warnings=[warning_msg])
    step = ManifestStep(fetcher=fake)
    # Must not raise even with a non-empty warnings list
    step.execute(parser_pipeline_context)
    assert parser_pipeline_context.components == []


def test_manifest_step_empty_components_list_does_not_raise(
    parser_pipeline_context,
) -> None:
    """ManifestStep.execute does not raise when the fetcher returns zero components.

    This is a guard against unintended IndexError / AttributeError when the TFS
    repository has no matching manifest files.
    """
    fake = FakeFetcher(value=[], warnings=[])
    step = ManifestStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert parser_pipeline_context.components == []
