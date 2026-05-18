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


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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


# ===========================================================================
# BL-PP-01 … BL-PP-10  — Pipeline Orchestration Rules (Part 4)
# ===========================================================================

# ---------------------------------------------------------------------------
# Shared step helpers for BL-PP tests
# ---------------------------------------------------------------------------


class _FakeManifestStep(BaseParseStep):
    """Sets ctx.components with one minimal component for BL-PP tests.

    Simulates the ManifestStep so that subsequent steps that expect
    ctx.components to be populated can function without real TFS I/O.
    """

    name = "fake_manifest_step"
    is_critical = True

    def execute(self, ctx: PipelineContext) -> None:
        """Populate ctx.components with a single minimal Component."""
        from autodoc.models.component import Component
        from autodoc.models.conan_variant import ProfileBuild
        from autodoc.models.release import Release

        pb = ProfileBuild(profile_name="hw-linux-x86_64")
        release = Release(
            version="1.0",
            platform="2.0",
            channel="fast",
            conan_reference="",
            artifactory_url="",
            profile_builds=[pb],
        )
        comp = Component(
            name="mylib",
            description="",
            git_project="P",
            git_repo="r",
            git_url="",
            is_header_only=False,
            releases=[release],
        )
        ctx.components = [comp]


# ---------------------------------------------------------------------------
# BL-PP-01 — critical ManifestStep failure stops pipeline, result is None
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_manifest_step_failure_stops_pipeline_no_result(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """BL-PP-01: Error in a critical ManifestStep stops the pipeline immediately.

    Business Rule:
        A DocGeneratorError raised by a critical step (ManifestStep) must
        propagate as ``ParsingError`` and halt execution of all subsequent
        steps.  ``ctx.result`` must remain ``None`` because ``FinalizeStep``
        was never reached.

    Preconditions:
        - Pipeline: [_FailManifest (critical), _ShouldNotRun (non-critical),
          _FakeFinalizeStep (critical)].

    Steps:
        1. Call ``parser.parse()``.

    Expected Result:
        - ``ParsingError`` is raised.
        - ``_ShouldNotRun.ran`` is ``False`` (step was never executed).
    """

    class _FailManifest(BaseParseStep):
        name = "manifest_step_bl_pp_01"
        is_critical = True

        def execute(self, ctx: PipelineContext) -> None:
            raise DocGeneratorError("TFS unavailable")

    class _ShouldNotRun(BaseParseStep):
        name = "should_not_run_bl_pp_01"
        is_critical = False
        ran = False

        def execute(self, ctx: PipelineContext) -> None:
            _ShouldNotRun.ran = True

    _ShouldNotRun.ran = False  # reset class-level sentinel

    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=[_FailManifest(), _ShouldNotRun(), _FinalizeOnlyStep()],
    )

    with pytest.raises(ParsingError):
        parser.parse()

    assert _ShouldNotRun.ran is False, "Step after critical failure must not execute"


# ---------------------------------------------------------------------------
# BL-PP-02 — critical FinalizeStep failure raises ParsingError
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_finalize_step_failure_stops_pipeline(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """BL-PP-02: Error in a critical FinalizeStep raises ParsingError.

    Business Rule:
        A DocGeneratorError raised by the FinalizeStep (critical) must
        propagate as ``ParsingError``.  Neither ``ctx.result`` nor any output
        file must be created; the pipeline stops immediately.

    Preconditions:
        - Pipeline: [_FakeManifestStep (critical), _FailFinalize (critical)].

    Steps:
        1. Call ``parser.parse()``.

    Expected Result:
        - ``ParsingError`` is raised.
    """

    class _FailFinalize(BaseParseStep):
        name = "finalize_step_bl_pp_02"
        is_critical = True

        def execute(self, ctx: PipelineContext) -> None:
            raise DocGeneratorError("Validation failed")

    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=[_FakeManifestStep(), _FailFinalize()],
    )

    with pytest.raises(ParsingError):
        parser.parse()


