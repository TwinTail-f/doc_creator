"""Юнит-тесты для autodoc/parser/steps/validation_step.py."""

import pytest
import requests

from autodoc.models.component import Component
from autodoc.models.conan_variant import ConanVariant, ProfileBuild
from autodoc.models.release import Release
from autodoc.parser.steps.validation_step import ArtifactoryValidationStep
from tests.unit.parser.steps.conftest import FakeArtifactoryClient

REAL_PACKAGE_ID: str = "575ea8086554107ae2c0fdbb4909d62390c52b77"
UI_URL: str = "https://art.example.com/ui/repos/tree/General/conan2/lib/package"
_VS_UI_URL_PREFIX: str = "http://art/ui/repos/tree/General/repo"


class _MixedClient(FakeArtifactoryClient):
    """
    Возвращает 404 для 'dead' и 200 для остальных URL, записывая вызванные URL.

    Переиспользует отслеживание called_urls и сборку Response из
    FakeArtifactoryClient.check_url(), переопределяя только выбор статуса.
    """

    def _status_for(self, url: str) -> int:
        """Возвращает 404, если в URL встречается 'dead', иначе 200."""
        return 404 if "dead" in url else 200


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
    pb = ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2", exists=True, variants=[variant])
    release = Release(
        version="1.0.0",
        platform="2.0",
        channel="tech",
        profile_builds=[pb],
    )
    component = Component(name="lib", git_project="DEP", git_repo="lib", releases=[release])
    return component, pb, variant


def _make_variant(url: str, package_id: str = "abc123") -> ConanVariant:
    """Строит минимальный ConanVariant с заданными build_url и package_id."""
    return ConanVariant(
        package_id=package_id,
        build_url=url,
        build_date="2024-01-01",
        options_ref="1",
    )


def _make_tree(
    url: str, package_id: str = "abc123"
) -> tuple[Component, Release, ProfileBuild, ConanVariant]:
    """Строит дерево Component → Release → ProfileBuild → ConanVariant с заданным URL."""
    variant = _make_variant(url, package_id)
    pb = ProfileBuild(profile_name="hw-linux-x86_64", exists=True, variants=[variant])
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
    return comp, release, pb, variant


class _RaisingClient:
    """Фейковый клиент Artifactory, чей check_url() всегда вызывает RequestException."""

    def check_url(self, url: str) -> requests.Response:
        """Безусловно вызывает сетевую ошибку."""
        raise requests.RequestException("network failure")


@pytest.mark.business_logic
def test_validation_step_keeps_200_variant(
    parser_pipeline_context,
) -> None:
    """Вариант, чей build_url возвращает HTTP 200, остаётся в pb.variants."""
    component, pb, _ = _make_component_with_variant(build_url=UI_URL)
    parser_pipeline_context.components = [component]
    parser_pipeline_context.artifactory_client = FakeArtifactoryClient(status_code=200)
    step = ArtifactoryValidationStep()
    step.execute(parser_pipeline_context)
    assert len(pb.variants) == 1


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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
    recording_client = FakeArtifactoryClient(status_code=200)
    parser_pipeline_context.artifactory_client = recording_client
    step = ArtifactoryValidationStep()
    step.execute(parser_pipeline_context)
    assert len(recording_client.called_urls) == 4


@pytest.mark.business_logic
def test_404_removes_variant_from_profile_build(
    parser_pipeline_context,
) -> None:
    """HTTP 404 при HEAD-запросе удаляет вариант из ProfileBuild.variants."""
    comp, _, pb, variant = _make_tree(f"{_VS_UI_URL_PREFIX}/v1.zip")
    ctx = parser_pipeline_context
    ctx.components = [comp]
    ctx.artifactory_client = FakeArtifactoryClient(status_code=404)

    ArtifactoryValidationStep().execute(ctx)

    assert variant not in pb.variants, "Вариант с 404 должен быть удалён"
    assert len(pb.variants) == 0


