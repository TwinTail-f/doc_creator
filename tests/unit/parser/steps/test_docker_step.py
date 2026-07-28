"""Юнит-тесты для autodoc/parser/steps/docker_step.py."""

import pytest

from autodoc.parser.steps.docker_step import DockerResolveStep

DockerLinksMap = dict[str, str]


@pytest.mark.business_logic
def test_docker_step_stores_links_in_intermediate(
    parser_pipeline_context,
    make_fake_fetcher,
) -> None:
    """ctx.intermediate['docker_links'] заполняется результатом fetcher."""
    docker_links: DockerLinksMap = {"linux-x86_64": "harbor.example.com/img:tag"}
    fake = make_fake_fetcher(value=docker_links)
    step = DockerResolveStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert (
        parser_pipeline_context.intermediate["docker_links"]["linux-x86_64"]
        == "harbor.example.com/img:tag"
    )


@pytest.mark.business_logic
def test_docker_step_upserts_profile_definitions(
    parser_pipeline_context,
    manifest_component,
    make_fake_fetcher,
) -> None:
    """DataEnricher.apply_docker_links добавляет запись ProfileDefinition для профиля компонента."""
    # manifest_component имеет profile_name="hw-linux-x86_64-gcc10_2"
    parser_pipeline_context.components = [manifest_component]
    docker_links: DockerLinksMap = {"hw-linux-x86_64-gcc10_2": "harbor.example.com/img"}
    fake = make_fake_fetcher(value=docker_links)
    step = DockerResolveStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert len(parser_pipeline_context.profile_definitions) == 1
    pd = parser_pipeline_context.profile_definitions[0]
    assert pd.profile_name == "hw-linux-x86_64-gcc10_2"
    assert pd.docker_image == "harbor.example.com/img"


@pytest.mark.business_logic
def test_docker_step_empty_links_does_not_clear_profile_definitions(
    parser_pipeline_context,
    manifest_component,
    make_fake_fetcher,
) -> None:
    """Пустой словарь docker links не удаляет уже существующую запись ProfileDefinition
    для профиля, реально присутствующего среди компонентов контекста.

    manifest_component имеет profile_name="hw-linux-x86_64-gcc10_2" — то же имя,
    что и у pre_existing, поэтому apply_docker_links() действительно проходит
    по этому профилю (без реального компонента с совпадающим профилем цикл
    в DataEnricher.apply_docker_links() не выполнился бы, и проверка была бы
    тривиально истинной вне зависимости от корректности обработки пустого словаря).
    """
    from autodoc.models.parsed_result import ProfileDefinition

    parser_pipeline_context.components = [manifest_component]
    pre_existing = ProfileDefinition(profile_name="hw-linux-x86_64-gcc10_2")
    parser_pipeline_context.profile_definitions = [pre_existing]

    fake = make_fake_fetcher(value={})
    step = DockerResolveStep(fetcher=fake)
    step.execute(parser_pipeline_context)

    assert pre_existing in parser_pipeline_context.profile_definitions


@pytest.mark.contract
def test_docker_step_default_fetcher_is_docker_fetcher() -> None:
    """DockerResolveStep() без аргумента fetcher создаёт по умолчанию реальный DockerFetcher."""
    from autodoc.parser.fetchers.docker_fetcher import DockerFetcher

    step = DockerResolveStep()
    assert isinstance(step._fetcher, DockerFetcher)


@pytest.mark.infrastructure
def test_docker_step_warnings_do_not_raise(
    parser_pipeline_context,
    make_fake_fetcher,
) -> None:
    """Предупреждения от fetcher не вызывают исключений при выполнении шага."""
    fake = make_fake_fetcher(value={}, warnings=["docker profile fetch timeout"])
    step = DockerResolveStep(fetcher=fake)
    step.execute(parser_pipeline_context)  # не должно вызывать исключений
