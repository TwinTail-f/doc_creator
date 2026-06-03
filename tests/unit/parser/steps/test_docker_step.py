"""Юнит-тесты для autodoc/parser/steps/docker_step.py."""

import pytest

from autodoc.parser.steps.docker_step import DockerResolveStep

DockerLinksMap = dict[str, str]


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------


@pytest.mark.infrastructure
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
    assert len(parser_pipeline_context.profile_definitions) >= 1


@pytest.mark.business_logic
def test_docker_step_is_not_critical() -> None:
    """DockerResolveStep является некритичным шагом пайплайна."""
    assert DockerResolveStep.is_critical is False


# ---------------------------------------------------------------------------
# GAP 2 — partial YAML and multiple profiles
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_docker_step_profile_with_no_docker_key_is_absent_from_links(
    parser_pipeline_context,
    make_fake_fetcher,
) -> None:
    """Arch without 'docker' key in YAML is excluded; step stores only the parsed entries."""
    # DockerFetcher/DockerParser already filtered the incomplete arch — simulate result
    partial_links: DockerLinksMap = {
        "hw-linux-x86_64-gcc10_2": "harbor.example.com/debian11:gcc10",
        # "hw-linux-armv7hf-gcc10_2" absent: no docker: field in its YAML block
    }
    fake = make_fake_fetcher(value=partial_links)
    step = DockerResolveStep(fetcher=fake)
    step.execute(parser_pipeline_context)

    links = parser_pipeline_context.intermediate["docker_links"]
    assert "hw-linux-x86_64-gcc10_2" in links
    assert "hw-linux-armv7hf-gcc10_2" not in links
    assert links["hw-linux-x86_64-gcc10_2"] == "harbor.example.com/debian11:gcc10"


@pytest.mark.business_logic
def test_docker_step_multiple_profile_urls_all_links_merged(
    parser_pipeline_context,
    make_fake_fetcher,
) -> None:
    """Links from multiple YAML files (merged by fetcher) all appear in intermediate."""
    merged_links: DockerLinksMap = {
        "hw-linux-x86_64-gcc10_2": "harbor.example.com/debian11:gcc10",
        "hw-linux-armv7hf-gcc10_2": "harbor.example.com/debian11:armv7",
        "mobile-android-x86_64": "harbor.example.com/android:ndk25",
    }
    fake = make_fake_fetcher(value=merged_links)
    step = DockerResolveStep(fetcher=fake)
    step.execute(parser_pipeline_context)

    links = parser_pipeline_context.intermediate["docker_links"]
    assert len(links) == 3
    assert links["hw-linux-x86_64-gcc10_2"] == "harbor.example.com/debian11:gcc10"
    assert links["hw-linux-armv7hf-gcc10_2"] == "harbor.example.com/debian11:armv7"
    assert links["mobile-android-x86_64"] == "harbor.example.com/android:ndk25"


@pytest.mark.business_logic
def test_docker_step_empty_links_does_not_clear_profile_definitions(
    parser_pipeline_context,
    make_fake_fetcher,
) -> None:
    """Empty docker links dict does not remove pre-existing ProfileDefinitions from context."""
    from autodoc.models.parsed_result import ProfileDefinition

    pre_existing = ProfileDefinition(profile_name="hw-linux-x86_64-gcc10_2")
    parser_pipeline_context.profile_definitions = [pre_existing]

    fake = make_fake_fetcher(value={})
    step = DockerResolveStep(fetcher=fake)
    step.execute(parser_pipeline_context)

    assert pre_existing in parser_pipeline_context.profile_definitions
