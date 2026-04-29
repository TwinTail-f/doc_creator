"""Юнит-тесты для autodoc/parser/steps/options_step.py."""

import pytest

from autodoc.models.types import OptionsMap
from autodoc.parser.fetchers.base import FetchResult
from autodoc.parser.steps.options_step import OptionsResolveStep

# ---------------------------------------------------------------------------
# Фейковый Fetcher
# ---------------------------------------------------------------------------


class FakeFetcher:
    """Управляемый фейковый fetcher для юнит-тестов OptionsResolveStep."""

    def __init__(self, value: OptionsMap, warnings: list[str] | None = None) -> None:
        """
        Args:
            value: Карта опций, возвращаемая из fetch().
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


def test_options_step_stores_options_map_in_intermediate(
    parser_pipeline_context,
) -> None:
    """ctx.intermediate['options_map'] заполняется результатом fetcher."""
    expected: OptionsMap = {("comp", "1.0", "tech"): {"1": ""}}
    fake = FakeFetcher(value=expected)
    step = OptionsResolveStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert parser_pipeline_context.intermediate["options_map"] == expected


def test_options_step_applies_options_to_components(
    parser_pipeline_context,
    manifest_component,
) -> None:
    """DataEnricher.apply_options вызывается: совпадающий релиз компонента получает build_option_sets."""
    parser_pipeline_context.components = [manifest_component]
    # Ключ должен совпадать с фикстурой: name="openssl", version="1.0.0", channel="tech"
    options_map: OptionsMap = {("openssl", "1.0.0", "tech"): {"1": "shared=True"}}
    fake = FakeFetcher(value=options_map)
    step = OptionsResolveStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert parser_pipeline_context.components[0].releases[0].build_option_sets != []


def test_options_step_is_not_critical() -> None:
    """OptionsResolveStep является некритичным шагом пайплайна."""
    assert OptionsResolveStep.is_critical is False
