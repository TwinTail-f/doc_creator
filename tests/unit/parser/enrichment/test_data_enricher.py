"""
Юнит-тесты для autodoc/parser/enrichment/data_enricher.py.

Охватывает DataEnricher.apply_options(), apply_docker_links() и
apply_conan_results(). Использует фикстуры из unit/parser/conftest.py там,
где доступны; фикстуры уровня компонента строятся инлайн для ясности.
"""

import pytest

from autodoc.models.component import Component
from autodoc.models.conan_variant import ConanVariant, ProfileBuild
from autodoc.models.options import ConanInputOptions, TotalOptionsSet
from autodoc.models.profile_definition import ProfileDefinition
from autodoc.models.release import Release
from autodoc.parser.conan.models.conan_enrichment_result import (
    ConanEnrichmentResult,
    ProfileConanData,
    ReleaseConanData,
)
from autodoc.parser.enrichment.data_enricher import DataEnricher

# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


def _release(
    name: str = "openssl",
    version: str = "1.0.0",
    channel: str = "tech",
    profile: str = "hw-linux-x86_64-gcc10_2",
) -> tuple[Component, Release, ProfileBuild]:
    """Возвращает тройку (Component, Release, ProfileBuild) для тестов обогащения."""
    pb = ProfileBuild(profile_name=profile)
    rel = Release(
        version=version,
        platform="2.0",
        channel=channel,
        profile_builds=[pb],
    )
    comp = Component(name=name, releases=[rel])
    return comp, rel, pb


def _minimal_enrich_result(
    comp: Component,
    release: Release,
    pb: ProfileBuild,
    base_ref: str = "",
    conan_settings: dict | None = None,
    variants: list[ConanVariant] | None = None,
    exists: bool = True,
) -> ConanEnrichmentResult:
    """Строит ConanEnrichmentResult, охватывающий заданный component/release/pb."""
    result = ConanEnrichmentResult()
    key = (comp.name, release.version, release.channel)
    result.release_data[key] = ReleaseConanData(
        base_ref=base_ref or f"{comp.name}/{release.version}@platform-2.0/{release.channel}",
        rrev="abc123",
        full_version=release.version,
        default_options=[],
        total_options=[],
        patches=[],
        dependencies=[],
        artifactory_url="",
    )
    result.profile_data[id(pb)] = ProfileConanData(
        conan_settings=conan_settings or {},
        exists=exists,
        variants=variants or [],
    )
    return result


# ---------------------------------------------------------------------------
# apply_options
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_apply_options_sets_build_option_sets(
    manifest_component: Component, manifest_release: Release
) -> None:
    """apply_options() устанавливает build_option_sets."""
    key = ("openssl", manifest_release.version, manifest_release.channel)
    options_map = {key: {"1": "shared=True"}}

    DataEnricher.apply_options([manifest_component], options_map)

    assert len(manifest_release.build_option_sets) == 1
    assert manifest_release.build_option_sets[0].id == "1"
    assert manifest_release.build_option_sets[0].options == "shared=True"


# ---------------------------------------------------------------------------
# apply_options: пустой options_map
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_apply_options_ignores_missing_key(
    manifest_component: Component, manifest_release: Release
) -> None:
    """apply_options() с пустым options_map оставляет build_option_sets без изменений."""
    DataEnricher.apply_options([manifest_component], {})

    assert manifest_release.build_option_sets == []


# ---------------------------------------------------------------------------
# apply_options: два набора опций
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_apply_options_multiple_sets(
    manifest_component: Component, manifest_release: Release
) -> None:
    """apply_options() с двумя наборами опций создаёт две записи ConanInputOptions."""
    key = ("openssl", manifest_release.version, manifest_release.channel)
    options_map = {key: {"1": "shared=True", "2": "shared=False"}}

    DataEnricher.apply_options([manifest_component], options_map)

    assert len(manifest_release.build_option_sets) == 2


# ---------------------------------------------------------------------------
# apply_docker_links: создание нового ProfileDefinition
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_apply_docker_links_creates_profile_definition() -> None:
    """apply_docker_links() добавляет новый ProfileDefinition, если его ещё нет."""
    comp, rel, pb = _release(profile="hw-linux-x86_64-gcc10_2")
    docker_links = {"hw-linux-x86_64-gcc10_2": "harbor.example.com/img:tag"}
    profile_definitions: list[ProfileDefinition] = []

    DataEnricher.apply_docker_links([comp], docker_links, profile_definitions)

    assert len(profile_definitions) == 1
    assert profile_definitions[0].docker_image == "harbor.example.com/img:tag"