@pytest.mark.business_logic
def test_network_error_keeps_variant_fail_open(
    parser_pipeline_context,
) -> None:
    """RequestException при HEAD-запросе не удаляет вариант (fail-open)."""
    comp, _, pb, variant = _make_tree(f"{_VS_UI_URL_PREFIX}/v1.zip")
    ctx = parser_pipeline_context
    ctx.components = [comp]
    ctx.artifactory_client = _RaisingClient()

    ArtifactoryValidationStep().execute(ctx)

    assert variant in pb.variants, "При сетевой ошибке вариант должен остаться (fail-open)"
    assert len(pb.variants) == 1


@pytest.mark.business_logic
def test_ui_url_converted_to_api_url_before_head(
    parser_pipeline_context,
) -> None:
    """UI URL преобразуется в API URL перед HEAD-запросом."""
    ui_url = "http://art/ui/repos/tree/General/repo/path/pkg.zip"
    comp, _, pb, variant = _make_tree(ui_url)
    ctx = parser_pipeline_context
    ctx.components = [comp]
    recording_client = FakeArtifactoryClient(status_code=200)
    ctx.artifactory_client = recording_client

    ArtifactoryValidationStep().execute(ctx)

    assert len(recording_client.called_urls) == 1, "Ожидался ровно один HEAD-запрос"
    called = recording_client.called_urls[0]
    assert (
        "/ui/repos/tree/General/" not in called
    ), f"UI-путь не должен встречаться в HEAD-URL: {called}"
    assert (
        "/artifactory/" in called
    ), f"API-путь '/artifactory/' должен встречаться в HEAD-URL: {called}"


@pytest.mark.business_logic
def test_empty_build_url_skips_head_check(
    parser_pipeline_context,
) -> None:
    """Вариант с пустым build_url не проверяется через HEAD и не удаляется."""
    comp, _, pb, variant = _make_tree("")  # empty URL
    ctx = parser_pipeline_context
    ctx.components = [comp]
    recording_client = FakeArtifactoryClient(status_code=200)
    ctx.artifactory_client = recording_client

    ArtifactoryValidationStep().execute(ctx)

    assert (
        recording_client.called_urls == []
    ), "HEAD не должен вызываться для варианта с пустым build_url"
    assert variant in pb.variants, "Вариант с пустым build_url не должен удаляться"


@pytest.mark.business_logic
def test_profile_build_with_all_dead_variants_becomes_empty_not_removed(
    parser_pipeline_context,
) -> None:
    """ProfileBuild с полностью мёртвыми вариантами остаётся в release.profile_builds пустым."""
    v1 = _make_variant(f"{_VS_UI_URL_PREFIX}/v1.zip", "id1")
    v2 = _make_variant(f"{_VS_UI_URL_PREFIX}/v2.zip", "id2")
    pb = ProfileBuild(profile_name="hw-linux-x86_64", exists=True, variants=[v1, v2])
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
    ctx = parser_pipeline_context
    ctx.components = [comp]
    ctx.artifactory_client = FakeArtifactoryClient(status_code=404)

    ArtifactoryValidationStep().execute(ctx)

    assert pb.variants == [], "Все варианты должны быть удалены при 404"
    assert (
        pb in release.profile_builds
    ), "ProfileBuild не должен удаляться — это ответственность FinalizeStep"
    assert len(release.profile_builds) == 1


@pytest.mark.business_logic
def test_validation_step_mixed_alive_and_dead_variants_partial_removal(
    parser_pipeline_context,
) -> None:
    """В одном execute() мёртвый (404) вариант удаляется, а живой (200) — остаётся."""
    v_dead = _make_variant(f"{_VS_UI_URL_PREFIX}/dead.zip", "dead-id")
    v_alive = _make_variant(f"{_VS_UI_URL_PREFIX}/alive.zip", "alive-id")
    pb = ProfileBuild(profile_name="hw-linux-x86_64", exists=True, variants=[v_dead, v_alive])
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

    ctx = parser_pipeline_context
    ctx.components = [comp]
    ctx.artifactory_client = _MixedClient()

    ArtifactoryValidationStep().execute(ctx)

    assert v_dead not in pb.variants
    assert v_alive in pb.variants
    assert len(pb.variants) == 1


