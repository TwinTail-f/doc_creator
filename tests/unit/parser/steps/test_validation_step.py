"""Юнит-тесты для autodoc/parser/steps/validation_step.py."""

import pytest
import requests

from autodoc.models.component import Component
from autodoc.models.conan_variant import ConanVariant, ProfileBuild
from autodoc.models.release import Release
from autodoc.parser.steps.validation_step import ArtifactoryValidationStep

# ---------------------------------------------------------------------------
# T3.7 — Make ParallelExecutor synchronous in all tests in this module
# ---------------------------------------------------------------------------


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


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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
    recording_client = _RecordingClient(status_code=200)
    parser_pipeline_context.artifactory_client = recording_client
    step = ArtifactoryValidationStep()
    step.execute(parser_pipeline_context)
    assert len(recording_client.called_urls) == 4


# ---------------------------------------------------------------------------
# T3.5 — Document and test 404 behaviour
# ---------------------------------------------------------------------------

_HTTP_NOT_FOUND: int = 404


@pytest.mark.business_logic
def test_validation_step_documents_behaviour_on_reachable_404(
    parser_pipeline_context,
) -> None:
    """Documents ValidationStep behaviour when Artifactory returns HTTP 404.

    A 404 from a reachable Artifactory means the artifact no longer exists.
    This test pins the current behaviour (remove) so any future change is a
    deliberate, visible decision — not a silent regression.
    """
    component, pb, _ = _make_component_with_variant(build_url=UI_URL)
    parser_pipeline_context.components = [component]
    parser_pipeline_context.artifactory_client = _RecordingClient(
        status_code=_HTTP_NOT_FOUND
    )

    step = ArtifactoryValidationStep()
    step.execute(parser_pipeline_context)

    remaining_variants = [
        v
        for comp in parser_pipeline_context.components
        for rel in comp.releases
        for pb_ in rel.profile_builds
        for v in pb_.variants
    ]
    # 404 → variant removed (fail-closed for authoritative 404 responses)
    assert len(remaining_variants) == 0, "404 → variant removed (fail-closed)"


# ===========================================================================
# BL-VS-01 … BL-VS-05  — ArtifactoryValidationStep (Part 4)
# ===========================================================================

# ---------------------------------------------------------------------------
# Shared helpers for BL-VS tests
# ---------------------------------------------------------------------------

_VS_UI_URL_PREFIX: str = "http://art/ui/repos/tree/General/repo"


def _make_variant(url: str, package_id: str = "abc123") -> ConanVariant:
    """Build a minimal ConanVariant with the given build_url and package_id."""
    return ConanVariant(
        package_id=package_id,
        build_url=url,
        build_date="2024-01-01",
        options_ref="1",
    )


def _make_tree(
    url: str, package_id: str = "abc123"
) -> tuple[Component, "Release", ProfileBuild, ConanVariant]:
    """Build Component → Release → ProfileBuild → ConanVariant with the given URL."""
    from autodoc.models.release import Release

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


# ---------------------------------------------------------------------------
# BL-VS-01 — HTTP 404 removes variant from ProfileBuild.variants
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_404_removes_variant_from_profile_build(
    parser_pipeline_context,
) -> None:
    """BL-VS-01: HTTP 404 on Artifactory HEAD request removes the variant.

    Business Rule:
        When ``client.head(url)`` returns HTTP 404 the variant is definitively
        absent from Artifactory and must be removed from
        ``ProfileBuild.variants`` (fail-closed for authoritative 404).

    Preconditions:
        - One component with one ProfileBuild containing one ConanVariant with
          a valid build_url.
        - ``_RecordingClient`` returns status 404.

    Steps:
        1. Set ``ctx.components`` and ``ctx.artifactory_client``.
        2. Call ``ArtifactoryValidationStep().execute(ctx)``.

    Expected Result:
        - ``pb.variants`` is empty after the step executes.
    """
    comp, release, pb, variant = _make_tree(f"{_VS_UI_URL_PREFIX}/v1.zip")
    ctx = parser_pipeline_context
    ctx.components = [comp]
    ctx.artifactory_client = _RecordingClient(status_code=404)

    ArtifactoryValidationStep().execute(ctx)

    assert variant not in pb.variants, "404 variant must be removed"
    assert len(pb.variants) == 0


# ---------------------------------------------------------------------------
# BL-VS-02 — network error keeps variant (fail-open policy)
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_network_error_keeps_variant_fail_open(
    parser_pipeline_context,
) -> None:
    """BL-VS-02: RequestException during HEAD keeps the variant (fail-open).

    Business Rule:
        When ``client.head(url)`` raises ``requests.RequestException`` (network
        failure, timeout, etc.) Artifactory availability is unknown.  To avoid
        data loss on transient failures the variant is retained in
        ``ProfileBuild.variants`` (fail-open policy).

    Preconditions:
        - One component with one ProfileBuild containing one ConanVariant.
        - ``_RaisingClient`` raises ``RequestException`` for every request.

    Steps:
        1. Call ``ArtifactoryValidationStep().execute(ctx)``.

    Expected Result:
        - ``pb.variants`` still contains the original variant.
    """
    import requests as _requests

    class _RaisingClient:
        """Stub client that always raises RequestException."""

        def head(self, url: str) -> None:
            raise _requests.RequestException("Connection refused")

    comp, release, pb, variant = _make_tree(f"{_VS_UI_URL_PREFIX}/v1.zip")
    ctx = parser_pipeline_context
    ctx.components = [comp]
    ctx.artifactory_client = _RaisingClient()

    ArtifactoryValidationStep().execute(ctx)

    assert variant in pb.variants, "Variant must remain on network error (fail-open)"
    assert len(pb.variants) == 1