# ---------------------------------------------------------------------------
# BL-PP-03 — non-critical ConanEnrichStep failure does not stop pipeline
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_conan_step_failure_pipeline_continues(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """BL-PP-03: Error in a non-critical ConanEnrichStep does not halt pipeline.

    Business Rule:
        A DocGeneratorError raised by a non-critical step (e.g. ConanEnrichStep)
        must be logged and swallowed; subsequent steps must still execute and
        the pipeline must return a valid ``ParsedResult``.

    Preconditions:
        - Pipeline: [_FakeManifestStep, _FailConan (non-critical),
          _AfterConan (non-critical), _FinalizeOnlyStep].

    Steps:
        1. Call ``parser.parse()``.

    Expected Result:
        - No exception is raised.
        - ``_AfterConan.ran`` is ``True``.
        - Return value is not ``None``.
    """

    class _FailConan(BaseParseStep):
        name = "conan_enrich_step_bl_pp_03"
        is_critical = False

        def execute(self, ctx: PipelineContext) -> None:
            raise DocGeneratorError("Conan unavailable")

    class _AfterConan(BaseParseStep):
        name = "after_conan_step_bl_pp_03"
        is_critical = False
        ran = False

        def execute(self, ctx: PipelineContext) -> None:
            _AfterConan.ran = True

    _AfterConan.ran = False

    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=[_FakeManifestStep(), _FailConan(), _AfterConan(), _FinalizeOnlyStep()],
    )

    result = parser.parse()

    assert _AfterConan.ran is True, "Step after non-critical failure must execute"
    assert result is not None, "Pipeline must complete with a valid result"


# ---------------------------------------------------------------------------
# BL-PP-04 — non-critical DockerResolveStep failure does not halt pipeline
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_docker_step_failure_pipeline_continues(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """BL-PP-04: Error in a non-critical DockerResolveStep does not halt pipeline.

    Business Rule:
        ``DockerResolveStep`` is non-critical; a failure there must not
        interrupt subsequent steps.

    Preconditions:
        - Pipeline: [_FakeManifestStep, _FailDocker (non-critical),
          _AfterDocker (non-critical), _FinalizeOnlyStep].

    Steps:
        1. Call ``parser.parse()``.

    Expected Result:
        - ``_AfterDocker.ran`` is ``True``.
    """

    class _FailDocker(BaseParseStep):
        name = "docker_resolve_step_bl_pp_04"
        is_critical = False

        def execute(self, ctx: PipelineContext) -> None:
            raise DocGeneratorError("Docker config unavailable")

    class _AfterDocker(BaseParseStep):
        name = "after_docker_bl_pp_04"
        is_critical = False
        ran = False

        def execute(self, ctx: PipelineContext) -> None:
            _AfterDocker.ran = True

    _AfterDocker.ran = False

    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=[_FakeManifestStep(), _FailDocker(), _AfterDocker(), _FinalizeOnlyStep()],
    )

    parser.parse()
    assert _AfterDocker.ran is True


# ---------------------------------------------------------------------------
# BL-PP-05 — non-critical OptionsResolveStep failure does not halt pipeline
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_options_step_failure_pipeline_continues(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """BL-PP-05: Error in a non-critical OptionsResolveStep does not halt pipeline.

    Business Rule:
        ``OptionsResolveStep`` is non-critical; its failure must be swallowed
        and steps registered after it must still execute.

    Preconditions:
        - Pipeline: [_FakeManifestStep, _FailOptions (non-critical),
          _AfterOptions (non-critical), _FinalizeOnlyStep].

    Steps:
        1. Call ``parser.parse()``.

    Expected Result:
        - ``_AfterOptions.ran`` is ``True``.
    """

    class _FailOptions(BaseParseStep):
        name = "options_resolve_step_bl_pp_05"
        is_critical = False

        def execute(self, ctx: PipelineContext) -> None:
            raise DocGeneratorError("TFS options unavailable")

    class _AfterOptions(BaseParseStep):
        name = "after_options_bl_pp_05"
        is_critical = False
        ran = False

        def execute(self, ctx: PipelineContext) -> None:
            _AfterOptions.ran = True

    _AfterOptions.ran = False

    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=[
            _FakeManifestStep(),
            _FailOptions(),
            _AfterOptions(),
            _FinalizeOnlyStep(),
        ],
    )

    parser.parse()
    assert _AfterOptions.ran is True