# ---------------------------------------------------------------------------
# apply_docker_links: обновление существующего ProfileDefinition
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_apply_docker_links_updates_existing_definition() -> None:
    """apply_docker_links() обновляет docker_image в существующем ProfileDefinition."""
    comp, rel, pb = _release(profile="hw-linux-x86_64-gcc10_2")
    existing = ProfileDefinition(profile_name="hw-linux-x86_64-gcc10_2", docker_image="old")
    profile_definitions: list[ProfileDefinition] = [existing]
    docker_links = {"hw-linux-x86_64-gcc10_2": "harbor.example.com/img:tag"}

    DataEnricher.apply_docker_links([comp], docker_links, profile_definitions)

    assert existing.docker_image == "harbor.example.com/img:tag"
    assert len(profile_definitions) == 1  # дубликат не создаётся


# ---------------------------------------------------------------------------
# apply_docker_links: пустой docker_links
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_apply_docker_links_profile_not_in_links_unchanged() -> None:
    """apply_docker_links() с пустым docker_links создаёт ProfileDefinition
    с пустым docker_image — профиль регистрируется, но URL не задан."""
    comp, rel, pb = _release(profile="hw-linux-x86_64-gcc10_2")
    profile_definitions: list[ProfileDefinition] = []

    DataEnricher.apply_docker_links([comp], {}, profile_definitions)

    # Запись профиля всегда обновляется/вставляется; docker_image пуст, если
    # имя профиля отсутствует в docker_links.
    assert len(profile_definitions) == 1
    assert profile_definitions[0].docker_image == ""


# ---------------------------------------------------------------------------
# apply_conan_results: запись base_ref в conan_reference
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_apply_conan_results_sets_conan_reference() -> None:
    """apply_conan_results() записывает base_ref в release.conan_reference."""
    comp, rel, pb = _release()
    expected_ref = "openssl/3.0@platform-2.0/tech"
    result = _minimal_enrich_result(comp, rel, pb, base_ref=expected_ref)

    DataEnricher.apply_conan_results([comp], result)

    assert rel.conan_reference == expected_ref


# ---------------------------------------------------------------------------
# apply_conan_results: pb.exists=True и pb.variants заполнены
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_apply_conan_results_sets_profile_build_exists_and_variants(
    conan_variant: ConanVariant,
) -> None:
    """apply_conan_results() устанавливает pb.exists=True и заполняет pb.variants."""
    comp, rel, pb = _release()
    result = _minimal_enrich_result(comp, rel, pb, exists=True, variants=[conan_variant])

    DataEnricher.apply_conan_results([comp], result)

    assert pb.exists is True
    assert len(pb.variants) == 1


# ---------------------------------------------------------------------------
# apply_conan_results: создание нового ProfileDefinition с conan_settings
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_apply_conan_results_upserts_conan_settings() -> None:
    """apply_conan_results() создаёт новый ProfileDefinition с conan_settings."""
    comp, rel, pb = _release(profile="hw-linux-x86_64-gcc10_2")
    result = _minimal_enrich_result(comp, rel, pb, conan_settings={"os": "Linux"})
    profile_definitions: list[ProfileDefinition] = []

    DataEnricher.apply_conan_results([comp], result, profile_definitions)

    assert len(profile_definitions) == 1
    assert profile_definitions[0].conan_settings.get("os") == "Linux"


# ---------------------------------------------------------------------------
# apply_conan_results: непустые conan_settings не стираются пустыми данными
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_apply_conan_results_does_not_overwrite_with_empty_settings() -> None:
    """Непустые conan_settings в существующем ProfileDefinition не стираются пустыми данными."""
    comp, rel, pb = _release(profile="hw-linux-x86_64-gcc10_2")
    existing_pd = ProfileDefinition(
        profile_name="hw-linux-x86_64-gcc10_2",
        conan_settings={"os": "Linux"},
    )
    # Новый profile_data содержит пустые conan_settings
    result = _minimal_enrich_result(comp, rel, pb, conan_settings={})
    profile_definitions: list[ProfileDefinition] = [existing_pd]

    DataEnricher.apply_conan_results([comp], result, profile_definitions)

    assert existing_pd.conan_settings == {"os": "Linux"}