# ---------------------------------------------------------------------------
# BL-VS-03 — UI URL is converted to API URL before HEAD request
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_ui_url_converted_to_api_url_before_head(
    parser_pipeline_context,
) -> None:
    """BL-VS-03: Artifactory UI URL is transformed to API URL before HEAD.

    Business Rule:
        Variant ``build_url`` values contain the Artifactory *UI* path
        (``/ui/repos/tree/General/``).  The validation step must translate
        them to the *API* path (``/artifactory/``) before sending the HEAD
        request, because Artifactory's HEAD endpoint is only available on the
        API path.

    Preconditions:
        - ``variant.build_url = "http://art/ui/repos/tree/General/repo/pkg.zip"``
        - ``_RecordingClient`` returns HTTP 200 and records called URLs.

    Steps:
        1. Call ``ArtifactoryValidationStep().execute(ctx)``.

    Expected Result:
        - Exactly one HEAD request was made.
        - The called URL does NOT contain ``/ui/repos/tree/General/``.
        - The called URL contains ``/artifactory/``.
    """
    ui_url = "http://art/ui/repos/tree/General/repo/path/pkg.zip"
    comp, release, pb, variant = _make_tree(ui_url)
    ctx = parser_pipeline_context
    ctx.components = [comp]
    recording_client = _RecordingClient(status_code=200)
    ctx.artifactory_client = recording_client

    ArtifactoryValidationStep().execute(ctx)

    assert len(recording_client.called_urls) == 1, "Exactly one HEAD request expected"
    called = recording_client.called_urls[0]
    assert (
        "/ui/repos/tree/General/" not in called
    ), f"UI path must not appear in HEAD URL: {called}"
    assert (
        "/artifactory/" in called
    ), f"API path '/artifactory/' must appear in HEAD URL: {called}"


# ---------------------------------------------------------------------------
# BL-VS-04 — empty build_url skips HEAD check entirely
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_empty_build_url_skips_head_check(
    parser_pipeline_context,
) -> None:
    """BL-VS-04: Variant with empty build_url is not checked via HEAD.

    Business Rule:
        A ``ConanVariant`` whose ``build_url`` is an empty string has no
        Artifactory artifact to check.  The step must skip it entirely —
        neither calling ``client.head()`` nor removing the variant.

    Preconditions:
        - ``variant.build_url = ""`` (empty string).
        - ``_RecordingClient`` is used to detect any accidental HEAD calls.

    Steps:
        1. Call ``ArtifactoryValidationStep().execute(ctx)``.

    Expected Result:
        - ``client.called_urls`` is empty (HEAD was never called).
        - The variant remains in ``pb.variants``.
    """
    comp, release, pb, variant = _make_tree("")  # empty URL
    ctx = parser_pipeline_context
    ctx.components = [comp]
    recording_client = _RecordingClient(status_code=200)
    ctx.artifactory_client = recording_client

    ArtifactoryValidationStep().execute(ctx)

    assert (
        recording_client.called_urls == []
    ), "HEAD must not be called for a variant with empty build_url"
    assert variant in pb.variants, "Variant with empty build_url must not be removed"


# ---------------------------------------------------------------------------
# BL-VS-05 — ProfileBuild with all dead variants becomes empty, not removed
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_profile_build_with_all_dead_variants_becomes_empty_not_removed(
    parser_pipeline_context,
) -> None:
    """BL-VS-05: ProfileBuild whose variants all return 404 ends up with variants=[].

    Business Rule:
        ``ArtifactoryValidationStep`` only removes individual dead
        ``ConanVariant`` objects — it does NOT remove the parent
        ``ProfileBuild`` from ``Release.profile_builds``.  Removing empty
        ``ProfileBuild`` entries is the responsibility of ``FinalizeStep``,
        not ``ValidationStep``.

    Preconditions:
        - One ProfileBuild with two variants (v1, v2), both with valid URLs.
        - ``_RecordingClient`` returns HTTP 404 for every request.

    Steps:
        1. Call ``ArtifactoryValidationStep().execute(ctx)``.

    Expected Result:
        - ``pb.variants`` is ``[]`` (both variants removed).
        - ``pb`` itself remains in ``release.profile_builds`` (not removed).
    """
    from autodoc.models.release import Release

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
    ctx.artifactory_client = _RecordingClient(status_code=404)

    ArtifactoryValidationStep().execute(ctx)

    assert pb.variants == [], "All variants must be removed on 404"
    assert (
        pb in release.profile_builds
    ), "ProfileBuild must NOT be removed — that is FinalizeStep's responsibility"
    assert len(release.profile_builds) == 1
