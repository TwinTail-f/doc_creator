"""Тесты для поведения накопления ошибок в пайплайне парсера autodoc.

Пайплайн должен накапливать ошибки от сбоев некритичных шагов и
выводить их все вместе, а не останавливаться на первом сбое.
"""

from pathlib import Path

import pytest

from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.exceptions import DocGeneratorError, ParsingError
from autodoc.parser.parser import ComponentParser
from autodoc.parser.pipeline.context import PipelineContext
from autodoc.parser.steps.base_parse_step import BaseParseStep

# Значения-дозоры, записываемые в ctx.intermediate для отслеживания порядка выполнения шагов.
_SENTINEL_SECOND_STEP: str = "second_step_ran"
_SENTINEL_AFTER_CRITICAL: str = "after_critical_ran"
_SENTINEL_VALUE: str = "yes"

# Сообщения об ошибках, встроенные в отказывающие шаги — используются для утверждения, что оба сообщаются.
_ERROR_MSG_FIRST: str = "first non-critical failure"
_ERROR_MSG_SECOND: str = "second non-critical failure"


@pytest.fixture()
def parser_config() -> ParserConfigSchema:
    """Минимально допустимая ParserConfigSchema для тестов сбоев пайплайна."""
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
    """Построить пустой PipelineContext для использования в тестах сбоев."""
    return PipelineContext(config=config, tmp_dir=tmp_path)


class _FailingNonCriticalStep(BaseParseStep):
    """Тестовый двойник: некритичный шаг, который всегда вызывает DocGeneratorError."""

    name = "_FailingNonCriticalStep"
    is_critical = False

    def __init__(self, error_message: str) -> None:
        """Args: error_message — текст, встроенный в вызываемый DocGeneratorError."""
        self._error_message = error_message

    def execute(self, ctx: PipelineContext) -> None:  # type: ignore[override]
        """Raise DocGeneratorError unconditionally."""
        raise DocGeneratorError(self._error_message)


class _SentinelStep(BaseParseStep):
    """Тестовый двойник: некритичный шаг, который записывает дозор в ctx.intermediate."""

    name = "_SentinelStep"
    is_critical = False

    def __init__(self, key: str, value: str) -> None:
        """Args: key/value записанные в ctx.intermediate при execute()."""
        self._key = key
        self._value = value

    def execute(self, ctx: PipelineContext) -> None:  # type: ignore[override]
        """Написать пару ключ-значение дозора в ctx.intermediate."""
        ctx.intermediate[self._key] = self._value


class _FailingCriticalStep(BaseParseStep):
    """Тестовый двойник: критичный шаг, который всегда вызывает DocGeneratorError."""

    name = "_FailingCriticalStep"
    is_critical = True

    def execute(self, ctx: PipelineContext) -> None:  # type: ignore[override]
        """Вызвать DocGeneratorError без условий."""
        raise DocGeneratorError("critical step failure")


