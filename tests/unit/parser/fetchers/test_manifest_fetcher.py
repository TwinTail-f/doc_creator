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
def test_manifest_fetcher_returns_nlohmann_json(
    parser_config: ParserConfigSchema,
    real_manifests_dir: Path,
    tmp_path: Path,
) -> None:
    """Реальный nlohmann_json.properties через CopyingFakeTFSClient даёт ровно 1 компонент."""
    ctx = _make_context(
        parser_config,
        CopyingFakeTFSClient(real_manifests_dir / "nlohmann_json.properties"),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(tmp_dir=ctx.tmp_dir, component_names=[], filter_mode="exclude")

    assert len(result.value) == 1
    assert result.warnings == []


@pytest.mark.integration
def test_manifest_fetcher_all_five_components(
    parser_config: ParserConfigSchema,
    real_manifests_dir: Path,
    tmp_path: Path,
) -> None:
    """Все реальные .properties-файлы через CopyingAllFakeTFSClient дают не менее 5 компонентов."""
    ctx = _make_context(
        parser_config,
        CopyingAllFakeTFSClient(real_manifests_dir),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(tmp_dir=ctx.tmp_dir, component_names=[], filter_mode="exclude")

    assert len(result.value) >= 5


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
    """ManifestFetcher выбрасывает ParsingError, если download_properties не записал ни одного файла.

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


@pytest.mark.integration
def test_manifest_fetcher_single_version_single_channel_fast(
    parser_config: ParserConfigSchema,
    real_manifests_dir: Path,
    tmp_path: Path,
) -> None:
    """Фетчер возвращает 1 компонент / 1 релиз для фикстуры nlohmann_json_fast_only.

    Использует синтетический nlohmann_json_fast_only.properties и проверяет, что
    связка fetcher-parser корректно обрабатывает простейшую структуру
    header-only манифеста. Конкретные значения полей (канал, версия) покрыты
    test_manifest_parser.py.
    """
    fixture = real_manifests_dir / "nlohmann_json_fast_only.properties"
    ctx = _make_context(
        parser_config,
        CopyingFakeTFSClient(fixture),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(tmp_dir=ctx.tmp_dir, component_names=[], filter_mode="exclude")
    components = result.value

    assert len(components) == 1
    assert len(components[0].releases) == 1
    assert result.warnings == []


@pytest.mark.integration
def test_manifest_fetcher_patchelf_two_versions_one_channel(
    parser_config: ParserConfigSchema,
    real_manifests_dir: Path,
    tmp_path: Path,
) -> None:
    """Фетчер возвращает 1 компонент / 2 релиза для patchelf (несколько версий в одном канале).

    Конкретные значения канала покрыты test_manifest_parser.py.
    """
    ctx = _make_context(
        parser_config,
        CopyingFakeTFSClient(real_manifests_dir / "patchelf.properties"),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(tmp_dir=ctx.tmp_dir, component_names=[], filter_mode="exclude")
    components = result.value

    assert len(components) == 1
    assert len(components[0].releases) == 2
    assert result.warnings == []


@pytest.mark.integration
def test_manifest_fetcher_external_project_no_error(
    parser_config: ParserConfigSchema,
    real_manifests_dir: Path,
    tmp_path: Path,
) -> None:
    """Фетчер обрабатывает libnetfilter_queue (внешний TFS-проект) без ошибок и предупреждений.

    Компонент из проекта, отличного от DEP_Components, не должен приводить к
    исключениям или неожиданным предупреждениям. Конкретные значения поля
    git_project покрыты test_manifest_parser.py.
    """
    ctx = _make_context(
        parser_config,
        CopyingFakeTFSClient(real_manifests_dir / "libnetfilter_queue.properties"),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(tmp_dir=ctx.tmp_dir, component_names=[], filter_mode="exclude")
    components = result.value

    assert len(components) == 1
    assert result.warnings == []
