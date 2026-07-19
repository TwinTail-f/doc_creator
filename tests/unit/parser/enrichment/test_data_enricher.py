"""
Юнит-тесты для autodoc/parser/enrichment/data_enricher.py.

Охватывает DataEnricher.apply_options(), apply_docker_links() и
apply_conan_results(). Использует фикстуры из unit/parser/conftest.py.
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
from tests.unit.parser.conftest import make_component, make_conan_variant


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


@pytest.mark.business_logic
def test_apply_options_ignores_missing_key(
    manifest_component: Component, manifest_release: Release
) -> None:
    """apply_options() с пустым options_map оставляет build_option_sets без изменений."""
    DataEnricher.apply_options([manifest_component], {})

    assert manifest_release.build_option_sets == []


@pytest.mark.business_logic
def test_apply_docker_links_creates_profile_definition() -> None:
    """apply_docker_links() добавляет новый ProfileDefinition, если его ещё нет."""
    comp, _, _ = _release(profile="hw-linux-x86_64-gcc10_2")
    docker_links = {"hw-linux-x86_64-gcc10_2": "harbor.example.com/img:tag"}
    profile_definitions: list[ProfileDefinition] = []

    DataEnricher.apply_docker_links([comp], docker_links, profile_definitions)

    assert len(profile_definitions) == 1
    assert profile_definitions[0].docker_image == "harbor.example.com/img:tag"


@pytest.mark.business_logic
def test_apply_docker_links_updates_existing_definition() -> None:
    """apply_docker_links() обновляет docker_image в существующем ProfileDefinition."""
    comp, _, _ = _release(profile="hw-linux-x86_64-gcc10_2")
    existing = ProfileDefinition(profile_name="hw-linux-x86_64-gcc10_2", docker_image="old")
    profile_definitions: list[ProfileDefinition] = [existing]
    docker_links = {"hw-linux-x86_64-gcc10_2": "harbor.example.com/img:tag"}

    DataEnricher.apply_docker_links([comp], docker_links, profile_definitions)

    assert existing.docker_image == "harbor.example.com/img:tag"
    assert len(profile_definitions) == 1  # дубликат не создаётся


@pytest.mark.business_logic
def test_apply_docker_links_profile_not_in_links_unchanged() -> None:
    """apply_docker_links() с пустым docker_links создаёт ProfileDefinition
    с пустым docker_image — профиль регистрируется, но URL не задан."""
    comp, _, _ = _release(profile="hw-linux-x86_64-gcc10_2")
    profile_definitions: list[ProfileDefinition] = []

    DataEnricher.apply_docker_links([comp], {}, profile_definitions)

    # Запись профиля всегда обновляется/вставляется; docker_image пуст, если
    # имя профиля отсутствует в docker_links.
    assert len(profile_definitions) == 1
    assert profile_definitions[0].docker_image == ""


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


@pytest.mark.business_logic
def test_apply_conan_results_upserts_conan_settings() -> None:
    """apply_conan_results() создаёт новый ProfileDefinition с conan_settings."""
    comp, rel, pb = _release(profile="hw-linux-x86_64-gcc10_2")
    result = _minimal_enrich_result(comp, rel, pb, conan_settings={"os": "Linux"})
    profile_definitions: list[ProfileDefinition] = []

    DataEnricher.apply_conan_results([comp], result, profile_definitions)

    assert len(profile_definitions) == 1
    assert profile_definitions[0].conan_settings.get("os") == "Linux"


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


@pytest.mark.business_logic
def test_apply_conan_results_missing_release_key_unchanged() -> None:
    """apply_conan_results() оставляет conan_reference пустым, если release_data не содержит совпадений."""
    comp, rel, _ = _release()
    empty_result = ConanEnrichmentResult()

    DataEnricher.apply_conan_results([comp], empty_result)

    assert rel.conan_reference == ""


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
    """Строит минимальный ``ConanEnrichmentResult`` для одной пары release/profile.

    Args:
        comp_name: Имя компонента — часть ключа в ``release_data``.
        version: Версия релиза — часть ключа.
        channel: Канал релиза — часть ключа.
        pb: ``ProfileBuild``, чей ``id()`` используется как ключ в ``profile_data``.
        exists: Существует ли данный вариант сборки в Conan.
        base_ref: Значение ``conan_reference``, записываемое в релиз.
        patches: Список патчей, привязываемых к релизу.
        dependencies: Список зависимостей, привязываемых к релизу.
        conan_settings: Словарь настроек Conan для профиля.
        variants: Список ``ConanVariant`` для профиля.

    Returns:
        ``ConanEnrichmentResult``, охватывающий ровно один релиз и один профиль.
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
    """Минимальный ``ReleaseConanData`` с пустыми необязательными полями.

    Используется в тестах, проверяющих обогащение на уровне профиля, для
    которых поля уровня релиза (patches, dependencies и т.п.) не важны.

    Returns:
        ``ReleaseConanData`` с разумными нулевыми значениями по умолчанию.
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


@pytest.mark.business_logic
def test_apply_options_creates_one_option_per_option_id() -> None:
    """Каждый ключ в options_map создаёт ровно один объект ConanInputOptions."""
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
    """Строка опции с префиксом имени пакета ('mylib:shared=True') сохраняется в parsed_options без префикса."""
    comp = make_component("mylib", "1.0", "fast")
    options_map = {("mylib", "1.0", "fast"): {"1": "mylib:shared=True"}}
    DataEnricher.apply_options([comp], options_map)

    opt = comp.releases[0].build_option_sets[0]
    assert opt.parsed_options == {"shared": "True"}
    assert "mylib:shared" not in opt.parsed_options


@pytest.mark.business_logic
def test_apply_options_does_not_mutate_other_releases() -> None:
    """apply_options() применяет опции только к релизу, указанному в ключе options_map, остальные не затрагиваются."""
    comp_a = make_component("mylib", "1.0", "fast")
    comp_b = make_component("otherlib", "2.0", "slow")
    options_map = {("mylib", "1.0", "fast"): {"1": "shared=True"}}

    DataEnricher.apply_options([comp_a, comp_b], options_map)

    assert len(comp_a.releases[0].build_option_sets) == 1
    assert comp_b.releases[0].build_option_sets == []


@pytest.mark.business_logic
def test_apply_options_all_releases_of_same_component_receive_options() -> None:
    """Каждый релиз одного компонента независимо получает свои опции из options_map."""
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
    """Повторный вызов apply_options() с тем же options_map не дублирует записи build_option_sets."""
    comp = make_component("mylib", "1.0", "fast")
    options_map = {("mylib", "1.0", "fast"): {"1": "shared=True"}}

    DataEnricher.apply_options([comp], options_map)
    DataEnricher.apply_options([comp], options_map)

    assert len(comp.releases[0].build_option_sets) == 1


@pytest.mark.business_logic
def test_apply_conan_results_conan_reference_format_no_revision_hash() -> None:
    """release.conan_reference содержит только часть name/ver@user/channel, без суффикса #rrev."""
    comp = make_component("mylib", "1.0", "fast")
    pb = comp.releases[0].profile_builds[0]
    enrich = _make_enrich_result("mylib", "1.0", "fast", pb, base_ref="mylib/1.0@user/fast")
    DataEnricher.apply_conan_results([comp], enrich)

    ref = comp.releases[0].conan_reference
    assert ref == "mylib/1.0@user/fast"
    assert "#" not in ref


