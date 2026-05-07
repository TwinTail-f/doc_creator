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
        git_url="DEP_Components/_git/contrib_openssl",
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
        base_ref=base_ref
        or f"{comp.name}/{release.version}@platform-2.0/{release.channel}",
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


def test_apply_options_sets_build_option_sets(
    manifest_component: Component, manifest_release: Release
) -> None:
    """apply_options() устанавливает _build_option_sets_internal и build_option_sets."""
    key = ("openssl", manifest_release.version, manifest_release.channel)
    options_map = {key: {"1": "shared=True"}}

    DataEnricher.apply_options([manifest_component], options_map)

    assert manifest_release._build_option_sets_internal == {"1": "shared=True"}
    assert len(manifest_release.build_option_sets) == 1
    assert manifest_release.build_option_sets[0].id == "1"


# ---------------------------------------------------------------------------
# apply_options: пустой options_map
# ---------------------------------------------------------------------------


def test_apply_options_ignores_missing_key(
    manifest_component: Component, manifest_release: Release
) -> None:
    """apply_options() с пустым options_map оставляет build_option_sets без изменений."""
    DataEnricher.apply_options([manifest_component], {})

    assert manifest_release.build_option_sets == []


# ---------------------------------------------------------------------------
# apply_options: два набора опций
# ---------------------------------------------------------------------------


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


def test_apply_docker_links_updates_existing_definition() -> None:
    """apply_docker_links() обновляет docker_image в существующем ProfileDefinition."""
    comp, rel, pb = _release(profile="hw-linux-x86_64-gcc10_2")
    existing = ProfileDefinition(
        profile_name="hw-linux-x86_64-gcc10_2", docker_image="old"
    )
    profile_definitions: list[ProfileDefinition] = [existing]
    docker_links = {"hw-linux-x86_64-gcc10_2": "harbor.example.com/img:tag"}

    DataEnricher.apply_docker_links([comp], docker_links, profile_definitions)

    assert existing.docker_image == "harbor.example.com/img:tag"
    assert len(profile_definitions) == 1  # дубликат не создаётся


# ---------------------------------------------------------------------------
# apply_docker_links: пустой docker_links
# ---------------------------------------------------------------------------


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


def test_apply_conan_results_sets_profile_build_exists_and_variants(
    conan_variant: ConanVariant,
) -> None:
    """apply_conan_results() устанавливает pb.exists=True и заполняет pb.variants."""
    comp, rel, pb = _release()
    result = _minimal_enrich_result(
        comp, rel, pb, exists=True, variants=[conan_variant]
    )

    DataEnricher.apply_conan_results([comp], result)

    assert pb.exists is True
    assert len(pb.variants) == 1


# ---------------------------------------------------------------------------
# apply_conan_results: создание нового ProfileDefinition с conan_settings
# ---------------------------------------------------------------------------


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


def test_apply_conan_results_missing_release_key_unchanged() -> None:
    """apply_conan_results() оставляет conan_reference пустым, если release_data не содержит совпадений."""
    comp, rel, pb = _release()
    empty_result = ConanEnrichmentResult()

    DataEnricher.apply_conan_results([comp], empty_result)

    assert rel.conan_reference == ""
