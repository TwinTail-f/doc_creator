"""Unit tests for autodoc/parser/steps/docker_step.py."""

import pytest

from autodoc.parser.fetchers.base import FetchResult
from autodoc.parser.steps.docker_step import DockerResolveStep

DockerLinksMap = dict[str, str]


# ---------------------------------------------------------------------------
# Fake Fetcher
# ---------------------------------------------------------------------------


class FakeFetcher:
    """Controllable fake fetcher for DockerResolveStep unit tests."""

    def __init__(
        self,
        value: DockerLinksMap,
        warnings: list[str] | None = None,
    ) -> None:
        """
        Args:
            value: The docker links map to return from fetch().
            warnings: Optional list of warning strings.
        """
        self.value = value
        self.warnings = warnings or []
        self.configure_called: bool = False
        self.fetch_called: bool = False

    def configure(self, ctx: object) -> None:
        """Record that configure was called."""
        self.configure_called = True

    def fetch(self, *args: object, **kwargs: object) -> FetchResult:
        """Return controlled FetchResult."""
        self.fetch_called = True
        return FetchResult(value=self.value, warnings=self.warnings)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_docker_step_stores_links_in_intermediate(
    parser_pipeline_context,
) -> None:
    """ctx.intermediate['docker_links'] is populated with the fetcher result."""
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
    """DataEnricher.apply_docker_links adds a ProfileDefinition entry for the component's profile."""
    # manifest_component has profile_name="hw-linux-x86_64-gcc10_2"
    parser_pipeline_context.components = [manifest_component]
    docker_links: DockerLinksMap = {"hw-linux-x86_64-gcc10_2": "harbor.example.com/img"}
    fake = FakeFetcher(value=docker_links)
    step = DockerResolveStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert len(parser_pipeline_context.profile_definitions) >= 1


def test_docker_step_is_not_critical() -> None:
    """DockerResolveStep is a non-critical pipeline step."""
    assert DockerResolveStep.is_critical is False
