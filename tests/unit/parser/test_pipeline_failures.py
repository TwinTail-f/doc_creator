"""Tests for error accumulation behaviour in the autodoc parser pipeline.

The pipeline must accumulate errors from non-critical step failures and
surface them all together, rather than stopping at the first failure.
"""

from pathlib import Path

import pytest

from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.exceptions import DocGeneratorError, ParsingError
from autodoc.parser.parser import ComponentParser
from autodoc.parser.pipeline.context import PipelineContext
from autodoc.parser.steps.base_parse_step import BaseParseStep

# Sentinel values written to ctx.intermediate to track step execution order.
_SENTINEL_SECOND_STEP: str = "second_step_ran"
_SENTINEL_AFTER_CRITICAL: str = "after_critical_ran"
_SENTINEL_VALUE: str = "yes"

# Error messages embedded in failing steps — used to assert both are reported.
_ERROR_MSG_FIRST: str = "first non-critical failure"
_ERROR_MSG_SECOND: str = "second non-critical failure"


@pytest.fixture()
def parser_config() -> ParserConfigSchema:
    """Minimal valid ParserConfigSchema for pipeline failure tests."""
    return ParserConfigSchema(
        platform_version="2.0",
        platform_branch_name="develop",
        platform_ref_type="branch",
        username="testuser",
        tfs_token="test-tfs-pat-token",
        tfs_collection_url="https://tfs.example.com",
        manifests_remotes_path="/platform/manifests",
        conan_config_url="https://art.example.com/conan-config.zip",
    )


def _make_context(config: ParserConfigSchema, tmp_path: Path) -> PipelineContext:
    """Construct a bare PipelineContext for use in failure tests."""
    return PipelineContext(config=config, tmp_dir=tmp_path)


class _FailingNonCriticalStep(BaseParseStep):
    """Test double: a non-critical step that always raises DocGeneratorError."""

    name = "_FailingNonCriticalStep"
    is_critical = False

    def __init__(self, error_message: str) -> None:
        """Args: error_message — text embedded in the raised DocGeneratorError."""
        self._error_message = error_message

    def execute(self, ctx: PipelineContext) -> None:  # type: ignore[override]
        """Raise DocGeneratorError unconditionally."""
        raise DocGeneratorError(self._error_message)


class _SentinelStep(BaseParseStep):
    """Test double: a non-critical step that writes a sentinel to ctx.intermediate."""

    name = "_SentinelStep"
    is_critical = False

    def __init__(self, key: str, value: str) -> None:
        """Args: key/value written to ctx.intermediate on execute()."""
        self._key = key
        self._value = value

    def execute(self, ctx: PipelineContext) -> None:  # type: ignore[override]
        """Write sentinel key-value pair to ctx.intermediate."""
        ctx.intermediate[self._key] = self._value


class _FailingCriticalStep(BaseParseStep):
    """Test double: a critical step that always raises DocGeneratorError."""

    name = "_FailingCriticalStep"
    is_critical = True

    def execute(self, ctx: PipelineContext) -> None:  # type: ignore[override]
        """Raise DocGeneratorError unconditionally."""
        raise DocGeneratorError("critical step failure")


class _FinalizeOnlyStep(BaseParseStep):
    """Test double: a critical step that sets ctx.result to a minimal ParsedResult."""

    name = "_FinalizeOnlyStep"
    is_critical = True

    def execute(self, ctx: PipelineContext) -> None:  # type: ignore[override]
        """Populate ctx.result so ComponentParser.parse() does not raise on missing result."""
        from autodoc.models.parsed_result import ParsedResult

        ctx.result = ParsedResult(
            generated_at="2024-01-01T00:00:00",
            platform_version="2.0",
        )