@pytest.mark.business_logic
def test_validation_step_removes_two_consecutive_dead_variants(
    parser_pipeline_context,
) -> None:
    """
    Удаление двух подряд идущих в списке мёртвых (404) вариантов не пропускает
    ни один из них: _remove_dead_variants удаляет по значению из dead_variants,
    а не по индексу while перебирает pb.variants, поэтому сдвиг индексов после
    первого remove() не приводит к пропуску следующего элемента."""
    v_dead1 = _make_variant(f"{_VS_UI_URL_PREFIX}/dead1.zip", "dead-id-1")
    v_dead2 = _make_variant(f"{_VS_UI_URL_PREFIX}/dead2.zip", "dead-id-2")
    v_alive = _make_variant(f"{_VS_UI_URL_PREFIX}/alive.zip", "alive-id")
    pb = ProfileBuild(
        profile_name="hw-linux-x86_64",
        exists=True,
        variants=[v_dead1, v_dead2, v_alive],
    )
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

    ctx = parser_pipeline_context
    ctx.components = [comp]
    ctx.artifactory_client = _MixedClient()

    ArtifactoryValidationStep().execute(ctx)

    assert v_dead1 not in pb.variants
    assert v_dead2 not in pb.variants
    assert v_alive in pb.variants
    assert len(pb.variants) == 1


@pytest.mark.business_logic
def test_validation_step_non_404_error_status_keeps_variant(
    parser_pipeline_context,
) -> None:
    """Статус, отличный от 404 (например 500), не приводит к удалению варианта."""
    comp, _, pb, variant = _make_tree(f"{_VS_UI_URL_PREFIX}/v1.zip")
    ctx = parser_pipeline_context
    ctx.components = [comp]
    ctx.artifactory_client = FakeArtifactoryClient(status_code=500)

    ArtifactoryValidationStep().execute(ctx)

    assert variant in pb.variants
    assert len(pb.variants) == 1


class _UnexpectedErrorClient:
    """
    Фейковый клиент Artifactory, чей check_url() бросает ValueError —
    ParallelExecutor перехватывает такие ошибки домена задач и подставляет
    None на место результата, вместо падения check_one()."""

    def check_url(self, url: str) -> requests.Response:
        """Безусловно бросает ValueError, не связанный с сетью."""
        raise ValueError("unexpected parsing failure inside check_url")


@pytest.mark.business_logic
def test_check_one_unexpected_exception_swallowed_by_executor_keeps_variant(
    parser_pipeline_context,
) -> None:
    """
    Если check_url() бросает исключение, не являющееся requests.RequestException
    (например ValueError), ParallelExecutor перехватывает его и возвращает
    None вместо результата — execute() не должен падать, а вариант должен
    остаться (ветка `result is None: continue` в _check_urls_parallel)."""
    comp, _, pb, variant = _make_tree(f"{_VS_UI_URL_PREFIX}/v1.zip")
    ctx = parser_pipeline_context
    ctx.components = [comp]
    ctx.artifactory_client = _UnexpectedErrorClient()

    ArtifactoryValidationStep().execute(ctx)  # не должно вызывать исключений

    assert variant in pb.variants, "При None-результате executor'а вариант не должен удаляться"
    assert len(pb.variants) == 1


@pytest.mark.business_logic
def test_remove_dead_variants_skips_variant_already_absent() -> None:
    """
    _remove_dead_variants не падает и не выполняет повторное удаление,
    если один и тот же вариант дважды попал в список мёртвых (например,
    из-за дублирующегося build_url у двух записей) — вторая попытка должна
    молча пропускаться веткой `if variant in pb.variants`."""
    variant = _make_variant(f"{_VS_UI_URL_PREFIX}/dup.zip", "dup-id")
    pb = ProfileBuild(profile_name="hw-linux-x86_64", exists=True, variants=[variant])

    step = ArtifactoryValidationStep()
    step._remove_dead_variants([(pb, variant), (pb, variant)])

    assert pb.variants == []
