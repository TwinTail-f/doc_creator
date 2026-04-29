"""Юнит-тесты для autodoc/parser/pipeline/context.py и BaseParseStep."""

import pytest

from autodoc.parser.pipeline.context import PipelineContext
from autodoc.parser.steps.base import BaseParseStep

# ---------------------------------------------------------------------------
# Тесты: PipelineContext
# ---------------------------------------------------------------------------


def test_pipeline_context_construction(
    parser_config,
    tmp_path,
) -> None:
    """PipelineContext инициализируется с пустыми components и result=None."""
    ctx = PipelineContext(config=parser_config, tmp_dir=tmp_path)
    assert ctx.components == []
    assert ctx.result is None


def test_pipeline_context_snapshot_excludes_docker_links(
    parser_config,
    tmp_path,
) -> None:
    """to_snapshot_dict исключает 'docker_links' из intermediate, но сообщает его количество."""
    ctx = PipelineContext(config=parser_config, tmp_dir=tmp_path)
    ctx.intermediate["docker_links"] = {"key1": "val1"}
    snapshot = ctx.to_snapshot_dict()
    assert "docker_links" not in snapshot["intermediate"]
    assert snapshot["docker_links_count"] == 1


def test_pipeline_context_snapshot_includes_components_count(
    parser_config,
    tmp_path,
    manifest_component,
) -> None:
    """to_snapshot_dict включает components_count, равный len(ctx.components)."""
    ctx = PipelineContext(config=parser_config, tmp_dir=tmp_path)
    ctx.components = [manifest_component]
    snapshot = ctx.to_snapshot_dict()
    assert snapshot["components_count"] == 1


def test_pipeline_context_snapshot_converts_tuple_keys(
    parser_config,
    tmp_path,
) -> None:
    """to_snapshot_dict преобразует ключи-кортежи в промежуточных словарях в строковые представления."""
    ctx = PipelineContext(config=parser_config, tmp_dir=tmp_path)
    ctx.intermediate["test_data"] = {("a", "b"): "value"}
    snapshot = ctx.to_snapshot_dict()
    keys = list(snapshot["intermediate"]["test_data"].keys())
    assert all(isinstance(k, str) for k in keys)


# ---------------------------------------------------------------------------
# Тесты: BaseParseStep
# ---------------------------------------------------------------------------


def test_base_parse_step_requires_name_attribute() -> None:
    """Определение подкласса BaseParseStep с пустым именем вызывает TypeError при определении класса."""
    with pytest.raises(TypeError):

        class BadStep(BaseParseStep):
            """Шаг с пустым именем — должен вызывать исключение при определении класса."""

            name = ""  # ложное значение → __init_subclass__ вызывает исключение

            def execute(self, ctx: PipelineContext) -> None:
                """Пустой execute для некорректного шага."""