@pytest.mark.business_logic
def test_apply_conan_results_multiple_profiles_each_gets_own_variants() -> None:
    """Два ProfileBuild одного релиза получают независимые списки variants с разными package_id."""
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
    """ProfileBuild, отсутствующий в profile_data результата обогащения, остаётся с exists=False."""
    comp = make_component("mylib", "1.0", "fast", profiles=["hw-linux-x86_64", "hw-linux-armv8"])
    pb1, pb2 = comp.releases[0].profile_builds

    # В profile_data присутствует только pb1; pb2 намеренно отсутствует.
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
    """release.total_option_sets заполняется, и id каждого TotalOptionsSet совпадает с id из build_option_sets."""
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
    """После обогащения release.patches и release.dependencies заполняются значениями из ReleaseConanData."""
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
    """apply_conan_results() только мутирует существующие ProfileBuild и не создаёт новые."""
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
    """Замена ProfileBuild новым объектом после построения ConanEnrichmentResult приводит к тихому пропуску обогащения (profile_data ключуется по id())."""
    comp = make_component("mylib", "1.0", "fast")
    original_pb = comp.releases[0].profile_builds[0]

    # Строим результат, используя id(original_pb).
    enrich = _make_enrich_result("mylib", "1.0", "fast", original_pb, exists=True)

    # Заменяем объект ПОСЛЕ построения результата — id() больше не совпадёт.
    new_pb = ProfileBuild(profile_name=original_pb.profile_name)
    comp.releases[0].profile_builds[0] = new_pb

    DataEnricher.apply_conan_results([comp], enrich)

    # new_pb не получает данных, так как id(new_pb) != id(original_pb).
    assert new_pb.exists is False
    assert new_pb.variants == []