def test_two_non_critical_failures_both_reported(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """Two non-critical failing steps must both be logged; the pipeline must not stop.

    The ComponentParser logs (and does not re-raise) DocGeneratorError from
    non-critical steps, so the pipeline must complete all steps.  The test
    confirms completion by checking that a subsequent FinalizeOnlyStep still runs.
    """
    warning_messages: list[str] = []

    import logging

    class _CapturingHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            warning_messages.append(self.format(record))

    import logging as _logging

    logger = _logging.getLogger("doc_parser")
    handler = _CapturingHandler()
    logger.addHandler(handler)

    try:
        steps = [
            _FailingNonCriticalStep(_ERROR_MSG_FIRST),
            _FailingNonCriticalStep(_ERROR_MSG_SECOND),
            _FinalizeOnlyStep(),
        ]
        parser = ComponentParser(
            config=parser_config,
            data_dir=tmp_path,
            steps=steps,
        )
        result = parser.parse()
        # Pipeline completed: result is populated by FinalizeOnlyStep
        assert result is not None
    finally:
        logger.removeHandler(handler)

    # Both error messages must have been logged
    all_messages: str = "\n".join(warning_messages)
    assert (
        _ERROR_MSG_FIRST in all_messages
    ), f"Expected '{_ERROR_MSG_FIRST}' in warning log but got: {all_messages}"
    assert (
        _ERROR_MSG_SECOND in all_messages
    ), f"Expected '{_ERROR_MSG_SECOND}' in warning log but got: {all_messages}"


def test_non_critical_failure_does_not_block_next_step(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """A non-critical step failure must not prevent the next step from running.

    The sentinel step after the failing step must execute and write its value,
    proving that non-critical errors are accumulated rather than propagated.
    """
    steps = [
        _FailingNonCriticalStep(_ERROR_MSG_FIRST),
        _SentinelStep(_SENTINEL_SECOND_STEP, _SENTINEL_VALUE),
        _FinalizeOnlyStep(),
    ]
    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=steps,
    )
    result = parser.parse()
    # FinalizeOnlyStep only sets ctx.result but does not expose ctx.intermediate.
    # The easiest way to verify the sentinel step ran is to run a custom finalize
    # that captures intermediate. We test this via a patched FinalizeOnlyStep.
    # Instead, run a variant where the sentinel step IS the last step and also
    # serves as finalize:

    class _SentinelAndFinalizeStep(_FinalizeOnlyStep):
        """Sets sentinel AND ctx.result."""

        name = "_SentinelAndFinalizeStep"

        def execute(self, ctx: PipelineContext) -> None:  # type: ignore[override]
            ctx.intermediate[_SENTINEL_SECOND_STEP] = _SENTINEL_VALUE
            super().execute(ctx)

    steps2 = [
        _FailingNonCriticalStep(_ERROR_MSG_FIRST),
        _SentinelAndFinalizeStep(),
    ]
    parser2 = ComponentParser(
        config=parser_config,
        data_dir=tmp_path / "run2",
        steps=steps2,
    )
    # Capture the ctx after execution by inspecting parse() result.
    # We can't directly inspect ctx, so we piggyback on a custom FinalizeStep.
    # Instead, we track via a shared list (closure):
    executed_steps: list[str] = []

    class _TrackingFail(_FailingNonCriticalStep):
        """Records that this step was attempted before failing."""

        name = "_TrackingFail"

        def execute(self, ctx: PipelineContext) -> None:  # type: ignore[override]
            executed_steps.append("fail")
            super().execute(ctx)

    class _TrackingFinalize(_FinalizeOnlyStep):
        """Records that this step executed."""

        name = "_TrackingFinalize"

        def execute(self, ctx: PipelineContext) -> None:  # type: ignore[override]
            executed_steps.append("finalize")
            super().execute(ctx)

    steps3 = [
        _TrackingFail(_ERROR_MSG_FIRST),
        _TrackingFinalize(),
    ]
    parser3 = ComponentParser(
        config=parser_config,
        data_dir=tmp_path / "run3",
        steps=steps3,
    )
    parser3.parse()

    assert "fail" in executed_steps, "Failing step was never attempted"
    assert (
        "finalize" in executed_steps
    ), "Step after failing non-critical step was not executed"


def test_critical_failure_stops_pipeline(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """A critical step failure must stop the pipeline immediately.

    The sentinel step registered after a critical failing step must NOT execute.
    The pipeline must raise ParsingError.
    """
    executed_after: list[str] = []

    class _TrackingStep(BaseParseStep):
        """Records execution and writes sentinel — must NOT run after critical failure."""

        name = "_TrackingStep"
        is_critical = False

        def execute(self, ctx: PipelineContext) -> None:  # type: ignore[override]
            executed_after.append("ran")

    steps = [
        _FailingCriticalStep(),
        _TrackingStep(),
    ]
    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=steps,
    )
    with pytest.raises(ParsingError):
        parser.parse()

    assert (
        len(executed_after) == 0
    ), "Step after critical failure must not execute, but it ran"
