"""Юнит-тесты для autodoc/parser/steps/validation_step.py."""

import pytest
import requests

from autodoc.models.component import Component, ConanVariant, ProfileBuild, Release
from autodoc.parser.steps.validation_step import ArtifactoryValidationStep

NULL_PACKAGE_ID: str = "da39a3ee5e6b4b0d3255bfef95601890afd80709"
REAL_PACKAGE_ID: str = "575ea8086554107ae2c0fdbb4909d62390c52b77"
UI_URL: str = "https://art.example.com/ui/repos/tree/General/conan2/lib/package"
API_URL: str = "https://art.example.com/artifactory/conan2/lib/package"


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


def _make_component_with_variant(
    package_id: str = REAL_PACKAGE_ID,
    build_url: str = UI_URL,
) -> tuple[Component, ProfileBuild, ConanVariant]:
    """Строит минимальное дерево Component → Release → ProfileBuild → ConanVariant."""
    variant = ConanVariant(
        package_id=package_id,
        build_url=build_url,
        build_date="2024-01-01",
        options_ref="1",
    )
    pb = ProfileBuild(
        profile_name="hw-linux-x86_64-gcc10_2", exists=True, variants=[variant]
    )
    release = Release(
        version="1.0.0",
        platform="2.0",
        channel="tech",
        git_url="DEP/_git/lib",
        profile_builds=[pb],
    )
    component = Component(
        name="lib", git_project="DEP", git_repo="lib", releases=[release]
    )
    return component, pb, variant


class _RecordingClient:
    """Фейковый клиент Artifactory, записывающий вызовы head() и возвращающий фиксированный статус."""

    def __init__(self, status_code: int = 200) -> None:
        """
        Args:
            status_code: Возвращаемый HTTP-код статуса.
        """
        self.status_code = status_code
        self.called_urls: list[str] = []

    def head(self, url: str) -> requests.Response:
        """Записывает URL и возвращает настроенный ответ."""
        self.called_urls.append(url)
        resp = requests.Response()
        resp.status_code = self.status_code
        return resp


class _RaisingClient:
    """Фейковый клиент Artifactory, чей head() всегда вызывает RequestException."""

    def head(self, url: str) -> requests.Response:
        """Безусловно вызывает сетевую ошибку."""
        raise requests.RequestException("network failure")


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------


def test_validation_step_removes_404_variant(
    parser_pipeline_context,
    artifactory_client,
) -> None:
    """Вариант, чей build_url возвращает HTTP 404, удаляется из pb.variants."""
    component, pb, _ = _make_component_with_variant(build_url=UI_URL)
    parser_pipeline_context.components = [component]
    parser_pipeline_context.artifactory_client = artifactory_client.__class__(
        status_code=404
    )
    step = ArtifactoryValidationStep()
    step.execute(parser_pipeline_context)
    assert pb.variants == []


def test_validation_step_keeps_200_variant(
    parser_pipeline_context,
    artifactory_client,
) -> None:
    """Вариант, чей build_url возвращает HTTP 200, остаётся в pb.variants."""
    component, pb, _ = _make_component_with_variant(build_url=UI_URL)
    parser_pipeline_context.components = [component]
    parser_pipeline_context.artifactory_client = artifactory_client.__class__(
        status_code=200
    )
    step = ArtifactoryValidationStep()
    step.execute(parser_pipeline_context)
    assert len(pb.variants) == 1


def test_validation_step_transforms_ui_url_to_api_url(
    parser_pipeline_context,
) -> None:
    """UI URL преобразуется в API URL перед вызовом client.head()."""
    component, _, _ = _make_component_with_variant(build_url=UI_URL)
    parser_pipeline_context.components = [component]
    recording_client = _RecordingClient(status_code=200)
    parser_pipeline_context.artifactory_client = recording_client
    step = ArtifactoryValidationStep()
    step.execute(parser_pipeline_context)
    assert recording_client.called_urls == [API_URL]


def test_validation_step_keeps_variant_on_network_exception(
    parser_pipeline_context,
) -> None:
    """Сетевое исключение во время проверки HEAD не удаляет вариант (fail-open)."""
    component, pb, _ = _make_component_with_variant(build_url=UI_URL)
    parser_pipeline_context.components = [component]
    parser_pipeline_context.artifactory_client = _RaisingClient()
    step = ArtifactoryValidationStep()
    step.execute(parser_pipeline_context)
    assert len(pb.variants) == 1


def test_validation_step_skips_variant_with_empty_build_url(
    parser_pipeline_context,
) -> None:
    """Вариант с пустым build_url не проверяется вообще (head() никогда не вызывается)."""
    component, _, _ = _make_component_with_variant(build_url="")
    parser_pipeline_context.components = [component]
    recording_client = _RecordingClient(status_code=200)
    parser_pipeline_context.artifactory_client = recording_client
    step = ArtifactoryValidationStep()
    step.execute(parser_pipeline_context)
    assert recording_client.called_urls == []


def test_validation_step_no_client_skips(
    parser_pipeline_context,
) -> None:
    """Когда artifactory_client равен None, шаг завершается без исключений."""
    component, pb, _ = _make_component_with_variant(build_url=UI_URL)
    parser_pipeline_context.components = [component]
    parser_pipeline_context.artifactory_client = None
    step = ArtifactoryValidationStep()
    step.execute(parser_pipeline_context)  # не должно вызывать исключений
    assert len(pb.variants) == 1


def test_collect_variants_collects_all_variants(
    parser_pipeline_context,
) -> None:
    """_collect_variants собирает все варианты по всем компонентам и профилям."""
    # Строим 2 компонента × 2 профиля × 1 вариант каждый → 4 собранных
    components: list[Component] = []
    for comp_idx in range(2):
        profile_builds: list[ProfileBuild] = []
        for pb_idx in range(2):
            variant = ConanVariant(
                package_id=REAL_PACKAGE_ID,
                build_url=UI_URL,
                build_date="2024-01-01",
                options_ref="1",
            )
            profile_builds.append(
                ProfileBuild(
                    profile_name=f"profile_{comp_idx}_{pb_idx}",
                    exists=True,
                    variants=[variant],
                )
            )
        release = Release(
            version="1.0.0",
            platform="2.0",
            channel="tech",
            git_url="DEP/_git/lib",
            profile_builds=profile_builds,
        )
        components.append(
            Component(
                name=f"comp_{comp_idx}",
                git_project="DEP",
                git_repo=f"lib_{comp_idx}",
                releases=[release],
            )
        )

    parser_pipeline_context.components = components
    recording_client = _RecordingClient(status_code=200)
    parser_pipeline_context.artifactory_client = recording_client
    step = ArtifactoryValidationStep()
    step.execute(parser_pipeline_context)
    assert len(recording_client.called_urls) == 4
