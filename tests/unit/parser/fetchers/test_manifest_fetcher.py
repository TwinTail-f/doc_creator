"""Юнит-тесты для autodoc/parser/fetchers/manifest_fetcher.py."""

import shutil
from pathlib import Path

import pytest

from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.exceptions import ParsingError
from autodoc.parser.fetchers.manifest_fetcher import ManifestFetcher
from autodoc.parser.pipeline.context import PipelineContext
from tests.unit.parser.conftest import CopyingAllFakeTFSClient, FakeTFSClient


class CopyingFakeTFSClient(FakeTFSClient):
    """FakeTFSClient, который копирует один реальный файл .properties в output_dir."""

    def __init__(self, source_file: Path) -> None:
        """
        Args:
            source_file: Путь к реальному файлу .properties для копирования.
        """
        self._source = source_file

    def download_properties(
        self,
        items_url: str,
        remote_path: str,
        branch: str,
        output_dir: str,
        version_type=None,
    ) -> None:
        """Копирует исходный файл в output_dir, сохраняя его имя."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        shutil.copy(self._source, out / self._source.name)


def _make_context(
    parser_config: ParserConfigSchema,
    tfs_client: FakeTFSClient,
    tmp_path: Path,
) -> PipelineContext:
    """Строит PipelineContext с заданным фейковым TFS-клиентом."""
    return PipelineContext(
        config=parser_config,
        tmp_dir=tmp_path / "tmp",
        tfs_client=tfs_client,
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    "filename",
    [
        # реальный nlohmann_json.properties через CopyingFakeTFSClient даёт ровно 1 компонент
        pytest.param("nlohmann_json.properties", id="nlohmann-json"),
        # синтетический header-only манифест: 1 компонент (fetcher-parser связка)
        pytest.param("nlohmann_json_fast_only.properties", id="single-version-single-channel-fast"),
        # patchelf: несколько версий в одном канале -> всё равно 1 компонент
        pytest.param("patchelf.properties", id="patchelf-two-versions-one-channel"),
        # libnetfilter_queue (внешний TFS-проект, не DEP_Components) обрабатывается без ошибок
        pytest.param("libnetfilter_queue.properties", id="external-project-no-error"),
    ],
)
def test_manifest_fetcher_single_file_scenarios(
    parser_config: ParserConfigSchema,
    real_manifests_dir: Path,
    tmp_path: Path,
    filename: str,
) -> None:
    """
    Собирает ctx с CopyingFakeTFSClient(<один файл>), вызывает fetch() и проверяет,
    что каждый .properties-файл даёт ровно один компонент без предупреждений."""
    ctx = _make_context(
        parser_config,
        CopyingFakeTFSClient(real_manifests_dir / filename),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(tmp_dir=ctx.tmp_dir, component_names=[], filter_mode="exclude")
    components = result.value

    assert len(components) == 1
    assert result.warnings == []


@pytest.mark.integration
@pytest.mark.parametrize(
    "filename, expected_release_count",
    [
        # синтетический header-only манифест: 1 версия / 1 канал -> 1 релиз (fetcher-parser связка)
        pytest.param(
            "nlohmann_json_fast_only.properties", 1, id="single-version-single-channel-fast"
        ),
        # patchelf: несколько версий в одном канале -> 1 компонент / 2 релиза
        pytest.param("patchelf.properties", 2, id="patchelf-two-versions-one-channel"),
    ],
)
def test_manifest_fetcher_release_count(
    parser_config: ParserConfigSchema,
    real_manifests_dir: Path,
    tmp_path: Path,
    filename: str,
    expected_release_count: int,
) -> None:
    """
    Для манифестов с предсказуемым числом версий проверяет точное количество
    releases у единственного полученного компонента.

    Вынесено из test_manifest_fetcher_single_file_scenarios: для nlohmann_json.properties
    и libnetfilter_queue.properties (реальные многосуффиксные манифесты) точное число
    releases не является предметом проверки этого теста и туда не подмешивается."""
    ctx = _make_context(
        parser_config,
        CopyingFakeTFSClient(real_manifests_dir / filename),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(tmp_dir=ctx.tmp_dir, component_names=[], filter_mode="exclude")
    components = result.value

    assert len(components) == 1
    assert len(components[0].releases) == expected_release_count
    assert result.warnings == []


@pytest.mark.integration
def test_manifest_fetcher_all_components(
    parser_config: ParserConfigSchema,
    real_manifests_dir: Path,
    tmp_path: Path,
) -> None:
    """
    Все реальные .properties-файлы через CopyingAllFakeTFSClient дают ровно
    по одному компоненту на файл (у каждого файла своё уникальное имя компонента)."""
    expected_component_count = len(list(real_manifests_dir.glob("*.properties")))

    ctx = _make_context(
        parser_config,
        CopyingAllFakeTFSClient(real_manifests_dir),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(tmp_dir=ctx.tmp_dir, component_names=[], filter_mode="exclude")

    assert len(result.value) == expected_component_count


@pytest.mark.integration
@pytest.mark.parametrize(
    "filter_mode, component_names, check_names",
    [
        # filter_mode='include' со всеми файлами возвращает ровно перечисленный компонент
        pytest.param(
            "include",
            ["apr"],
            lambda names: names == ["apr"],
            id="include-keeps-only-listed",
        ),
        # filter_mode='exclude' со всеми файлами исключает перечисленный компонент из результата
        pytest.param(
            "exclude",
            ["apr"],
            lambda names: "apr" not in names,
            id="exclude-removes-listed",
        ),
        # filter_mode='include' со списком, не совпадающим ни с одним компонентом, даёт пустой результат
        pytest.param(
            "include",
            ["no_such_component"],
            lambda names: names == [],
            id="include-nonmatching-returns-empty",
        ),
    ],
)
def test_manifest_fetcher_filter_mode(
    parser_config: ParserConfigSchema,
    real_manifests_dir: Path,
    tmp_path: Path,
    filter_mode: str,
    component_names: list[str],
    check_names,
) -> None:
    """component_names/filter_mode фильтруют список компонентов, возвращаемых ManifestFetcher."""
    ctx = _make_context(
        parser_config,
        CopyingAllFakeTFSClient(real_manifests_dir),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(
        tmp_dir=ctx.tmp_dir, component_names=component_names, filter_mode=filter_mode
    )
    names = [c.name for c in result.value]

    assert check_names(names)
    assert result.warnings == []


@pytest.mark.business_logic
def test_manifest_fetcher_no_files_raises_parsing_error(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """
    ManifestFetcher выбрасывает ParsingError, если download_properties не записал ни одного файла.

    ManifestParser при этом не вызывается (ошибка возникает раньше), поэтому
    это собственное правило ManifestFetcher, а не путь двух коллабораторов."""
    ctx = _make_context(
        parser_config,
        FakeTFSClient(),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    with pytest.raises(ParsingError):
        fetcher.fetch(tmp_dir=ctx.tmp_dir, component_names=[], filter_mode="exclude")