class _FinalizeOnlyStep(BaseParseStep):
    """Тестовый двойник: критичный шаг, который устанавливает ctx.result на минимальный ParsedResult."""

    name = "_FinalizeOnlyStep"
    is_critical = True

    def execute(self, ctx: PipelineContext) -> None:  # type: ignore[override]
        """Заполнить ctx.result, чтобы ComponentParser.parse() не вызывал исключение на отсутствие результата."""
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
    """Два некритичных отказывающих шага должны быть залогированы; пайплайн не должен остановиться.

    ComponentParser логирует (и не пробрасывает заново) DocGeneratorError из
    некритичных шагов, поэтому пайплайн должен выполнить все шаги.  Тест
    подтверждает завершение, проверяя, что последующий FinalizeOnlyStep всё ещё работает.
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
        # Пайплайн завершен: result заполнен FinalizeOnlyStep
        assert result is not None
    finally:
        logger.removeHandler(handler)

    # Оба сообщения об ошибке должны быть залогированы
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
    """Сбой некритичного шага не должен предотвратить запуск следующего шага.

    Дозорный шаг после отказывающего шага должен выполниться и записать своё значение,
    доказывая, что некритичные ошибки накапливаются, а не распространяются.
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
    # FinalizeOnlyStep только устанавливает ctx.result, но не выражает ctx.intermediate.
    # Самый простой способ убедиться, что дозорный шаг работал — это запустить пользовательскую финализацию
    # которая захватывает промежуточные результаты. Мы тестируем это через залатанный FinalizeOnlyStep.
    # Вместо этого запустите вариант, где дозорный шаг ЯВЛЯЕТСЯ последним шагом и также
    # служит финализацией:

    class _SentinelAndFinalizeStep(_FinalizeOnlyStep):
        """Устанавливает дозор И ctx.result."""

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
    # Захватить ctx после выполнения путём проверки результата parse().
    # Мы не можем прямо проверить ctx, поэтому мы полагаемся на пользовательский FinalizeStep.
    # Вместо этого отслеживаем через общий список (closure):
    executed_steps: list[str] = []

    class _TrackingFail(_FailingNonCriticalStep):
        """Записывает, что этот шаг был попытан перед отказом."""

        name = "_TrackingFail"

        def execute(self, ctx: PipelineContext) -> None:  # type: ignore[override]
            executed_steps.append("fail")
            super().execute(ctx)

    class _TrackingFinalize(_FinalizeOnlyStep):
        """Записывает, что этот шаг был выполнен."""

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

    assert "fail" in executed_steps, "Отказавший шаг никогда не был попытан"
    assert "finalize" in executed_steps, "Шаг после некритичного отказа не был выполнен"


@pytest.mark.business_logic
def test_critical_failure_stops_pipeline(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """Сбой критичного шага должен остановить пайплайн немедленно.

    Дозорный шаг, зарегистрированный после отказывающего критичного шага, НЕ ДОЛЖЕН выполниться.
    Пайплайн должен вызвать ParsingError.
    """
    executed_after: list[str] = []

    class _TrackingStep(BaseParseStep):
        """Записывает выполнение и записывает дозор — НЕ ДОЛЖЕН работать после критичного сбоя."""

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
    ), "Шаг после критичного сбоя не должен выполниться, но он работал"


# ===========================================================================
# BL-PP-01 … BL-PP-10  — Правила оркестрации пайплайна (часть 4)
# ===========================================================================

# ---------------------------------------------------------------------------
# Общие помощники шагов для BL-PP тестов
# ---------------------------------------------------------------------------