# ---------------------------------------------------------------------------
# apply_conan_results: conan_reference пуст при отсутствии совпадений
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_apply_conan_results_missing_release_key_unchanged() -> None:
    """apply_conan_results() оставляет conan_reference пустым, если release_data не содержит совпадений."""
    comp, rel, pb = _release()
    empty_result = ConanEnrichmentResult()

    DataEnricher.apply_conan_results([comp], empty_result)

    assert rel.conan_reference == ""


# ===========================================================================
# Factories & helpers — Part-1 additions (BL-DE-01 … BL-DE-16)
# ===========================================================================
#
# make_component / make_conan_variant are canonical factories defined in
# tests/unit/parser/conftest.py.  NULL_PACKAGE_ID is also defined there.
# We import them explicitly so these tests remain self-contained and
# easy to read without implicit pytest fixture magic.

from tests.unit.parser.conftest import (  # noqa: E402
    make_component,
    make_conan_variant,
    NULL_PACKAGE_ID,
)


def _make_enrich_result(
    comp_name: str,
    version: str,
    channel: str,
    pb: "ProfileBuild",
    exists: bool = True,
    base_ref: str = "mylib/1.0@user/fast",
    patches: list[str] | None = None,
    dependencies: list[str] | None = None,
    conan_settings: dict | None = None,
    variants: "list[ConanVariant] | None" = None,
) -> "ConanEnrichmentResult":
    """Построить минимальный ``ConanEnrichmentResult`` for a single release/profile pair.

    Business Rule: helper factory — no business rule of its own.

    Args:
        comp_name: Component name key used in ``release_data``.
        version: Release version key.
        channel: Release channel key.
        pb: The ``ProfileBuild`` whose ``id()`` is used as the ``profile_data`` key.
        exists: Whether the profile build exists in Conan.
        base_ref: ``conan_reference`` value written to the release.
        patches: Patch list attached to the release.
        dependencies: Dependency list attached to the release.
        conan_settings: Conan settings dict for the profile.
        variants: ``ConanVariant`` list for the profile.

    Returns:
        A ``ConanEnrichmentResult`` covering exactly one release and one profile.
    """
    profile_data_obj = ProfileConanData(
        conan_settings=conan_settings or {},
        exists=exists,
        variants=variants if variants is not None else [make_conan_variant()],
    )
    release_data_obj = ReleaseConanData(
        base_ref=base_ref,
        rrev="abc",
        full_version=f"{comp_name}/{version}@user/{channel}#abc",
        default_options=[],
        total_options=[TotalOptionsSet(id="1", options={})],
        patches=patches or [],
        dependencies=dependencies or [],
        artifactory_url="http://art/pkg",
    )
    return ConanEnrichmentResult(
        release_data={(comp_name, version, channel): release_data_obj},
        profile_data={id(pb): profile_data_obj},
    )


def _minimal_release_data() -> "ReleaseConanData":
    """Minimal ``ReleaseConanData`` with empty optional fields.

    Used in tests that exercise profile-level enrichment but do not care
    about release-level fields (patches, dependencies, etc.).

    Returns:
        A ``ReleaseConanData`` with sensible zero-value defaults.
    """
    return ReleaseConanData(
        base_ref="mylib/1.0@user/fast",
        rrev="r",
        full_version="mylib/1.0@user/fast#r",
        default_options=[],
        total_options=[],
        patches=[],
        dependencies=[],
        artifactory_url="http://art/pkg",
    )


# ===========================================================================
# Section 1 — DataEnricher.apply_options (BL-DE-01 … BL-DE-05)
# ===========================================================================


