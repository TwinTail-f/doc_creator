"""Unit tests for autodoc/parser/parser.py (ComponentParser)."""

import datetime
from pathlib import Path

import pytest

from autodoc.exceptions import ParsingError
from autodoc.models.parsed_result import ParsedResult
from autodoc.parser.parser import ComponentParser
from autodoc.parser.pipeline.context import PipelineContext
from autodoc.parser.steps.base import BaseParseStep
from autodoc.parser.steps.conan_step import ConanEnrichStep

# ---------------------------------------------------------------------------
# Fake pipeline steps
# ---------------------------------------------------------------------------


class FakeStep(BaseParseStep):
    """Fake pipeline step that records execution order and optionally raises."""

    name = "fake_step"
    is_critical = True

    def __init__(self, side_effect: Exception | None = None) -> None:
        """
        Args:
            side_effect: Exception to raise when execute() is called. None → no-op.
        """
        self._side_effect = side_effect

    def execute(self, ctx: PipelineContext) -> None:
        """Execute fake step; optionally raise a configured exception."""
        if self._side_effect:
            raise self._side_effect


class FakeFinalize(BaseParseStep):
    """Fake FinalizeStep that populates ctx.result with a minimal ParsedResult."""

    name = "fake_finalize"
    is_critical = True

    def execute(self, ctx: PipelineContext) -> None:
        """Populate ctx.result with a minimal valid ParsedResult."""
        ctx.result = ParsedResult(
            generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            platform_version=ctx.config.platform_version,
            profile_definitions=[],
            components=[],
        )


class NonCriticalStep(BaseParseStep):
    """Non-critical step that always raises ParsingError."""

    name = "non_critical"
    is_critical = False

    def execute(self, ctx: PipelineContext) -> None:
        """Always raise to simulate a non-critical failure."""
        raise ParsingError("non-critical boom")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_component_parser_parse_returns_parsed_result(
    parser_config,
    tmp_path,
) -> None:
    """Happy path: parse() returns a ParsedResult when FakeFinalize populates ctx.result."""
    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=[FakeStep(), FakeFinalize()],
    )
    result = parser.parse()
    assert isinstance(result, ParsedResult)


def test_component_parser_critical_step_failure_raises_parsing_error(
    parser_config,
    tmp_path,
) -> None:
    """A critical step failure raises ParsingError and subsequent steps are not executed."""
    finalize_executed: list[bool] = []

    class TrackingFinalize(BaseParseStep):
        name = "tracking_finalize"
        is_critical = True

        def execute(self, ctx: PipelineContext) -> None:
            finalize_executed.append(True)

    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=[FakeStep(side_effect=ParsingError("boom")), TrackingFinalize()],
    )
    with pytest.raises(ParsingError):
        parser.parse()
    assert finalize_executed == []


def test_component_parser_non_critical_step_failure_continues(
    parser_config,
    tmp_path,
) -> None:
    """A non-critical step failure is swallowed and the pipeline continues to completion."""
    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=[NonCriticalStep(), FakeFinalize()],
    )
    result = parser.parse()  # must not raise
    assert isinstance(result, ParsedResult)


def test_component_parser_cleans_up_tmp_dir_on_success(
    parser_config,
    tmp_path,
) -> None:
    """The tmp_dir is removed after a successful parse (finally block)."""
    data_dir = tmp_path / "workspace"
    data_dir.mkdir()
    tmp_dir = data_dir / "tmp"
    tmp_dir.mkdir()
    parser = ComponentParser(
        config=parser_config,
        data_dir=data_dir,
        steps=[FakeFinalize()],
    )
    parser.parse()
    assert not tmp_dir.exists()


def test_component_parser_cleans_up_tmp_dir_on_failure(
    parser_config,
    tmp_path,
) -> None:
    """The tmp_dir is removed even when a critical step raises (finally block)."""
    data_dir = tmp_path / "workspace"
    data_dir.mkdir()
    tmp_dir = data_dir / "tmp"
    tmp_dir.mkdir()
    parser = ComponentParser(
        config=parser_config,
        data_dir=data_dir,
        steps=[FakeStep(side_effect=ParsingError("boom"))],
    )
    with pytest.raises(ParsingError):
        parser.parse()
    assert not tmp_dir.exists()


def test_component_parser_raises_if_result_not_set(
    parser_config,
    tmp_path,
) -> None:
    """If no step populates ctx.result, parse() raises ParsingError after all steps complete."""
    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=[FakeStep()],
    )
    with pytest.raises(ParsingError):
        parser.parse()


def test_component_parser_with_steps_excluded_removes_step_class(
    parser_config,
    tmp_path,
) -> None:
    """with_steps_excluded factory method removes all instances of the specified step class."""
    parser = ComponentParser.with_steps_excluded(
        config=parser_config,
        data_dir=tmp_path,
        exclude=[ConanEnrichStep],
    )
    assert not any(isinstance(s, ConanEnrichStep) for s in parser._steps)


def test_component_parser_uses_injected_tfs_client(
    mocker,
    parser_config,
    tmp_path,
) -> None:
    """When a tfs_client is injected via constructor, TFSClient.__init__ is never called."""
    from autodoc.tests.unit.parser.conftest import FakeTFSClient

    mock_tfs_init = mocker.patch(
        "autodoc.parser.parser.TFSClient.__init__",
        return_value=None,
    )
    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=[FakeFinalize()],
        tfs_client=FakeTFSClient(),
    )
    parser.parse()
    mock_tfs_init.assert_not_called()


def test_component_parser_save_intermediate_writes_files(
    parser_config,
    tmp_path,
) -> None:
    """parse(save_intermediate=True) writes at least one JSON file into the intermediate dir."""
    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=[FakeFinalize()],
    )
    parser.parse(save_intermediate=True)
    intermediate_dir = tmp_path / "intermediate"
    json_files = list(intermediate_dir.glob("*.json"))
    assert len(json_files) >= 1
