"""Юнит-тесты для autodoc/parser/steps/docker_step.py."""

import pytest

from autodoc.parser.fetchers.models.fetch_result import FetchResult
from autodoc.parser.steps.docker_step import DockerResolveStep

DockerLinksMap = dict[str, str]


# ---------------------------------------------------------------------------
# Фейковый Fetcher
# ---------------------------------------------------------------------------


class FakeFetcher:
    """Управляемый фейковый fetcher для юнит-тестов DockerResolveStep."""

    def __init__(
        self,
        value: DockerLinksMap,
        warnings: list[str] | None = None,
    ) -> None:
        """
        Args:
            value: Карта docker-ссылок, возвращаемая из fetch().
            warnings: Необязательный список строк предупреждений.
        """
        self.value = value
        self.warnings = warnings or []
        self.configure_called: bool = False
        self.fetch_called: bool = False

    def configure(self, ctx: object) -> None:
        """Записывает факт вызова configure."""
        self.configure_called = True

    def fetch(self, *args: object, **kwargs: object) -> FetchResult:
        """Возвращает управляемый FetchResult."""
        self.fetch_called = True
        return FetchResult(value=self.value, warnings=self.warnings)


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------


def test_docker_step_stores_links_in_intermediate(
    parser_pipeline_context,
) -> None:
    """ctx.intermediate['docker_links'] заполняется результатом fetcher."""
    docker_links: DockerLinksMap = {"linux-x86_64": "harbor.example.com/img:tag"}
    fake = FakeFetcher(value=docker_links)
    step = DockerResolveStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert (
        parser_pipeline_context.intermediate["docker_links"]["linux-x86_64"]
        == "harbor.example.com/img:tag"
    )


def test_docker_step_upserts_profile_definitions(
    parser_pipeline_context,
    manifest_component,
) -> None:
    """DataEnricher.apply_docker_links добавляет запись ProfileDefinition для профиля компонента."""
    # manifest_component имеет profile_name="hw-linux-x86_64-gcc10_2"
    parser_pipeline_context.components = [manifest_component]
    docker_links: DockerLinksMap = {"hw-linux-x86_64-gcc10_2": "harbor.example.com/img"}
    fake = FakeFetcher(value=docker_links)
    step = DockerResolveStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert len(parser_pipeline_context.profile_definitions) >= 1


def test_docker_step_is_not_critical() -> None:
    """DockerResolveStep является некритичным шагом пайплайна."""
    assert DockerResolveStep.is_critical is False