@pytest.mark.business_logic
def test_apply_options_creates_one_option_per_option_id() -> None:
    """Verify that each key in ``options_map`` creates exactly one ``ConanInputOptions``.

    Business Rule (BL-DE-01): Two option-set keys ``"1"`` and ``"2"`` in the
    ``options_map`` dict must produce exactly two ``ConanInputOptions`` objects
    attached to ``release.build_option_sets``, one per key.

    Preconditions:
        - Component ``mylib`` with one release (version=``"1.0"``, channel=``"fast"``).
        - ``options_map`` contains two nested keys for this release.

    Steps:
        1. Create component via ``make_component("mylib", "1.0", "fast")``.
        2. Prepare ``options_map = {("mylib","1.0","fast"): {"1":"shared=True","2":"shared=False"}}``.
        3. Call ``DataEnricher.apply_options([comp], options_map)``.
        4. Inspect ``release.build_option_sets``.

    Expected Result:
        - ``len(release.build_option_sets) == 2``.
        - The set of ``opt.id`` values equals ``{"1","2"}``.
        - The object with ``id="1"`` has ``options="shared=True"``.
    """
    comp = make_component("mylib", "1.0", "fast")
    release = comp.releases[0]
    options_map = {("mylib", "1.0", "fast"): {"1": "shared=True", "2": "shared=False"}}
    DataEnricher.apply_options([comp], options_map)

    assert len(release.build_option_sets) == 2
    ids = {opt.id for opt in release.build_option_sets}
    assert ids == {"1", "2"}
    opt1 = next(o for o in release.build_option_sets if o.id == "1")
    assert opt1.options == "shared=True"


@pytest.mark.business_logic
def test_apply_options_parsed_options_strip_package_prefix() -> None:
    """Verify that ``parsed_options`` strips the package-name prefix from option strings.

    Business Rule (BL-DE-02): An option string containing an explicit package
    prefix (``"mylib:shared=True"``) must be stored in ``parsed_options`` as
    ``{"shared": "True"}`` — without the ``"mylib:"`` prefix.

    Preconditions:
        - Options string contains an explicit package prefix ``"mylib:shared=True"``.

    Steps:
        1. Create component ``make_component("mylib", "1.0", "fast")``.
        2. ``options_map = {("mylib","1.0","fast"): {"1":"mylib:shared=True"}}``.
        3. ``DataEnricher.apply_options([comp], options_map)``.
        4. Retrieve the created ``ConanInputOptions`` with ``id="1"``.

    Expected Result:
        - ``opt.parsed_options == {"shared": "True"}``.
        - Key ``"mylib:shared"`` is absent from ``opt.parsed_options``.
    """
    comp = make_component("mylib", "1.0", "fast")
    options_map = {("mylib", "1.0", "fast"): {"1": "mylib:shared=True"}}
    DataEnricher.apply_options([comp], options_map)

    opt = comp.releases[0].build_option_sets[0]
    assert opt.parsed_options == {"shared": "True"}
    assert "mylib:shared" not in opt.parsed_options


@pytest.mark.business_logic
def test_apply_options_does_not_mutate_other_releases() -> None:
    """Verify that options are applied only to the matching release.

    Business Rule (BL-DE-03): When ``options_map`` contains a key for only one
    ``(component, version, channel)`` triple, all other releases — of the same
    or different components — must remain untouched (``build_option_sets == []``).

    Preconditions:
        - Component A (``mylib/1.0/fast``) — present in ``options_map``.
        - Component B (``otherlib/2.0/slow``) — absent from ``options_map``.

    Steps:
        1. ``comp_a = make_component("mylib", "1.0", "fast")``.
        2. ``comp_b = make_component("otherlib", "2.0", "slow")``.
        3. ``options_map = {("mylib","1.0","fast"): {"1":"shared=True"}}``.
        4. ``DataEnricher.apply_options([comp_a, comp_b], options_map)``.

    Expected Result:
        - ``comp_a.releases[0].build_option_sets`` has 1 element.
        - ``comp_b.releases[0].build_option_sets == []``.
    """
    comp_a = make_component("mylib", "1.0", "fast")
    comp_b = make_component("otherlib", "2.0", "slow")
    options_map = {("mylib", "1.0", "fast"): {"1": "shared=True"}}

    DataEnricher.apply_options([comp_a, comp_b], options_map)

    assert len(comp_a.releases[0].build_option_sets) == 1
    assert comp_b.releases[0].build_option_sets == []


