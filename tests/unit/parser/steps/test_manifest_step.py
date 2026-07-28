"""Юнит-тесты для autodoc/parser/steps/manifest_step.py."""

import pytest

from autodoc.exceptions import ParsingError
from autodoc.parser.fetchers.manifest_fetcher import ManifestFetcher
from autodoc.parser.steps.manifest_step import ManifestStep
from tests.unit.parser.conftest import FakeTFSClient


@pytest.mark.business_logic
def test_manifest_step_populates_ctx_components(
    parser_pipeline_context,
    manifest_component,
    make_fake_fetcher,
) -> None:
    """ctx.components заполняется результатом fetcher."""
    fake = make_fake_fetcher(value=[manifest_component])
    step = ManifestStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert parser_pipeline_context.components == [manifest_component]


@pytest.mark.parametrize(
    "warnings",
    [[], ["something failed"]],
    ids=["no-warnings", "with-warning"],
)
@pytest.mark.business_logic
def test_manifest_step_empty_result_does_not_raise(
    parser_pipeline_context,
    make_fake_fetcher,
    warnings: list[str],
) -> None:
    """ManifestStep не бросает исключение, когда fetcher вернул ноль компонентов, с предупреждениями или без."""
    fake = make_fake_fetcher(value=[], warnings=warnings)
    step = ManifestStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert parser_pipeline_context.components == []


@pytest.mark.contract
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


@pytest.mark.contract
def test_manifest_step_default_fetcher_is_manifest_fetcher() -> None:
    """При отсутствии аргумента fetcher ManifestStep создаёт реальный ManifestFetcher."""
    step = ManifestStep()
    assert isinstance(step._fetcher, ManifestFetcher)


@pytest.mark.integration
def test_manifest_step_propagates_parsing_error_from_fetcher(
    parser_pipeline_context,
) -> None:
    """Реальный ParsingError из ManifestFetcher пробрасывается наружу необработанным."""
    parser_pipeline_context.tfs_client = FakeTFSClient()
    step = ManifestStep()

    with pytest.raises(ParsingError):
        step.execute(parser_pipeline_context)
