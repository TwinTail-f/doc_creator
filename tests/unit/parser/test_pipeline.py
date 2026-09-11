"""Юнит-тесты для autodoc/parser/pipeline/context.py и BaseParseStep."""

import pytest

from autodoc.models.profile_definition import ProfileDefinition
from autodoc.parser.pipeline.context import PipelineContext
from autodoc.parser.steps.base_parse_step import BaseParseStep


@pytest.mark.business_logic
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


@pytest.mark.business_logic
def test_pipeline_context_snapshot_includes_components_count(
    parser_config,
    tmp_path,
    manifest_component,
) -> None:
    """
    to_snapshot_dict включает components_count, равный len(ctx.components).

    Отмечено как ``business_logic`` для согласованности с соседним тестом
    ``test_pipeline_context_snapshot_excludes_docker_links`` в этом же файле:
    оба теста описывают одно и то же контрактное поведение ``to_snapshot_dict``
    (что именно попадает в диагностический снимок), хотя реализация поля
    ``components_count`` сама по себе — тривиальный ``len()``.
    """
    ctx = PipelineContext(config=parser_config, tmp_dir=tmp_path)
    ctx.components = [manifest_component]
    snapshot = ctx.to_snapshot_dict()
    assert snapshot["components_count"] == 1


@pytest.mark.business_logic
def test_pipeline_context_snapshot_includes_profile_definitions(
    parser_config,
    tmp_path,
) -> None:
    """to_snapshot_dict включает ctx.profile_definitions (он терялся, зафиксируем)."""
    ctx = PipelineContext(config=parser_config, tmp_dir=tmp_path)
    ctx.profile_definitions = [
        ProfileDefinition(
            profile_name="linux-x64",
            conan_settings={"os": "Linux"},
            docker_image="registry.example.com/linux-x64:latest",
        )
    ]
    snapshot = ctx.to_snapshot_dict()
    assert snapshot["profile_definitions"] == [
        {
            "profile_name": "linux-x64",
            "conan_settings": {"os": "Linux"},
            "docker_image": "registry.example.com/linux-x64:latest",
        }
    ]


@pytest.mark.business_logic
def test_pipeline_context_snapshot_handles_non_dict_intermediate(
    parser_config,
    tmp_path,
) -> None:
    """to_snapshot_dict корректно переносит нестроковое значение intermediate без словаря."""
    ctx = PipelineContext(config=parser_config, tmp_dir=tmp_path)
    ctx.intermediate["plain_value"] = "just a string, not a dict"
    snapshot = ctx.to_snapshot_dict()
    assert snapshot["intermediate"]["plain_value"] == "just a string, not a dict"


@pytest.mark.business_logic
def test_pipeline_context_snapshot_converts_tuple_keys(
    parser_config,
    tmp_path,
) -> None:
    """to_snapshot_dict преобразует ключи-кортежи в промежуточных словарях в строковые представления."""
    ctx = PipelineContext(config=parser_config, tmp_dir=tmp_path)
    ctx.intermediate["test_data"] = {("a", "b"): "value"}
    snapshot = ctx.to_snapshot_dict()
    keys = list(snapshot["intermediate"]["test_data"].keys())
    assert keys == ["['a', 'b']"]


@pytest.mark.contract
def test_base_parse_step_requires_name_attribute() -> None:
    """Определение подкласса BaseParseStep с пустым именем вызывает TypeError при определении класса."""
    with pytest.raises(TypeError):

        class BadStep(BaseParseStep):
            """Шаг с пустым именем — должен вызывать исключение при определении класса."""

            name = ""  # ложное значение → __init_subclass__ вызывает исключение

            def execute(self, ctx: PipelineContext) -> None:
                """Пустой execute для некорректного шага."""
