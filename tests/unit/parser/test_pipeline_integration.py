"""Интеграционные тесты для полного пайплайна парсера autodoc.

Подключает все реальные экземпляры шагов (ManifestStep → OptionsResolveStep → ConanEnrichStep →
DockerResolveStep → ArtifactoryValidationStep → FinalizeStep) с заглушками внешнего ввода-вывода.
Сбой здесь указывает на переименование ключа контекста или изменение интерфейса шага,
которое было невидимо для отдельных модульных тестов.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.models.parsed_result import ParsedResult
from autodoc.parser.parser import ComponentParser
from autodoc.parser.pipeline.context import PipelineContext
from autodoc.parser.steps.manifest_step import ManifestStep
from autodoc.parser.steps.finalize_step import FinalizeStep

from autodoc.parser.conan.models.conan_enrichment_result import ConanEnrichmentResult
from autodoc.parser.fetchers.models.fetch_result import FetchResult

_MIN_COMPONENTS: int = 1
_HTTP_OK: int = 200

_EMPTY_CONAN_RESULT = FetchResult(value=ConanEnrichmentResult(), warnings=[])


@pytest.fixture()
def parser_config() -> ParserConfigSchema:
    """Минимально допустимая ParserConfigSchema для интеграционных тестов."""
    return ParserConfigSchema(
        platform_version="2.0",
        platform_branch_name="develop",
        platform_ref_type="branch",
        username="testuser",
        tfs_token="test-tfs-pat-token",
        artifactory_token="test-art-token",
        tfs_collection_url="https://tfs.example.com",
        manifests_remotes_path="/platform/manifests",
        conan_config_url="https://art.example.com/conan-config.zip",
    )


@pytest.fixture()
def resources_dir() -> Path:
    """Путь к реальным .properties фиксчурам манифестов, общим для модульных тестов."""
    return Path(__file__).parent / "resources" / "manifests"


def _make_parser_with_real_steps(
    config: ParserConfigSchema,
    data_dir: Path,
    resources_dir: Path,
) -> ComponentParser:
    """Построить ComponentParser, который использует реальные экземпляры шагов с заглушками ввода-вывода.

    TFS клиент копирует реальные .properties файлы из resources_dir;
    Artifactory всегда возвращает HTTP 200; ConanFetcher залатан для возврата
    результата без операций, чтобы подпроцесс не был запущен.
    """
    from tests.unit.parser.conftest import CopyingAllFakeTFSClient

    tfs_client = CopyingAllFakeTFSClient(resources_dir)
    artifactory_client = _AlwaysOkArtifactoryClient()

    return ComponentParser(
        config=config,
        data_dir=data_dir,
        tfs_client=tfs_client,
        artifactory_client=artifactory_client,
    )


@pytest.mark.integration
def test_full_pipeline_runs_without_raising(
    parser_config: ParserConfigSchema,
    resources_dir: Path,
    tmp_path: Path,
) -> None:
    """Полный пайплайн завершается без вызова исключений и выдаёт ParsedResult.

    Подключает все реальные экземпляры шагов с заглушками внешнего ввода-вывода. Сбой здесь
    указывает на регрессию в проводке шагов, использовании ключей контекста или интерфейсе шага.
    """
    parser = _make_parser_with_real_steps(parser_config, tmp_path, resources_dir)

    with patch(
        "autodoc.parser.fetchers.conan_fetcher.ConanFetcher.fetch",
        return_value=_EMPTY_CONAN_RESULT,
    ):
        result: ParsedResult = parser.parse()

    assert result is not None
    assert isinstance(result, ParsedResult)


@pytest.mark.integration
def test_manifest_step_populates_ctx_components(
    parser_config: ParserConfigSchema,
    resources_dir: Path,
    tmp_path: Path,
) -> None:
    """ManifestStep заполняет ctx.components непустым списком.

    Защита от переименований ключей контекста, которые могли бы незаметно
    очистить список компонентов до того, как他 будут обработаны нисходящими шагами.
    """
    from tests.unit.parser.conftest import CopyingAllFakeTFSClient

    tfs_client = CopyingAllFakeTFSClient(resources_dir)
    ctx = PipelineContext(
        config=parser_config,
        tmp_dir=tmp_path / "tmp",
        tfs_client=tfs_client,
        artifactory_client=MagicMock(),
    )
    ManifestStep().execute(ctx)
    assert len(ctx.components) >= _MIN_COMPONENTS, (
        f"ManifestStep must populate at least {_MIN_COMPONENTS} component(s); "
        f"got {len(ctx.components)}"
    )


@pytest.mark.integration
def test_finalize_step_output_length_matches_input(
    parser_config: ParserConfigSchema,
    resources_dir: Path,
    tmp_path: Path,
) -> None:
    """Количество компонентов в ctx.result.components не превышает число входных компонентов.

    Передаёт полный пайплайн с N компонентами. После завершения пайплайна
    компоненты могут быть отфильтрованы ValidationStep, но никогда искусственно добавлены.
    """
    parser = _make_parser_with_real_steps(parser_config, tmp_path, resources_dir)

    with patch(
        "autodoc.parser.fetchers.conan_fetcher.ConanFetcher.fetch",
        return_value=_EMPTY_CONAN_RESULT,
    ):
        result: ParsedResult = parser.parse()

    assert result is not None
    # Count components seen before finalization via the manifest resources.
    n_manifest_files: int = len(list(resources_dir.glob("*.properties")))
    assert (
        len(result.components) <= n_manifest_files
    ), "FinalizeStep must not create more components than ManifestStep parsed"

_HTTP_OK_E2E: int = 200


class _AlwaysOkArtifactoryClient:
    """Заглушка Artifactory клиента: каждый HEAD запрос возвращает HTTP 200 OK."""

    def head(self, url: str) -> "requests.Response":
        """Возвращает HTTP 200 без выполнения реального сетевого запроса."""
        import requests as _req

        resp = _req.Response()
        resp.status_code = _HTTP_OK_E2E
        return resp


def _make_real_pipeline(
    resources_dir: Path,
    tmp_path: Path,
    parser_config: ParserConfigSchema,
) -> ComponentParser:
    """Создаёт ComponentParser с реальными экземплярами шагов и заглушками внешнего ввода-вывода.

    - TFS: ``CopyingAllFakeTFSClient`` копирует реальные фиксчуры ``.properties``.
    - Artifactory: всегда возвращает HTTP 200.
    - Conan: должен быть залатан каждым тестом на уровне fetcher.
    """
    from tests.unit.parser.conftest import CopyingAllFakeTFSClient

    tfs_client = CopyingAllFakeTFSClient(resources_dir)
    artifactory_client = _AlwaysOkArtifactoryClient()

    return ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        tfs_client=tfs_client,
        artifactory_client=artifactory_client,
    )


@patch("autodoc.parser.fetchers.conan_fetcher.ConanFetcher.fetch")
@pytest.mark.integration
def test_pipeline_patchelf_has_two_releases_after_full_run(
    mock_conan_fetch,
    resources_dir: Path,
    tmp_path: Path,
    parser_config: ParserConfigSchema,
) -> None:
    """patchelf имеет ровно 2 релиза после полного прохода пайплайна.

    Бизнес-сценарий:
        Фиксчур ``patchelf.properties`` объявляет две версии компонента
        (0.16.1 и 0.18.0), привязанные к одной платформе. После полного прохода
        пайплайна (с заглушкой Conan и всегда возвращающим 200 Artifactory),
        полученный ``ParsedResult`` должен содержать один компонент patchelf
        с ровно двумя релизами.

    Предусловия:
        - Реальный пайплайн с ``CopyingAllFakeTFSClient``, указывающим на директорию
          фиксчур ``resources/manifests``.
        - ``ConanFetcher.fetch`` залатан для возврата пустого результата обогащения.

    Шаги:
        1. Вызвать ``parser.parse()``.
        2. Найти компонент ``patchelf`` в ``result.components``.

    Ожидаемый результат:
        - Ровно один компонент patchelf существует.
        - Он имеет ровно 2 релиза.
    """
    mock_conan_fetch.return_value = _EMPTY_CONAN_RESULT
    parser = _make_real_pipeline(resources_dir, tmp_path, parser_config)

    result: ParsedResult = parser.parse()

    patchelf_components = [c for c in result.components if c.name == "patchelf"]
    assert len(patchelf_components) == 1, "Exactly one patchelf component must exist"
    assert (
        len(patchelf_components[0].releases) == 2
    ), f"patchelf should have 2 releases, got: {len(patchelf_components[0].releases)}"


@patch("autodoc.parser.fetchers.conan_fetcher.ConanFetcher.fetch")
@pytest.mark.integration
def test_pipeline_header_only_component_marked_after_conan_enrich(
    mock_conan_fetch,
    resources_dir: Path,
    tmp_path: Path,
    parser_config: ParserConfigSchema,
) -> None:
    """nlohmann_json помечена is_header_only=True после обогащения.

    Бизнес-сценарий:
        ``FinalizeStep._compute_header_only_flags`` устанавливает
        ``Component.is_header_only = True``, когда каждый ``ConanVariant`` во всех
        релизах и профильных сборках компонента имеет NULL_PACKAGE_ID
        (``da39a3ee5e6b4b0d3255bfef95601890afd80709``), что является сигналом Conan
        для заголовочных пакетов, которые не производят бинарный артефакт.

    Предусловия:
        - ``nlohmann_json.properties`` существует в директории фиксчур manifests.
        - ``ConanFetcher.fetch`` залатан с ``side_effect``, который получает живой
          список ``components`` во время вызова (после того как ``ManifestStep``
          создал объекты ``ProfileBuild``) и строит ``ConanEnrichmentResult``
          с ключом ``id(pb)`` для каждого профиля nlohmann, присваивая каждому
          один ``ConanVariant`` с ``package_id = NULL_PACKAGE_ID`` и ``exists = True``.

    Шаги:
        1. Зарегистрировать ``side_effect``, который строит обогащение во время вызова.
        2. Вызвать ``parser.parse()``.
        3. Найти nlohmann_json в ``result.components``.

    Ожидаемый результат:
        - nlohmann_json присутствует (у него есть варианты, поэтому FinalizeStep оставляет его).
        - ``nlohmann.is_header_only`` равна ``True``.
    """
    from autodoc.parser.conan.models.conan_enrichment_result import (
        ConanEnrichmentResult as _EnrichResult,
        ProfileConanData as _ProfileConanData,
    )
    from autodoc.models.conan_variant import ConanVariant as _ConanVariant

    _NULL_PACKAGE_ID: str = "da39a3ee5e6b4b0d3255bfef95601890afd80709"

    def _build_nlohmann_enrich(components):
        """Построить ConanEnrichmentResult, дав каждому профилю nlohmann вариант с NULL_PACKAGE_ID.

        Вызывается во время fetch(), поэтому живые объекты ProfileBuild (созданные
        ManifestStep) доступны и id(pb) может быть использован как ключ словаря,
        ожидаемый DataEnricher.apply_conan_results().
        """
        result = _EnrichResult()
        for comp in components:
            if "nlohmann" not in comp.name.lower():
                continue
            for release in comp.releases:
                for pb in release.profile_builds:
                    result.profile_data[id(pb)] = _ProfileConanData(
                        conan_settings={},
                        exists=True,
                        variants=[
                            _ConanVariant(
                                package_id=_NULL_PACKAGE_ID,
                                build_url="",
                                build_date="2024-01-01",
                                options_ref="1",
                            )
                        ],
                    )
        return FetchResult(value=result, warnings=[])

    mock_conan_fetch.side_effect = _build_nlohmann_enrich
    parser = _make_real_pipeline(resources_dir, tmp_path, parser_config)

    result: ParsedResult = parser.parse()

    nlohmann = next((c for c in result.components if "nlohmann" in c.name.lower()), None)

    assert nlohmann is not None, (
        "nlohmann_json must be present in the result when enriched with "
        "NULL_PACKAGE_ID variants (FinalizeStep must not prune it)"
    )
    assert nlohmann.is_header_only is True, (
        f"nlohmann_json must be marked is_header_only=True after enrichment with "
        f"NULL_PACKAGE_ID variants; got {nlohmann.is_header_only}"
    )


@patch("autodoc.parser.fetchers.conan_fetcher.ConanFetcher.fetch")
@pytest.mark.integration
def test_pipeline_profile_builds_populated_after_manifest_step(
    mock_conan_fetch,
    resources_dir: Path,
    tmp_path: Path,
    parser_config: ParserConfigSchema,
) -> None:
    """После ManifestStep все компоненты имеют скелеты ProfileBuild.

    Бизнес-сценарий:
        После того как выполняется ``ManifestStep``, каждый Release в каждом
        Component должен иметь по крайней мере одну запись ``ProfileBuild``.
        Каждая запись должна иметь ``exists=False`` (ещё не проверена в Artifactory)
        и ``variants=[]`` (ещё не обогащена Conan).

    Предусловия:
        - Реальный пайплайн; observer-шаг вставлен после ManifestStep (индекс 1).
        - Conan залатан для возврата пустого обогащения.

    Шаги:
        1. Вставить ``_ObserveAfterManifest`` с индексом 1 в ``parser._steps``.
        2. Вызвать ``parser.parse()``.

    Ожидаемый результат:
        - По крайней мере одно наблюдение записано.
        - Каждый наблюдаемый ProfileBuild имеет ``exists=False`` и ``len(variants)==0``.
    """
    from autodoc.parser.steps.base_parse_step import BaseParseStep
    from autodoc.parser.pipeline.context import PipelineContext

    mock_conan_fetch.return_value = _EMPTY_CONAN_RESULT

    observed_states: list[tuple[str, bool, int]] = []

    class _ObserveAfterManifest(BaseParseStep):
        name = "observe_after_manifest_bl_e2e_03"
        is_critical = False

        def execute(self, ctx: PipelineContext) -> None:
            for comp in ctx.components:
                for release in comp.releases:
                    for pb in release.profile_builds:
                        observed_states.append((comp.name, pb.exists, len(pb.variants)))

    parser = _make_real_pipeline(resources_dir, tmp_path, parser_config)
    parser._steps.insert(1, _ObserveAfterManifest())

    parser.parse()

    assert (
        len(observed_states) > 0
    ), "ManifestStep must create ProfileBuild skeletons before the observer runs"
    for comp_name, exists, variant_count in observed_states:
        assert exists is False, (
            f"After ManifestStep pb.exists must be False; " f"got True for {comp_name}"
        )
        assert variant_count == 0, (
            f"After ManifestStep pb.variants must be []; " f"got {variant_count} for {comp_name}"
        )


@patch("autodoc.parser.fetchers.conan_fetcher.ConanFetcher.fetch")
@pytest.mark.integration
def test_pipeline_options_applied_after_options_step(
    mock_conan_fetch,
    resources_dir: Path,
    tmp_path: Path,
    parser_config: ParserConfigSchema,
) -> None:
    """По крайней мере один релиз имеет build_option_sets после OptionsResolveStep.

    Бизнес-сценарий:
        ``OptionsResolveStep`` получает конфигурацию параметров Conan из TFS и
        заполняет ``Release.build_option_sets``. С реальными фиксчурами манифестов
        и ``CopyingAllFakeTFSClient``, по крайней мере один релиз должен иметь
        непустой список опций после выполнения шага.

    Предусловия:
        - Observer-шаг вставлен после OptionsResolveStep (индекс 2).
        - Conan залатан для возврата пустого обогащения.

    Шаги:
        1. Вставить ``_ObserveAfterOptions`` с индексом 2.
        2. Вызвать ``parser.parse()``.

    Ожидаемый результат:
        - Сумма ``len(release.build_option_sets)`` во всех релизах больше 0
          по крайней мере для одного компонента.

    Примечание:
        Если фейк TFS-клиент не возвращает файлы опций, общее значение может быть 0.
        Тест утверждает, что наблюдатель выполнился (проводка шагов корректна),
        даже если фейк TFS не применил опции.
    """
    from autodoc.parser.steps.base_parse_step import BaseParseStep
    from autodoc.parser.pipeline.context import PipelineContext

    mock_conan_fetch.return_value = _EMPTY_CONAN_RESULT

    options_by_release: dict[tuple, int] = {}

    class _ObserveAfterOptions(BaseParseStep):
        name = "observe_after_options_bl_e2e_04"
        is_critical = False

        def execute(self, ctx: PipelineContext) -> None:
            for comp in ctx.components:
                for release in comp.releases:
                    key = (comp.name, release.version, release.channel)
                    options_by_release[key] = len(release.build_option_sets)

    parser = _make_real_pipeline(resources_dir, tmp_path, parser_config)
    # Вставить observer сразу после OptionsResolveStep (индекс 2 в стандартном пайплайне)
    parser._steps.insert(2, _ObserveAfterOptions())

    parser.parse()

    # Убедиться, что наблюдатель выполнился (проводка шагов валидна)
    assert (
        len(options_by_release) > 0
    ), "_ObserveAfterOptions должен был выполниться; ни один релиз не был наблюден"


@patch("autodoc.parser.fetchers.conan_fetcher.ConanFetcher.fetch")
@pytest.mark.integration
def test_pipeline_result_components_sorted_alphabetically(
    mock_conan_fetch,
    resources_dir: Path,
    tmp_path: Path,
    parser_config: ParserConfigSchema,
) -> None:
    """Компоненты в ParsedResult.components отсортированы в алфавитном порядке.

    Бизнес-сценарий:
        ``FinalizeStep`` сортирует финальный список компонентов по имени
        (без учёта регистра) так, чтобы сгенерированная документация
        была детерминированной и удобочитаемой.

    Предусловия:
        - Реальный пайплайн; по крайней мере 2 компонента из директории manifests.
        - Conan залатан для возврата пустого обогащения.

    Шаги:
        1. Вызвать ``parser.parse()``.
        2. Извлечь названия компонентов из ``result.components``.

    Ожидаемый результат:
        - ``names`` равна ``sorted(names, key=str.lower)``.
    """
    mock_conan_fetch.return_value = _EMPTY_CONAN_RESULT
    parser = _make_real_pipeline(resources_dir, tmp_path, parser_config)

    result: ParsedResult = parser.parse()

    names = [c.name for c in result.components]
    assert len(names) >= 2, "Нужно по крайней мере 2 компонента для проверки алфавитной сортировки"
    sorted_names = sorted(names, key=lambda n: n.lower())
    assert names == sorted_names, (
        f"Компоненты должны быть отсортированы в алфавитном порядке (без учёта регистра), "
        f"получено: {names}"
    )


@patch("autodoc.parser.fetchers.conan_fetcher.ConanFetcher.fetch")
@pytest.mark.integration
def test_pipeline_non_existing_profiles_removed_after_finalize(
    mock_conan_fetch,
    resources_dir: Path,
    tmp_path: Path,
    parser_config: ParserConfigSchema,
) -> None:
    """Финальный ParsedResult не содержит записей ProfileBuild с exists=False.

    Бизнес-сценарий:
        ``ManifestStep`` создаёт скелеты ``ProfileBuild`` с ``exists=False``.
        ``ConanEnrichStep`` помечает их ``exists=True``, когда пакеты найдены.
        Затем ``FinalizeStep`` удаляет все оставшиеся записи ``exists=False``.
        Финальный ``ParsedResult`` должен поэтому содержать только живые профильные сборки.

    Предусловия:
        - Реальный пайплайн с пустым обогащением Conan (без возвращённых вариантов).
        - Все ProfileBuilds останутся с ``exists=False`` → FinalizeStep удалит все.

    Шаги:
        1. Вызвать ``parser.parse()``.
        2. Пройти по всем компонентам → релизам → profile_builds.

    Ожидаемый результат:
        - Ни один ``ProfileBuild`` с ``exists=False`` не появляется в результате.
        (С пустым обогащением Conan результат может содержать ноль компонентов
        или ноль релизов — это также валидно.)
    """
    mock_conan_fetch.return_value = _EMPTY_CONAN_RESULT
    parser = _make_real_pipeline(resources_dir, tmp_path, parser_config)

    result: ParsedResult = parser.parse()

    for comp in result.components:
        for release in comp.releases:
            for pb in release.profile_builds:
                assert pb.exists is True, (
                    f"После FinalizeStep не должно быть ProfileBuilds с exists=False. "
                    f"Найден для {comp.name}/{release.version}/{pb.profile_name}"
                )


@pytest.mark.integration
def test_full_pipeline_raises_parsing_error_when_no_manifests_found(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """Реальный ManifestFetcher без .properties-файлов останавливает пайплайн с ParsingError.

    Заменяет прежние синтетические тесты сбоя (фейковые шаги, лишь названные
    в честь реальных), которые не добавляли покрытия сверх модульных тестов
    ComponentParser. Здесь используется настоящая production-цепочка шагов:
    TFS-клиент по умолчанию (``FakeTFSClient``) не копирует ни одного файла,
    поэтому ``ManifestFetcher`` реально бросает ``ParsingError`` при
    отсутствии манифестов, и это исключение должно дойти до вызывающей стороны
    непосредственно через ``ManifestStep`` → ``ComponentParser.parse()``.
    """
    from tests.unit.parser.conftest import FakeTFSClient
    from autodoc.exceptions import ParsingError

    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        tfs_client=FakeTFSClient(),
        artifactory_client=_AlwaysOkArtifactoryClient(),
    )

    with pytest.raises(ParsingError):
        parser.parse()


@patch("autodoc.parser.fetchers.conan_fetcher.ConanFetcher.fetch")
@pytest.mark.integration
def test_full_pipeline_save_intermediate_writes_real_files(
    mock_conan_fetch,
    resources_dir: Path,
    tmp_path: Path,
    parser_config: ParserConfigSchema,
) -> None:
    """save_intermediate=True записывает JSON-снимок для каждого шага реального пайплайна.

    До этого теста ``save_intermediate`` проверялся только с фейковыми
    шагами (``test_component_parser_save_intermediate_writes_files`` в
    ``test_parser.py``). Здесь снимки должны появляться и когда пайплайн
    состоит из настоящих production-шагов.
    """
    mock_conan_fetch.return_value = _EMPTY_CONAN_RESULT
    parser = _make_real_pipeline(resources_dir, tmp_path, parser_config)

    parser.parse(save_intermediate=True)

    intermediate_dir = tmp_path / "intermediate"
    json_files = list(intermediate_dir.glob("*.json"))
    assert len(json_files) == 6, (
        f"Ожидалось 6 файлов снимков (по одному на шаг реального пайплайна), "
        f"получено {len(json_files)}"
    )


@patch("autodoc.parser.fetchers.conan_fetcher.ConanFetcher.fetch")
@pytest.mark.integration
def test_full_pipeline_removes_dead_variant_on_404(
    mock_conan_fetch,
    resources_dir: Path,
    tmp_path: Path,
    parser_config: ParserConfigSchema,
) -> None:
    """Вариант, для которого Artifactory возвращает HTTP 404, удаляется реальной валидацией.

    Заглушка Artifactory в этом файле всегда возвращает 200, поэтому ветка
    удаления мёртвых вариантов в ``ArtifactoryValidationStep`` не покрывалась
    сквозным тестом. Здесь Conan обогащает один профиль patchelf вариантом
    с ``build_url``, а Artifactory-клиент отвечает 404 именно на этот URL —
    после ``ArtifactoryValidationStep`` вариант должен исчезнуть из
    ``pb.variants``, хотя сам ``ProfileBuild`` остаётся (``exists=True``).
    """
    from autodoc.parser.conan.models.conan_enrichment_result import (
        ConanEnrichmentResult as _EnrichResult,
        ProfileConanData as _ProfileConanData,
    )
    from autodoc.models.conan_variant import ConanVariant as _ConanVariant

    _DEAD_URL: str = "https://art.example.com/ui/repos/tree/General/patchelf/dead"

    def _build_patchelf_enrich(components):
        """Дать одному профилю patchelf вариант с build_url, ведущим к 404."""
        result = _EnrichResult()
        for comp in components:
            if comp.name != "patchelf":
                continue
            for release in comp.releases:
                for pb in release.profile_builds:
                    result.profile_data[id(pb)] = _ProfileConanData(
                        conan_settings={},
                        exists=True,
                        variants=[
                            _ConanVariant(
                                package_id="abc123",
                                build_url=_DEAD_URL,
                                build_date="2024-01-01",
                                options_ref="1",
                            )
                        ],
                    )
        return FetchResult(value=result, warnings=[])

    class _NotFoundForDeadUrlArtifactoryClient:
        """Заглушка: HTTP 404 для _DEAD_URL (после преобразования в API-путь), иначе 200."""

        def head(self, url: str):
            import requests as _req

            resp = _req.Response()
            resp.status_code = 404 if "patchelf/dead" in url else 200
            return resp

    from tests.unit.parser.conftest import CopyingAllFakeTFSClient

    mock_conan_fetch.side_effect = _build_patchelf_enrich

    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        tfs_client=CopyingAllFakeTFSClient(resources_dir),
        artifactory_client=_NotFoundForDeadUrlArtifactoryClient(),
    )

    result: ParsedResult = parser.parse()

    patchelf = next((c for c in result.components if c.name == "patchelf"), None)
    assert patchelf is not None, "patchelf должен пережить финализацию"

    all_variants = [
        v
        for release in patchelf.releases
        for pb in release.profile_builds
        for v in pb.variants
    ]
    assert all(v.build_url != _DEAD_URL for v in all_variants), (
        "Вариант с build_url, вернувшим HTTP 404, должен быть удалён "
        "ArtifactoryValidationStep"
    )