@pytest.mark.business_logic
def test_apply_options_all_releases_of_same_component_receive_options() -> None:
    """Verify that multiple releases of one component each receive their own options.

    Business Rule (BL-DE-04): All releases of a component (different
    versions/channels) independently receive options from ``options_map`` when
    the corresponding key is present for each release.

    Preconditions:
        - One component with two releases: ``(mylib, 1.0, fast)`` and
          ``(mylib, 1.1, fast)``.
        - Both keys are present in ``options_map``.

    Steps:
        1. Build a component with two releases manually.
        2. Prepare ``options_map`` with keys for both releases.
        3. Call ``DataEnricher.apply_options([comp], options_map)``.

    Expected Result:
        - ``rel_10.build_option_sets`` has 1 element with ``options="shared=True"``.
        - ``rel_11.build_option_sets`` has 1 element with ``options="shared=False"``.
    """
    pb = ProfileBuild(profile_name="hw-linux-x86_64")
    rel_10 = Release(
        version="1.0",
        platform="2.2",
        channel="fast",
        conan_reference="",
        artifactory_url="",
        profile_builds=[pb],
    )
    pb2 = ProfileBuild(profile_name="hw-linux-x86_64")
    rel_11 = Release(
        version="1.1",
        platform="2.2",
        channel="fast",
        conan_reference="",
        artifactory_url="",
        profile_builds=[pb2],
    )
    comp = Component(
        name="mylib",
        description="",
        git_project="P",
        git_repo="r",
        git_url="",
        is_header_only=False,
        releases=[rel_10, rel_11],
    )
    options_map = {
        ("mylib", "1.0", "fast"): {"1": "shared=True"},
        ("mylib", "1.1", "fast"): {"1": "shared=False"},
    }
    DataEnricher.apply_options([comp], options_map)

    assert len(rel_10.build_option_sets) == 1
    assert len(rel_11.build_option_sets) == 1
    assert rel_10.build_option_sets[0].options == "shared=True"
    assert rel_11.build_option_sets[0].options == "shared=False"


@pytest.mark.business_logic
def test_apply_options_replaces_build_option_sets_idempotently() -> None:
    """Verify that repeated calls to ``apply_options`` do not duplicate option sets.

    Business Rule (BL-DE-05): Calling ``apply_options`` twice with the same
    ``options_map`` must NOT append duplicates to ``build_option_sets``; the
    list is replaced wholesale on each call.

    Preconditions:
        - Component with one release, ``options_map`` with one key.

    Steps:
        1. ``comp = make_component("mylib", "1.0", "fast")``.
        2. Prepare ``options_map``.
        3. Call ``DataEnricher.apply_options([comp], options_map)`` twice.

    Expected Result:
        - After two calls, ``len(release.build_option_sets) == 1``, not 2.
    """
    comp = make_component("mylib", "1.0", "fast")
    options_map = {("mylib", "1.0", "fast"): {"1": "shared=True"}}

    DataEnricher.apply_options([comp], options_map)
    DataEnricher.apply_options([comp], options_map)

    assert len(comp.releases[0].build_option_sets) == 1


# ===========================================================================
# Section 2 — DataEnricher.apply_conan_results (BL-DE-06 … BL-DE-12)
# ===========================================================================


@pytest.mark.business_logic
def test_apply_conan_results_conan_reference_format_no_revision_hash() -> None:
    """Verify that ``release.conan_reference`` contains no ``#rrev`` suffix.

    Business Rule (BL-DE-06): After enrichment, ``release.conan_reference``
    holds only the ``name/ver@user/channel`` portion of the reference —
    the ``#rrev`` hash is NOT included.

    Steps:
        1. Create component ``mylib/1.0/fast`` with one ``ProfileBuild``.
        2. Build ``ConanEnrichmentResult`` with ``base_ref="mylib/1.0@user/fast"``.
        3. Call ``DataEnricher.apply_conan_results([comp], enrich)``.

    Expected Result:
        - ``release.conan_reference == "mylib/1.0@user/fast"``.
        - The ``"#"`` character is absent from the reference.
    """
    comp = make_component("mylib", "1.0", "fast")
    pb = comp.releases[0].profile_builds[0]
    enrich = _make_enrich_result("mylib", "1.0", "fast", pb, base_ref="mylib/1.0@user/fast")
    DataEnricher.apply_conan_results([comp], enrich)

    ref = comp.releases[0].conan_reference
    assert ref == "mylib/1.0@user/fast"
    assert "#" not in ref


