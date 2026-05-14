"""Юнит-тесты для autodoc/parser/parser.py (ComponentParser)."""

import datetime
from pathlib import Path

import pytest

from autodoc.exceptions import ParsingError
from autodoc.models.parsed_result import ParsedResult
from autodoc.parser.parser import ComponentParser
from autodoc.parser.pipeline.context import PipelineContext
from autodoc.parser.steps.base_parse_step import BaseParseStep
from autodoc.parser.steps.conan_step import ConanEnrichStep

# ---------------------------------------------------------------------------
# Фейковые шаги пайплайна
# ---------------------------------------------------------------------------


class FakeStep(BaseParseStep):
    """Фейковый шаг пайплайна, записывающий порядок выполнения и опционально вызывающий исключение."""

    name = "fake_step"
    is_critical = True

    def __init__(self, side_effect: Exception | None = None) -> None:
        """
        Args:
            side_effect: Исключение для вызова при execute(). None → нет действий.
        """
        self._side_effect = side_effect

    def execute(self, ctx: PipelineContext) -> None:
        """Выполняет фейковый шаг; опционально вызывает настроенное исключение."""
        if self._side_effect:
            raise self._side_effect


class FakeFinalize(BaseParseStep):
    """Фейковый FinalizeStep, заполняющий ctx.result минимальным ParsedResult."""

    name = "fake_finalize"
    is_critical = True

    def execute(self, ctx: PipelineContext) -> None:
        """Заполняет ctx.result минимальным корректным ParsedResult."""
        ctx.result = ParsedResult(
            generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            platform_version=ctx.config.platform_version,
            profile_definitions=[],
            components=[],
        )


class NonCriticalStep(BaseParseStep):
    """Некритичный шаг, всегда вызывающий ParsingError."""

    name = "non_critical"
    is_critical = False

    def execute(self, ctx: PipelineContext) -> None:
        """Всегда вызывает исключение для имитации некритичного сбоя."""
        raise ParsingError("non-critical boom")


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------


def test_component_parser_parse_returns_parsed_result(
    parser_config,
    tmp_path,
) -> None:
    """Успешный путь: parse() возвращает ParsedResult, когда FakeFinalize заполняет ctx.result."""
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
    """Сбой критичного шага вызывает ParsingError, последующие шаги не выполняются."""
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
    """Сбой некритичного шага поглощается, и пайплайн продолжает работу до завершения."""
    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=[NonCriticalStep(), FakeFinalize()],
    )
    result = parser.parse()  # не должно вызывать исключений
    assert isinstance(result, ParsedResult)


def test_component_parser_cleans_up_tmp_dir_on_success(
    parser_config,
    tmp_path,
) -> None:
    """tmp_dir удаляется после успешного парсинга (блок finally)."""
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
    """tmp_dir удаляется даже когда критичный шаг вызывает исключение (блок finally)."""
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
    """Если ни один шаг не заполняет ctx.result, parse() вызывает ParsingError после завершения всех шагов."""
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
    """Фабричный метод with_steps_excluded удаляет все экземпляры указанного класса шагов."""
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
    """Когда tfs_client передаётся через конструктор, TFSClient.__init__ никогда не вызывается."""
    from tests.unit.parser.conftest import FakeTFSClient

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
    """parse(save_intermediate=True) записывает хотя бы один JSON-файл в директорию intermediate."""
    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=[FakeFinalize()],
    )
    parser.parse(save_intermediate=True)
    intermediate_dir = tmp_path / "intermediate"
    json_files = list(intermediate_dir.glob("*.json"))
    assert len(json_files) >= 1