class _FakeManifestStep(BaseParseStep):
    """Устанавливает ctx.components с одним минимальным компонентом для BL-PP тестов.

    Имитирует ManifestStep, чтобы последующие шаги, которые ожидают
    ctx.components быть заполненным, могли функционировать без реального TFS ввода-вывода.
    """

    name = "fake_manifest_step"
    is_critical = True

    def execute(self, ctx: PipelineContext) -> None:
        """Заполнить ctx.components одним минимальным компонентом."""
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
    """BL-PP-01: Ошибка в критичном ManifestStep останавливает пайплайн немедленно.

    Бизнес-правило:
        DocGeneratorError, вызванный критичным шагом (ManifestStep), должен
        распространяться как ``ParsingError`` и остановить выполнение всех последующих
        шагов.  ``ctx.result`` должен оставаться ``None``, потому что ``FinalizeStep``
        никогда не был достигнут.

    Предусловия:
        - Пайплайн: [_FailManifest (критичный), _ShouldNotRun (некритичный),
          _FakeFinalizeStep (критичный)].

    Шаги:
        1. Вызвать ``parser.parse()``.

    Ожидаемый результат:
        - ``ParsingError`` вызывается.
        - ``_ShouldNotRun.ran`` равен ``False`` (шаг никогда не был выполнен).
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

    assert _ShouldNotRun.ran is False, "Шаг после критичного сбоя не должен выполниться"


# ---------------------------------------------------------------------------
# BL-PP-02 — критичный FinalizeStep сбой вызывает ParsingError
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_finalize_step_failure_stops_pipeline(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """BL-PP-02: Ошибка в критичном FinalizeStep вызывает ParsingError.

    Бизнес-правило:
        DocGeneratorError, вызванный FinalizeStep (критичный), должен
        распространяться как ``ParsingError``. Ни ``ctx.result``, ни какой-либо
        выходной файл не должны быть созданы; пайплайн останавливается немедленно.

    Предусловия:
        - Пайплайн: [_FakeManifestStep (критичный), _FailFinalize (критичный)].

    Шаги:
        1. Вызвать ``parser.parse()``.

    Ожидаемый результат:
        - ``ParsingError`` вызывается.
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
# BL-PP-03 — некритичный ConanEnrichStep сбой не останавливает пайплайн
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_conan_step_failure_pipeline_continues(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """BL-PP-03: Ошибка в некритичном ConanEnrichStep не останавливает пайплайн.

    Бизнес-правило:
        DocGeneratorError, вызванный некритичным шагом (например ConanEnrichStep),
        должен быть залогирован и проглочен; последующие шаги должны всё ещё выполняться и
        пайплайн должен вернуть корректный ``ParsedResult``.

    Предусловия:
        - Пайплайн: [_FakeManifestStep, _FailConan (некритичный),
          _AfterConan (некритичный), _FinalizeOnlyStep].

    Шаги:
        1. Вызвать ``parser.parse()``.

    Ожидаемый результат:
        - Исключение не вызывается.
        - ``_AfterConan.ran`` равен ``True``.
        - Возвращаемое значение не ``None``.
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

    assert _AfterConan.ran is True, "Шаг после некритичного сбоя должен выполниться"
    assert result is not None, "Пайплайн должен завершиться с корректным результатом"


# ---------------------------------------------------------------------------
# BL-PP-04 — некритичный DockerResolveStep сбой не останавливает пайплайн
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_docker_step_failure_pipeline_continues(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """BL-PP-04: Ошибка в некритичном DockerResolveStep не останавливает пайплайн.

    Бизнес-правило:
        ``DockerResolveStep`` некритичен; сбой там не должен прерывать
        последующие шаги.

    Предусловия:
        - Пайплайн: [_FakeManifestStep, _FailDocker (некритичный),
          _AfterDocker (некритичный), _FinalizeOnlyStep].

    Шаги:
        1. Вызвать ``parser.parse()``.

    Ожидаемый результат:
        - ``_AfterDocker.ran`` равен ``True``.
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
# BL-PP-05 — некритичный OptionsResolveStep сбой не останавливает пайплайн
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_options_step_failure_pipeline_continues(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """BL-PP-05: Ошибка в некритичном OptionsResolveStep не останавливает пайплайн.

    Бизнес-правило:
        ``OptionsResolveStep`` некритичен; его сбой должен быть проглочен
        и шаги, зарегистрированные после него, должны всё ещё выполняться.

    Предусловия:
        - Пайплайн: [_FakeManifestStep, _FailOptions (некритичный),
          _AfterOptions (некритичный), _FinalizeOnlyStep].

    Шаги:
        1. Вызвать ``parser.parse()``.

    Ожидаемый результат:
        - ``_AfterOptions.ran`` равен ``True``.
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
# BL-PP-06 — некритичный ArtifactoryValidationStep сбой не останавливает пайплайн
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_validation_step_failure_pipeline_continues(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """BL-PP-06: Ошибка в некритичном ArtifactoryValidationStep не останавливает пайплайн.

    Бизнес-правило:
        ``ArtifactoryValidationStep`` некритичен; сбои (например, потому что
        Artifactory недостижим) не должны прерывать последующие шаги.

    Предусловия:
        - Пайплайн: [_FakeManifestStep, _FailValidation (некритичный),
          _AfterValidation (некритичный), _FinalizeOnlyStep].

    Шаги:
        1. Вызвать ``parser.parse()``.

    Ожидаемый результат:
        - ``_AfterValidation.ran`` равен ``True``.
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
    """BL-PP-07: ctx.components пусто в самом начале пайплайна.

    Бизнес-правило:
        Начальный ``PipelineContext`` должен начинаться с пустого списка компонентов.
        Только ManifestStep (или его заменитель) может добавлять к нему.
        Это защищает от остаточного состояния из предыдущего запуска.

    Предусловия:
        - Пайплайн: [_ObservingStep (критичный), _FinalizeOnlyStep].
        - ``_ObservingStep`` читает ``len(ctx.components)`` перед написанием чего-либо.

    Шаги:
        1. Вызвать ``parser.parse()``.

    Ожидаемый результат:
        - Первое наблюдаемое ``len(ctx.components)`` равно ``0``.
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

    assert len(observed_counts) > 0, "_ObservingStep должен был быть выполнен"
    assert observed_counts[0] == 0, (
        f"ctx.components должен быть пуст перед тем, как какой-либо шаг заполнит его, "
        f"получили {observed_counts[0]}"
    )


# ---------------------------------------------------------------------------
# BL-PP-08 — ctx.result равен None перед выполнением FinalizeStep
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_context_result_none_before_finalize_step(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """BL-PP-08: ctx.result равен None перед запуском FinalizeStep.

    Бизнес-правило:
        Только FinalizeStep отвечает за установку ``ctx.result``.  Все
        шаги, которые выполняются перед ним, должны наблюдать ``ctx.result is None``.

    Предусловия:
        - Пайплайн: [_FakeManifestStep, _CheckResultStep (некритичный),
          _FinalizeOnlyStep].

    Шаги:
        1. Вызвать ``parser.parse()``.

    Ожидаемый результат:
        - Значение ``ctx.result``, захваченное внутри ``_CheckResultStep``, равно ``None``.
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

    assert len(observed_results) > 0, "_CheckResultStep должен был быть выполнен"
    assert (
        observed_results[0] is None
    ), f"ctx.result должен быть None перед FinalizeStep, получено {observed_results[0]}"


# ---------------------------------------------------------------------------
# BL-PP-09 — with_steps_excluded удаляет по классу, не по сходству имён
# ---------------------------------------------------------------------------


@pytest.mark.infrastructure
def test_with_steps_excluded_removes_class_not_instance(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """BL-PP-09: with_steps_excluded удаляет шаги по типу класса, не по строке имени.

    Бизнес-правило:
        ``ComponentParser.with_steps_excluded(config, data_dir, [ConanEnrichStep])``
        фильтрует шаги, используя проверки ``isinstance``.  Другой класс, который
        случайно имеет похожее имя, НЕ удаляется.

    Предусловия:
        - Создать парсер с пайплайном по умолчанию
          через ``ComponentParser.with_steps_excluded(..., [ConanEnrichStep])``.

    Шаги:
        1. Проверить атрибут ``_steps`` отфильтрованного парсера.

    Ожидаемый результат:
        - Нет экземпляра ``ConanEnrichStep`` в ``_steps``.
        - Общее количество шагов на один меньше, чем пайплайн по умолчанию.
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
    ), "ConanEnrichStep должен быть исключён из отфильтрованного пайплайна"
    assert len(filtered_parser._steps) == default_count - 1, (
        f"Отфильтрованный пайплайн должен иметь {default_count - 1} шагов, "
        f"получили {len(filtered_parser._steps)}"
    )


# ---------------------------------------------------------------------------
# BL-PP-10 — tmp_dir очищается в finally блоке даже при ParsingError
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_tmp_dir_cleaned_up_in_finally_block_on_error(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """BL-PP-10: Временная директория удаляется даже когда вызывается ParsingError.

    Бизнес-правило:
        ``ComponentParser.parse()`` обёртывает выполнение в ``try/finally`` блок,
        который удаляет ``tmp_dir`` через ``shutil.rmtree``.  Очистка должна
        произойти независимо от того, вызвал ли критичный шаг ``ParsingError``.
        Никакие временные файлы не должны протечь на диск после завершения пайплайна.

    Предусловия:
        - Пайплайн: [_CriticalFail (критичный)].
        - ``_CriticalFail.execute`` захватывает ``ctx.tmp_dir`` перед вызовом исключения.

    Шаги:
        1. Вызвать ``parser.parse()`` внутри ``pytest.raises(ParsingError)``.
        2. Проверить, что захваченный путь ``tmp_dir`` больше не существует на диске.

    Ожидаемый результат:
        - ``ParsingError`` вызывается.
        - Путь, который был ``ctx.tmp_dir``, НЕ существует после вызова.
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

    assert len(captured_tmp_dir) == 1, "_CriticalFail должен был быть выполнен"
    tmp_dir_path = captured_tmp_dir[0]
    assert (
        not tmp_dir_path.exists()
    ), f"tmp_dir {tmp_dir_path} должен быть удален после ParsingError (finally блок)"
