"""Юнит-тесты для autodoc/parser/steps/conan_step.py."""

import pytest

from autodoc.parser.conan.models.conan_enrichment_result import ConanEnrichmentResult
from autodoc.parser.fetchers.models.fetch_result import FetchResult
from autodoc.parser.steps.conan_step import ConanEnrichStep

# ---------------------------------------------------------------------------
# Сигнальный пустой результат, используемый в тестах
# ---------------------------------------------------------------------------

EMPTY_CONAN_RESULT: ConanEnrichmentResult = ConanEnrichmentResult(
    release_data={}, profile_data={}, errors={}
)


# ---------------------------------------------------------------------------
# Фейковый Fetcher
# ---------------------------------------------------------------------------


class FakeFetcher:
    """Управляемый фейковый fetcher для юнит-тестов ConanEnrichStep."""

    def __init__(
        self,
        value: ConanEnrichmentResult,
        warnings: list[str] | None = None,
    ) -> None:
        """
        Args:
            value: ConanEnrichmentResult, возвращаемый из fetch().
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


def test_conan_step_stores_conan_report_in_intermediate(
    parser_pipeline_context,
) -> None:
    """ctx.intermediate['conan_report'] заполняется после execute."""
    fake = FakeFetcher(value=EMPTY_CONAN_RESULT)
    step = ConanEnrichStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert "conan_report" in parser_pipeline_context.intermediate


def test_conan_step_is_not_critical() -> None:
    """ConanEnrichStep является некритичным шагом пайплайна."""
    assert ConanEnrichStep.is_critical is False


def test_conan_step_warnings_do_not_raise(
    parser_pipeline_context,
) -> None:
    """Предупреждения от fetcher не вызывают исключений."""
    fake = FakeFetcher(value=EMPTY_CONAN_RESULT, warnings=["conan timeout"])
    step = ConanEnrichStep(fetcher=fake)
    step.execute(parser_pipeline_context)  # не должно вызывать исключений