@pytest.mark.business_logic
def test_apply_conan_results_multiple_profiles_each_gets_own_variants() -> None:
    """Verify that two ProfileBuilds receive independent variant lists.

    Business Rule (BL-DE-07): Two ``ProfileBuild`` objects in the same release
    must each receive their own ``variants`` list — the lists must not be the
    same object, and the ``package_id`` values must differ accordingly.

    Preconditions:
        - Two profiles: ``"hw-linux-x86_64"`` and ``"hw-linux-armv8"``.
        - Each receives its own ``ProfileConanData`` with a unique ``package_id``.

    Expected Result:
        - ``pb1.variants[0].package_id == "aaa111"``.
        - ``pb2.variants[0].package_id == "bbb222"``.
        - ``pb1.variants is not pb2.variants`` (different list objects).
    """
    comp = make_component("mylib", "1.0", "fast", profiles=["hw-linux-x86_64", "hw-linux-armv8"])
    pb1, pb2 = comp.releases[0].profile_builds

    variant1 = make_conan_variant(package_id="aaa111")
    variant2 = make_conan_variant(package_id="bbb222")

    enrich = ConanEnrichmentResult(
        release_data={
            ("mylib", "1.0", "fast"): ReleaseConanData(
                base_ref="mylib/1.0@user/fast",
                rrev="r",
                full_version="mylib/1.0@user/fast#r",
                default_options=[],
                total_options=[],
                patches=[],
                dependencies=[],
                artifactory_url="http://art/pkg",
            )
        },
        profile_data={
            id(pb1): ProfileConanData(conan_settings={}, exists=True, variants=[variant1]),
            id(pb2): ProfileConanData(conan_settings={}, exists=True, variants=[variant2]),
        },
    )
    DataEnricher.apply_conan_results([comp], enrich)

    assert pb1.variants[0].package_id == "aaa111"
    assert pb2.variants[0].package_id == "bbb222"
    assert pb1.variants is not pb2.variants


@pytest.mark.business_logic
def test_apply_conan_results_exists_false_when_profile_not_in_enrichment() -> None:
    """Verify that a ProfileBuild absent from the enrichment result stays unenriched.

    Business Rule (BL-DE-08): A ``ProfileBuild`` whose ``id()`` is missing from
    ``ConanEnrichmentResult.profile_data`` retains ``exists=False`` and an
    empty ``variants`` list — the enricher silently skips it.

    Preconditions:
        - Two profiles, but ``ConanEnrichmentResult`` contains data for only one.

    Expected Result:
        - ``pb1.exists is True`` (enriched).
        - ``pb2.exists is False`` (not enriched — retains skeleton state).
        - ``pb2.variants == []``.
    """
    comp = make_component("mylib", "1.0", "fast", profiles=["hw-linux-x86_64", "hw-linux-armv8"])
    pb1, pb2 = comp.releases[0].profile_builds

    # Only pb1 in profile_data; pb2 is intentionally missing.
    enrich = ConanEnrichmentResult(
        release_data={("mylib", "1.0", "fast"): _minimal_release_data()},
        profile_data={
            id(pb1): ProfileConanData(
                conan_settings={},
                exists=True,
                variants=[make_conan_variant()],
            ),
        },
    )
    DataEnricher.apply_conan_results([comp], enrich)

    assert pb1.exists is True
    assert pb2.exists is False
    assert pb2.variants == []


@pytest.mark.business_logic
def test_apply_conan_results_total_option_sets_linked_by_id() -> None:
    """Verify that ``release.total_option_sets`` is populated with matching IDs.

    Business Rule (BL-DE-09): After enrichment the release carries
    ``total_option_sets``, and each ``TotalOptionsSet.id`` must match the
    corresponding ``ConanInputOptions.id`` from ``build_option_sets``.

    Expected Result:
        - ``release.total_option_sets`` contains one element with ``id="1"``.
        - ``TotalOptionsSet.options == {"shared": "True"}``.
    """
    comp = make_component("mylib", "1.0", "fast")
    release = comp.releases[0]
    release.build_option_sets = [ConanInputOptions(id="1", options="shared=True")]

    pb = release.profile_builds[0]
    enrich = ConanEnrichmentResult(
        release_data={
            ("mylib", "1.0", "fast"): ReleaseConanData(
                base_ref="mylib/1.0@user/fast",
                rrev="r",
                full_version="mylib/1.0@user/fast#r",
                default_options=[],
                total_options=[TotalOptionsSet(id="1", options={"shared": "True"})],
                patches=[],
                dependencies=[],
                artifactory_url="http://art/pkg",
            )
        },
        profile_data={
            id(pb): ProfileConanData(
                conan_settings={}, exists=True, variants=[make_conan_variant()]
            )
        },
    )
    DataEnricher.apply_conan_results([comp], enrich)

    assert len(release.total_option_sets) == 1
    assert release.total_option_sets[0].id == "1"
    assert release.total_option_sets[0].options == {"shared": "True"}