# ---------------------------------------------------------------------------
# BL-PP-06 — non-critical ArtifactoryValidationStep failure does not halt pipeline
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_validation_step_failure_pipeline_continues(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """BL-PP-06: Error in a non-critical ArtifactoryValidationStep does not halt pipeline.

    Business Rule:
        ``ArtifactoryValidationStep`` is non-critical; failures (e.g. because
        Artifactory is unreachable) must not interrupt subsequent steps.

    Preconditions:
        - Pipeline: [_FakeManifestStep, _FailValidation (non-critical),
          _AfterValidation (non-critical), _FinalizeOnlyStep].

    Steps:
        1. Call ``parser.parse()``.

    Expected Result:
        - ``_AfterValidation.ran`` is ``True``.
    """

    class _FailValidation(BaseParseStep):
        name = "artifactory_validation_step_bl_pp_06"
        is_critical = False

        def execute(self, ctx: PipelineContext) -> None:
            raise DocGeneratorError("Artifactory unavailable")

    class _AfterValidation(BaseParseStep):
        name = "after_validation_bl_pp_06"
        is_critical = False
        ran = False

        def execute(self, ctx: PipelineContext) -> None:
            _AfterValidation.ran = True

    _AfterValidation.ran = False

    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=[
            _FakeManifestStep(),
            _FailValidation(),
            _AfterValidation(),
            _FinalizeOnlyStep(),
        ],
    )

    parser.parse()
    assert _AfterValidation.ran is True


# ---------------------------------------------------------------------------
# BL-PP-07 — ctx.components is empty before any step populates it
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_context_components_empty_before_manifest_step(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """BL-PP-07: ctx.components is empty at the very start of the pipeline.

    Business Rule:
        The initial ``PipelineContext`` must start with an empty component
        list.  Only the ManifestStep (or its substitute) may add to it.
        This guards against leftover state from a previous run.

    Preconditions:
        - Pipeline: [_ObservingStep (critical), _FinalizeOnlyStep].
        - ``_ObservingStep`` reads ``len(ctx.components)`` before writing anything.

    Steps:
        1. Call ``parser.parse()``.

    Expected Result:
        - The first observed ``len(ctx.components)`` is ``0``.
    """
    observed_counts: list[int] = []

    class _ObservingStep(BaseParseStep):
        name = "observing_step_bl_pp_07"
        is_critical = True

        def execute(self, ctx: PipelineContext) -> None:
            observed_counts.append(len(ctx.components))

    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=[_ObservingStep(), _FinalizeOnlyStep()],
    )
    parser.parse()

    assert len(observed_counts) > 0, "_ObservingStep must have executed"
    assert observed_counts[0] == 0, (
        f"ctx.components should be empty before any step populates it, "
        f"got {observed_counts[0]}"
    )


# ---------------------------------------------------------------------------
# BL-PP-08 — ctx.result is None before FinalizeStep executes
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_context_result_none_before_finalize_step(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """BL-PP-08: ctx.result is None before FinalizeStep runs.

    Business Rule:
        Only FinalizeStep is responsible for setting ``ctx.result``.  All
        steps that execute before it must observe ``ctx.result is None``.

    Preconditions:
        - Pipeline: [_FakeManifestStep, _CheckResultStep (non-critical),
          _FinalizeOnlyStep].

    Steps:
        1. Call ``parser.parse()``.

    Expected Result:
        - The value of ``ctx.result`` captured inside ``_CheckResultStep`` is ``None``.
    """
    observed_results: list = []

    class _CheckResultStep(BaseParseStep):
        name = "check_result_step_bl_pp_08"
        is_critical = False

        def execute(self, ctx: PipelineContext) -> None:
            observed_results.append(ctx.result)

    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=[_FakeManifestStep(), _CheckResultStep(), _FinalizeOnlyStep()],
    )
    parser.parse()

    assert len(observed_results) > 0, "_CheckResultStep must have executed"
    assert (
        observed_results[0] is None
    ), f"ctx.result should be None before FinalizeStep, got {observed_results[0]}"


