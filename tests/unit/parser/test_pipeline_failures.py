"""
Тесты для поведения накопления ошибок в пайплайне парсера autodoc.

Пайплайн должен накапливать ошибки от сбоев некритичных шагов и
выводить их все вместе, а не останавливаться на первом сбое.
"""

import logging
from pathlib import Path

import pytest

from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.exceptions import DocGeneratorError, ParsingError
from autodoc.models.parsed_result import ParsedResult
from autodoc.parser.parser import ComponentParser
from autodoc.parser.steps.conan_step import ConanEnrichStep
from tests.unit.parser.conftest import CallbackStep, FailingStep, FakeManifestStep, FinalizeOnlyStep

# Тексты ошибок, с которыми падают шаги-заглушки — по ним проверяем, что в лог попали оба сообщения.
_ERROR_MSG_FIRST: str = "first non-critical failure"
_ERROR_MSG_SECOND: str = "second non-critical failure"


@pytest.mark.business_logic
def test_two_non_critical_failures_both_reported(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Ошибки двух падающих некритичных шагов должны попасть в лог; пайплайн не должен остановиться.

    ComponentParser логирует (и не пробрасывает заново) DocGeneratorError из
    некритичных шагов, поэтому пайплайн должен выполнить все шаги.  Тест
    подтверждает завершение, проверяя, что последующий FinalizeOnlyStep всё ещё работает.
    """
    steps = [
        FailingStep(DocGeneratorError(_ERROR_MSG_FIRST)),
        FailingStep(DocGeneratorError(_ERROR_MSG_SECOND)),
        FinalizeOnlyStep(),
    ]
    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=steps,
    )
    with caplog.at_level(logging.WARNING, logger="doc_parser"):
        result = parser.parse()
    # Пайплайн завершён: result заполнен FinalizeOnlyStep
    assert isinstance(result, ParsedResult)

    # Оба сообщения об ошибке должны быть залогированы
    assert (
        _ERROR_MSG_FIRST in caplog.text
    ), f"Ожидалось сообщение '{_ERROR_MSG_FIRST}' в логе предупреждений, получено: {caplog.text}"
    assert (
        _ERROR_MSG_SECOND in caplog.text
    ), f"Ожидалось сообщение '{_ERROR_MSG_SECOND}' в логе предупреждений, получено: {caplog.text}"


@pytest.mark.business_logic
def test_non_critical_failure_does_not_block_next_step(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """Сбой некритичного шага не должен помешать запуску следующего шага."""
    executed_steps: list[str] = []

    steps = [
        FailingStep(DocGeneratorError(_ERROR_MSG_FIRST), record=executed_steps, record_as="fail"),
        FinalizeOnlyStep(record=executed_steps, record_as="finalize"),
    ]
    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=steps,
    )
    parser.parse()

    assert "fail" in executed_steps, "Падающий шаг не был запущен"
    assert "finalize" in executed_steps, "Шаг после сбоя некритичного шага не был выполнен"


@pytest.mark.business_logic
def test_critical_failure_stops_pipeline(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """
    Сбой критичного шага должен остановить пайплайн немедленно.

    Контрольный шаг (он лишь записывает в список факт своего запуска), стоящий в пайплайне
    после падающего критичного шага, НЕ ДОЛЖЕН выполниться.
    Пайплайн должен завершиться исключением ParsingError.
    """
    executed_after: list[str] = []

    steps = [
        FailingStep(DocGeneratorError("critical step failure"), is_critical=True),
        CallbackStep(lambda ctx: executed_after.append("ran"), name="tracking_step"),
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


@pytest.mark.business_logic
def test_context_components_empty_before_manifest_step(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """
    ctx.components пусто в самом начале пайплайна.

    Здесь ``ctx`` — ``PipelineContext``, общий контекст, который шаги пайплайна
    передают друг другу, а ``ctx.components`` — его список компонентов
    (``list[Component]``), который по ходу пайплайна наполняют шаги.

    Бизнес-правило:
        Новый ``PipelineContext`` должен создаваться с пустым списком компонентов.
        Наполнять его должен только ManifestStep (или его заглушка).
        Пустой список в начале гарантирует, что в новый запуск пайплайна не попадут
        компоненты из предыдущего запуска.

    Предусловия:
        - Пайплайн: [CallbackStep ``observing_step`` (критичный), FinalizeOnlyStep].
        - ``observing_step`` читает ``len(ctx.components)`` до того, как что-либо
          успело записаться в список.

    Шаги:
        1. Вызвать ``parser.parse()``.

    Ожидаемый результат:
        - Первое наблюдаемое ``len(ctx.components)`` равно ``0``.
    """
    observed_counts: list[int] = []

    steps = [
        CallbackStep(
            lambda ctx: observed_counts.append(len(ctx.components)),
            name="observing_step",
            is_critical=True,
        ),
        FinalizeOnlyStep(),
    ]
    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=steps,
    )
    parser.parse()

    assert len(observed_counts) > 0, "observing_step должен был быть выполнен"
    assert observed_counts[0] == 0, (
        f"ctx.components должен быть пуст перед тем, как какой-либо шаг заполнит его, "
        f"получили {observed_counts[0]}"
    )


@pytest.mark.business_logic
def test_context_result_none_before_finalize_step(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """
    ctx.result равен None перед запуском FinalizeStep.

    Бизнес-правило:
        Только FinalizeStep отвечает за установку ``ctx.result``.  Все
        шаги, которые выполняются перед ним, должны наблюдать ``ctx.result is None``.

    Предусловия:
        - Пайплайн: [FakeManifestStep, CallbackStep ``check_result_step``
          (некритичный), FinalizeOnlyStep].

    Шаги:
        1. Вызвать ``parser.parse()``.

    Ожидаемый результат:
        - Значение ``ctx.result``, прочитанное внутри ``check_result_step``, равно ``None``.
    """
    observed_results: list = []

    steps = [
        FakeManifestStep(),
        CallbackStep(lambda ctx: observed_results.append(ctx.result), name="check_result_step"),
        FinalizeOnlyStep(),
    ]
    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=steps,
    )
    parser.parse()

    assert len(observed_results) > 0, "check_result_step должен был быть выполнен"
    assert (
        observed_results[0] is None
    ), f"ctx.result должен быть None перед FinalizeStep, получено {observed_results[0]}"


@pytest.mark.business_logic
def test_exclude_removes_class_not_instance(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """
    exclude() принимает класс шага (не экземпляр и не имя) и удаляет из пайплайна шаги этого класса.

    Бизнес-правило:
        ``parser.exclude(ConanEnrichStep)`` убирает из ``self._steps`` все шаги,
        для которых ``isinstance(шаг, ConanEnrichStep)``; остальные шаги остаются.

    Предусловия:
        - Создать парсер с пайплайном по умолчанию через обычный конструктор.
        - Вызвать на нём ``parser.exclude(ConanEnrichStep)``.

    Шаги:
        1. Проверить атрибут ``_steps`` парсера после вызова ``exclude``.

    Ожидаемый результат:
        - Нет экземпляра ``ConanEnrichStep`` в ``_steps``.
        - Общее количество шагов на один меньше, чем в исходном пайплайне.
        - ``exclude`` возвращает сам парсер (``self``), поэтому вызовы можно писать
          цепочкой: ``parser.exclude(A).exclude(B)``.
    """
    parser = ComponentParser(config=parser_config, data_dir=tmp_path)
    default_count = len(parser._steps)

    returned = parser.exclude(ConanEnrichStep)

    step_classes = [type(s) for s in parser._steps]
    assert ConanEnrichStep not in step_classes, "ConanEnrichStep должен быть исключён из пайплайна"
    assert len(parser._steps) == default_count - 1, (
        f"После exclude() пайплайн должен иметь {default_count - 1} шагов, "
        f"получили {len(parser._steps)}"
    )
    assert returned is parser, "exclude() должен возвращать self (для вызовов цепочкой)"