@pytest.mark.business_logic
def test_apply_conan_results_patches_and_dependencies_applied() -> None:
    """Verify that ``release.patches`` and ``release.dependencies`` are populated.

    Business Rule (BL-DE-10): After enrichment, ``release.patches`` and
    ``release.dependencies`` reflect the values from ``ReleaseConanData`` —
    they are not left as empty lists.

    Expected Result:
        - ``release.patches == ["fix-alpine.patch"]``.
        - ``release.dependencies == ["tcl"]``.
    """
    comp = make_component("mylib", "1.0", "fast")
    pb = comp.releases[0].profile_builds[0]
    enrich = _make_enrich_result(
        "mylib",
        "1.0",
        "fast",
        pb,
        patches=["fix-alpine.patch"],
        dependencies=["tcl"],
    )
    DataEnricher.apply_conan_results([comp], enrich)

    assert comp.releases[0].patches == ["fix-alpine.patch"]
    assert comp.releases[0].dependencies == ["tcl"]


@pytest.mark.business_logic
def test_apply_conan_results_does_not_create_new_profile_builds() -> None:
    """Verify that ``apply_conan_results`` mutates existing ProfileBuilds only.

    Business Rule (BL-DE-11): The enricher must not create new ``ProfileBuild``
    objects — it only mutates existing ones in-place.  The length of
    ``release.profile_builds`` must not increase.

    Steps:
        1. Record ``id(pb)`` and ``len(profile_builds)`` before enrichment.
        2. Run ``DataEnricher.apply_conan_results([comp], enrich)``.
        3. Verify object identity and list length are unchanged.

    Expected Result:
        - ``count_before == count_after == 1``.
        - ``id(profile_builds[0])`` remains the same object.
    """
    comp = make_component("mylib", "1.0", "fast", profiles=["hw-linux-x86_64"])
    pb = comp.releases[0].profile_builds[0]
    original_id = id(pb)
    count_before = len(comp.releases[0].profile_builds)

    enrich = _make_enrich_result("mylib", "1.0", "fast", pb)
    DataEnricher.apply_conan_results([comp], enrich)

    count_after = len(comp.releases[0].profile_builds)
    assert count_before == count_after == 1
    assert id(comp.releases[0].profile_builds[0]) == original_id


@pytest.mark.business_logic
def test_apply_conan_results_profile_data_keyed_by_object_identity() -> None:
    """Document that replacing a ProfileBuild after building the EnrichmentResult silently skips enrichment.

    Business Rule (BL-DE-12): ``ConanEnrichmentResult.profile_data`` is keyed
    by ``id(pb)`` (Python object identity).  If the ``ProfileBuild`` is replaced
    with a new object after the result is built, the new object's ``id()`` will
    not match any key — enrichment is silently skipped.

    This test documents a dangerous coupling pattern that callers must avoid.

    Expected Result:
        - ``new_pb.exists is False`` (not enriched — id mismatch).
        - ``new_pb.variants == []``.
    """
    comp = make_component("mylib", "1.0", "fast")
    original_pb = comp.releases[0].profile_builds[0]

    # Build result using id(original_pb).
    enrich = _make_enrich_result("mylib", "1.0", "fast", original_pb, exists=True)

    # Replace the object AFTER building the result — id() will no longer match.
    new_pb = ProfileBuild(profile_name=original_pb.profile_name)
    comp.releases[0].profile_builds[0] = new_pb

    DataEnricher.apply_conan_results([comp], enrich)

    # new_pb receives no data because id(new_pb) != id(original_pb).
    assert new_pb.exists is False
    assert new_pb.variants == []


# ===========================================================================
# Section 3 — DataEnricher.apply_docker_links (BL-DE-13 … BL-DE-16)
# ===========================================================================