# ---------------------------------------------------------------------------
# BL-PP-09 — with_steps_excluded removes by class, not by name similarity
# ---------------------------------------------------------------------------


@pytest.mark.infrastructure
def test_with_steps_excluded_removes_class_not_instance(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """BL-PP-09: with_steps_excluded removes steps by class type, not by name string.

    Business Rule:
        ``ComponentParser.with_steps_excluded(config, data_dir, [ConanEnrichStep])``
        filters steps using ``isinstance`` checks.  A different class that
        happens to have a similar name is NOT removed.

    Preconditions:
        - Create a parser with the default pipeline
          via ``ComponentParser.with_steps_excluded(..., [ConanEnrichStep])``.

    Steps:
        1. Inspect the ``_steps`` attribute of the filtered parser.

    Expected Result:
        - No instance of ``ConanEnrichStep`` is present in ``_steps``.
        - The total number of steps is one fewer than the default pipeline.
    """
    from autodoc.parser.steps.conan_step import ConanEnrichStep

    default_parser = ComponentParser(config=parser_config, data_dir=tmp_path)
    default_count = len(default_parser._steps)

    filtered_parser = ComponentParser.with_steps_excluded(
        config=parser_config,
        data_dir=tmp_path,
        exclude=[ConanEnrichStep],
    )

    step_classes = [type(s) for s in filtered_parser._steps]
    assert (
        ConanEnrichStep not in step_classes
    ), "ConanEnrichStep must be excluded from the filtered pipeline"
    assert len(filtered_parser._steps) == default_count - 1, (
        f"Filtered pipeline should have {default_count - 1} steps, "
        f"got {len(filtered_parser._steps)}"
    )


# ---------------------------------------------------------------------------
# BL-PP-10 — tmp_dir is cleaned up in finally block even on ParsingError
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_tmp_dir_cleaned_up_in_finally_block_on_error(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """BL-PP-10: Temporary directory is deleted even when ParsingError is raised.

    Business Rule:
        ``ComponentParser.parse()`` wraps execution in a ``try/finally`` block
        that removes ``tmp_dir`` via ``shutil.rmtree``.  The cleanup must
        happen regardless of whether a critical step raised a ``ParsingError``.
        No temporary files must leak to disk after the pipeline terminates.

    Preconditions:
        - Pipeline: [_CriticalFail (critical)].
        - ``_CriticalFail.execute`` captures ``ctx.tmp_dir`` before raising.

    Steps:
        1. Call ``parser.parse()`` inside ``pytest.raises(ParsingError)``.
        2. Check that the captured ``tmp_dir`` path no longer exists on disk.

    Expected Result:
        - ``ParsingError`` is raised.
        - The path that was ``ctx.tmp_dir`` does NOT exist after the call.
    """
    captured_tmp_dir: list[Path] = []

    class _CriticalFail(BaseParseStep):
        name = "manifest_step_bl_pp_10"
        is_critical = True

        def execute(self, ctx: PipelineContext) -> None:
            captured_tmp_dir.append(ctx.tmp_dir)
            raise DocGeneratorError("Critical failure")

    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=[_CriticalFail()],
    )

    with pytest.raises(ParsingError):
        parser.parse()

    assert len(captured_tmp_dir) == 1, "_CriticalFail must have executed"
    tmp_dir_path = captured_tmp_dir[0]
    assert (
        not tmp_dir_path.exists()
    ), f"tmp_dir {tmp_dir_path} must be deleted after ParsingError (finally block)"