@pytest.mark.business_logic
def test_apply_docker_links_matches_profile_by_name_exact() -> None:
    """Docker-образ привязывается к ProfileDefinition только при точном совпадении имени профиля с ключом docker_links."""
    comp = make_component("mylib", profiles=["hw-linux-x86_64"])
    pd = ProfileDefinition(profile_name="hw-linux-x86_64", docker_image="")
    docker_links = {"hw-linux-x86_64": "harbor.example.com/img:tag"}

    DataEnricher.apply_docker_links([comp], docker_links, [pd])

    assert pd.docker_image == "harbor.example.com/img:tag"


@pytest.mark.business_logic
def test_apply_docker_links_partial_match_does_not_apply() -> None:
    """Частичное (более короткое) совпадение имени профиля с ключом docker_links не приводит к привязке образа."""
    comp = make_component("mylib", profiles=["hw-linux-x86_64-gcc10_2"])
    pd = ProfileDefinition(profile_name="hw-linux-x86_64-gcc10_2", docker_image="")
    # docker_links содержит НЕ точное (более короткое) имя — совпадения быть не должно.
    docker_links = {"hw-linux-x86_64": "harbor.example.com/img:tag"}

    DataEnricher.apply_docker_links([comp], docker_links, [pd])

    assert pd.docker_image == ""


@pytest.mark.business_logic
def test_apply_docker_links_empty_docker_image_preserved_when_no_match() -> None:
    """Отсутствие имени профиля в docker_links оставляет docker_image пустой строкой, а не None."""
    comp = make_component("mylib", profiles=["hw-linux-x86_64"])
    pd = ProfileDefinition(profile_name="hw-linux-x86_64", docker_image="")
    docker_links: dict[str, str] = {}  # Пусто — совпадение невозможно.

    DataEnricher.apply_docker_links([comp], docker_links, [pd])

    assert pd.docker_image == ""


@pytest.mark.business_logic
def test_apply_docker_links_profile_definitions_none_skips_upsert() -> None:
    """При profile_definitions=None (по умолчанию) apply_docker_links() не пытается
    создавать или обновлять ProfileDefinition — ветка upsert выполняется только
    когда список explicit передан вызывающим кодом."""
    comp = make_component("mylib", profiles=["hw-linux-x86_64"])
    docker_links = {"hw-linux-x86_64": "harbor.example.com/img:tag"}

    # Не должно бросать исключение и не должно требовать список.
    DataEnricher.apply_docker_links([comp], docker_links, profile_definitions=None)


@pytest.mark.business_logic
def test_apply_docker_links_multiple_components_same_profile() -> None:
    """Одна запись docker_links применяется ко всем компонентам, использующим общий профиль."""
    comp_a = make_component("mylib", profiles=["hw-linux-x86_64"])
    comp_b = make_component("otherlib", profiles=["hw-linux-x86_64"])
    pd = ProfileDefinition(profile_name="hw-linux-x86_64", docker_image="")
    docker_links = {"hw-linux-x86_64": "harbor.example.com/img:tag"}

    DataEnricher.apply_docker_links([comp_a, comp_b], docker_links, [pd])

    assert pd.docker_image == "harbor.example.com/img:tag"