@pytest.mark.business_logic
def test_apply_docker_links_matches_profile_by_name_exact() -> None:
    """Verify that Docker image binding uses exact profile-name matching.

    Business Rule (BL-DE-13): A ``ProfileDefinition`` is updated with a Docker
    image URL only when its ``profile_name`` is an exact key in ``docker_links``.
    No prefix or substring matching occurs.

    Steps:
        1. Create component with profile ``"hw-linux-x86_64"``.
        2. Create ``ProfileDefinition(profile_name="hw-linux-x86_64", docker_image="")``.
        3. ``docker_links = {"hw-linux-x86_64": "harbor.example.com/img:tag"}``.
        4. Call ``DataEnricher.apply_docker_links([comp], docker_links, [pd])``.

    Expected Result:
        - ``pd.docker_image == "harbor.example.com/img:tag"``.
    """
    comp = make_component("mylib", profiles=["hw-linux-x86_64"])
    pd = ProfileDefinition(profile_name="hw-linux-x86_64", docker_image="")
    docker_links = {"hw-linux-x86_64": "harbor.example.com/img:tag"}

    DataEnricher.apply_docker_links([comp], docker_links, [pd])

    assert pd.docker_image == "harbor.example.com/img:tag"


@pytest.mark.business_logic
def test_apply_docker_links_partial_match_does_not_apply() -> None:
    """Verify that a partial profile-name match does NOT trigger Docker binding.

    Business Rule (BL-DE-14): If ``docker_links`` contains only a shorter key
    (e.g. ``"hw-linux-x86_64"``) and the ``ProfileDefinition`` has a longer
    name (e.g. ``"hw-linux-x86_64-gcc10_2"``), the binding must NOT occur.

    Preconditions:
        - ``ProfileDefinition`` with name ``"hw-linux-x86_64-gcc10_2"``.
        - ``docker_links`` contains only the short key ``"hw-linux-x86_64"``.

    Expected Result:
        - ``pd.docker_image`` remains ``""``.
    """
    comp = make_component("mylib", profiles=["hw-linux-x86_64-gcc10_2"])
    pd = ProfileDefinition(profile_name="hw-linux-x86_64-gcc10_2", docker_image="")
    # docker_links contains a NON-exact (shorter) name — must not match.
    docker_links = {"hw-linux-x86_64": "harbor.example.com/img:tag"}

    DataEnricher.apply_docker_links([comp], docker_links, [pd])

    assert pd.docker_image == ""


@pytest.mark.business_logic
def test_apply_docker_links_empty_docker_image_preserved_when_no_match() -> None:
    """Verify that a missing profile key leaves docker_image as empty string (not None).

    Business Rule (BL-DE-15): When the profile name is absent from
    ``docker_links``, ``ProfileDefinition.docker_image`` must remain ``""``
    and must never become ``None``.

    Expected Result:
        - ``pd.docker_image == ""``.
        - ``pd.docker_image is not None``.
    """
    comp = make_component("mylib", profiles=["hw-linux-x86_64"])
    pd = ProfileDefinition(profile_name="hw-linux-x86_64", docker_image="")
    docker_links: dict[str, str] = {}  # Empty — no match possible.

    DataEnricher.apply_docker_links([comp], docker_links, [pd])

    assert pd.docker_image == ""
    assert pd.docker_image is not None


@pytest.mark.business_logic
def test_apply_docker_links_multiple_components_same_profile() -> None:
    """Verify that a single docker_links entry applies across multiple components sharing a profile.

    Business Rule (BL-DE-16): When two or more components share the same
    profile name, one call to ``apply_docker_links`` with a shared
    ``ProfileDefinition`` must update that definition regardless of which
    component is iterated first.

    Preconditions:
        - Two components both using profile ``"hw-linux-x86_64"``.
        - One shared ``ProfileDefinition`` for this profile.

    Expected Result:
        - ``pd.docker_image == "harbor.example.com/img:tag"`` after the call.
        - No exceptions are raised when passing a list of two components.
    """
    comp_a = make_component("mylib", profiles=["hw-linux-x86_64"])
    comp_b = make_component("otherlib", profiles=["hw-linux-x86_64"])
    pd = ProfileDefinition(profile_name="hw-linux-x86_64", docker_image="")
    docker_links = {"hw-linux-x86_64": "harbor.example.com/img:tag"}

    DataEnricher.apply_docker_links([comp_a, comp_b], docker_links, [pd])

    assert pd.docker_image == "harbor.example.com/img:tag"
