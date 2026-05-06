"""
Юнит-тесты для autodoc/parser/fetchers/manifest_fetcher.py.

Стратегия: предоставляются фейковые TFS-клиенты, записывающие реалистичное
.properties-содержимое в tmp_dir без сетевого ввода/вывода. ManifestParser
НЕ мокируется — тестируется вся цепочка ManifestFetcher → ManifestParser.
"""

import shutil
from pathlib import Path

import pytest

from autodoc.config.parser_config_schema import ParserConfigSchema
from autodoc.exceptions import ParsingError
from autodoc.parser.fetchers.manifest_fetcher import ManifestFetcher
from autodoc.parser.pipeline.context import PipelineContext
from autodoc.tests.unit.parser.conftest import FakeTFSClient

# ---------------------------------------------------------------------------
# Общее содержимое properties (платформа 2.0-tech, компонент "openssl")
# ---------------------------------------------------------------------------

_VALID_PROPERTIES: str = """name= openssl
description= Test OpenSSL component
versions.component= 1.0.0
versions.platform= 2.0-tech
profiles-1.0.0-2.0-tech= hw-linux-x86_64-gcc10_2
tfs_git_project= DEP_Components
git_repo_name= contrib_openssl
"""


# ---------------------------------------------------------------------------
# Локальные фейковые клиенты — определены здесь, НЕ в conftest (по правилам владения)
# ---------------------------------------------------------------------------


class WritingFakeTFSClient(FakeTFSClient):
    """FakeTFSClient, записывающий .properties-файл в output_dir при вызове download_properties."""

    def __init__(self, content: str, filename: str = "test.properties") -> None:
        """
        Args:
            content: Текст для записи в .properties-файл.
            filename: Имя файла, создаваемого внутри output_dir.
        """
        self._content = content
        self._filename = filename

    def download_properties(
        self,
        items_url: str,
        remote_path: str,
        branch: str,
        output_dir: str,
        version_type=None,
    ) -> None:
        """Записывает настроенное содержимое в output_dir как .properties-файл."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / self._filename).write_text(self._content, encoding="utf-8")


class CopyingFakeTFSClient(FakeTFSClient):
    """FakeTFSClient, копирующий реальный .properties-файл в output_dir."""

    def __init__(self, source_file: Path) -> None:
        """
        Args:
            source_file: Путь к реальному .properties-файлу для копирования.
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


# ---------------------------------------------------------------------------
# Вспомогательная функция
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Успешный путь: fetcher возвращает компонент из корректного .properties
# ---------------------------------------------------------------------------


def test_manifest_fetcher_returns_component_on_valid_properties(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """ManifestFetcher возвращает ровно один компонент при корректном .properties-содержимом."""
    ctx = _make_context(
        parser_config,
        WritingFakeTFSClient(content=_VALID_PROPERTIES),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(tmp_dir=ctx.tmp_dir, excluded=[])

    assert len(result.value) == 1
    assert result.value[0].name == "openssl"


# ---------------------------------------------------------------------------
# Исключённый компонент не возвращается
# ---------------------------------------------------------------------------


def test_manifest_fetcher_excludes_named_component(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """ManifestFetcher не возвращает компоненты, если имя компонента исключено."""
    ctx = _make_context(
        parser_config,
        WritingFakeTFSClient(content=_VALID_PROPERTIES),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(tmp_dir=ctx.tmp_dir, excluded=["openssl"])

    assert result.value == []


# ---------------------------------------------------------------------------
# configure сохраняет tfs_client в fetcher
# ---------------------------------------------------------------------------


def test_manifest_fetcher_configure_sets_tfs_client(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """После configure() внутренняя ссылка _tfs в fetcher не равна None."""
    fake_client = WritingFakeTFSClient(content=_VALID_PROPERTIES)
    ctx = _make_context(parser_config, fake_client, tmp_path)
    fetcher = ManifestFetcher()

    fetcher.configure(ctx)

    assert fetcher._tfs is not None


# ---------------------------------------------------------------------------
# Отсутствие .properties-файлов в tmp_dir вызывает ParsingError
# ---------------------------------------------------------------------------


def test_manifest_fetcher_no_files_returns_empty(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """
    ManifestFetcher вызывает ParsingError, когда download_properties не записывает файлы.

    Базовый FakeTFSClient (заглушка) создаёт пустую директорию, которую
    fetcher воспринимает как фатальную ошибку конфигурации или сети.
    """
    ctx = _make_context(
        parser_config,
        FakeTFSClient(),  # заглушка: ничего не записывает
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    with pytest.raises(ParsingError):
        fetcher.fetch(tmp_dir=ctx.tmp_dir, excluded=[])


# ---------------------------------------------------------------------------
# Реальный файл patchelf.properties (использует фикстуру resources_dir)
# ---------------------------------------------------------------------------


def test_manifest_fetcher_with_real_properties_file(
    resources_dir: Path,
    tmp_path: Path,
    parser_config: ParserConfigSchema,
) -> None:
    """ManifestFetcher возвращает компоненты при передаче реального .properties-файла."""
    source = resources_dir / "manifests" / "patchelf.properties"
    ctx = PipelineContext(
        config=parser_config,
        tmp_dir=tmp_path / "tmp",
        tfs_client=CopyingFakeTFSClient(source_file=source),
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(tmp_dir=ctx.tmp_dir, excluded=[])

    names = [c.name for c in result.value]
    assert "patchelf" in names
