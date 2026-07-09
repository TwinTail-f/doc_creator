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
    """Сбой некритичного шага не должен предотвратить запуск следующего шага."""
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

    steps = [
        _TrackingFail(_ERROR_MSG_FIRST),
        _TrackingFinalize(),
    ]
    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=steps,
    )
    parser.parse()

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



