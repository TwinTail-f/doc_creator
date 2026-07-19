"""
Юнит-тесты для autodoc/parser/fetchers/options_fetcher.py.
"""
from pathlib import Path

import pytest
import requests

from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.exceptions import NetworkError
from autodoc.models.component import Component
from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.release import Release
from autodoc.parser.fetchers.options_fetcher import OptionsFetcher
from autodoc.parser.pipeline.context import PipelineContext
from tests.unit.parser.conftest import FakeTFSClient


def _load_options_bytes(resources_dir: Path, filename: str) -> bytes:
    """Загружает реальный файл options JSON из resources/options/ как байты."""
    return (resources_dir / "options" / filename).read_bytes()


def _make_items_response(paths: list[str]) -> list[dict]:
    """Строит список item-словарей TFS (не-папок) из списка путей."""
    return [{"path": p, "isFolder": False} for p in paths]


class _OptionsFileFakeTFSClient(FakeTFSClient):
    """Отдаёт фиксированные байты options.json на каждый вызов get_file_content."""

    def __init__(self, items: list[dict], content_bytes: bytes) -> None:
        """
        Args:
            items: Список item-словарей, возвращаемых get_items.
            content_bytes: Сырые байты, возвращаемые как тело ответа.
        """
        self._items = items
        self._bytes = content_bytes

    def get_items(self, items_url, branch, recursion=None, version_type=None):
        """Возвращает предварительно настроенный список items."""
        return self._items

    def get_file_content(self, items_url, path, branch, version_type=None):
        """Возвращает ответ 200 с предварительно настроенными байтами содержимого."""
        resp = requests.Response()
        resp.status_code = 200
        resp._content = self._bytes
        return resp


def _make_component(name, repo, version, channel, project="DEP_Components"):
    """Строит минимальный Component с одним Release для тестов фетчера."""
    release = Release(
        version=version,
        platform="2.0",
        channel=channel,
        profile_builds=[ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")],
    )
    return Component(
        name=name,
        git_project=project,
        git_repo=repo,
        git_url=f"{project}/_git/{repo}",
        releases=[release],
    )


def _make_context(parser_config: ParserConfigSchema, tfs_client, tmp_path: Path):
    """Строит минимальный PipelineContext с заданным фейковым TFS-клиентом."""
    return PipelineContext(
        config=parser_config,
        tmp_dir=tmp_path / "tmp",
        tfs_client=tfs_client,
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    "comp_name, repo, version, channel, tfs_path, options_file",
    [
        pytest.param(
            "apr", "contrib_apr", "1.7.6", "fast",
            "/conan/ci-1.6/options.json", "apr_options.json", id="apr",
        ),
        pytest.param(
            "sqlite3", "contrib_sqlite3", "3.51.2", "fast",
            "/conan/ci-2.0/fast/options.json", "sqlite3_fast_options.json", id="sqlite3",
        ),
        pytest.param(
            "nlohmann_json", "contrib_nlohmann_json", "3.9.1", "slow",
            "/conan/ci-2.0/options.json", "nlohmann_json_options.json", id="nlohmann_json",
        ),
        pytest.param(
            "icu", "contrib_icu", "78.2", "fast",
            "/conan/ci-1.6/fast/options.json", "icu_fast_options.json", id="icu",
        ),
    ],
)
def test_options_fetcher_maps_release_to_real_options_file(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
    resources_dir: Path,
    comp_name: str,
    repo: str,
    version: str,
    channel: str,
    tfs_path: str,
    options_file: str,
) -> None:
    """OptionsFetcher сопоставляет релиз с записью опций из реального файла options.json.

    Конкретные значения опций покрыты test_options_parser.py.
    """
    content = _load_options_bytes(resources_dir, options_file)
    client = _OptionsFileFakeTFSClient(
        items=_make_items_response([tfs_path]),
        content_bytes=content,
    )
    comp = _make_component(comp_name, repo, version, channel)
    ctx = _make_context(parser_config, client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)
    result = fetcher.fetch([comp])

    assert (comp_name, version, channel) in result.value


@pytest.mark.integration
def test_options_fetcher_patchelf_two_versions_share_options(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
    resources_dir: Path,
) -> None:
    """Обе версии patchelf в одном репозитории получают опции; фетчер дедуплицирует скачивание.

    Конкретные значения опций покрыты test_options_parser.py.
    """
    patchelf_bytes = _load_options_bytes(resources_dir, "patchelf_options.json")
    path = "/conan/ci-2.0/options.json"
    client = _OptionsFileFakeTFSClient(
        items=[{"path": path, "isFolder": False}],
        content_bytes=patchelf_bytes,
    )
    comp = Component(
        name="patchelf",
        git_project="DEP_Components",
        git_repo="contrib_patchelf",
        releases=[
            Release(
                version="0.16.1",
                platform="2.0",
                channel="tech",
                profile_builds=[ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")],
            ),
            Release(
                version="0.18.0",
                platform="2.0",
                channel="tech",
                profile_builds=[ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")],
            ),
        ],
    )
    ctx = _make_context(parser_config, client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)
    result = fetcher.fetch([comp])

    assert ("patchelf", "0.16.1", "tech") in result.value
    assert ("patchelf", "0.18.0", "tech") in result.value


@pytest.mark.integration
def test_options_fetcher_empty_items_returns_empty_map(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """Когда get_items не возвращает элементов, OptionsFetcher добавляет запись опций-плейсхолдер."""
    client = _OptionsFileFakeTFSClient(items=[], content_bytes=b"{}")
    release = Release(
        version="3.0.0",
        platform="2.0",
        channel="tech",
        profile_builds=[ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")],
    )
    comp = Component(
        name="openssl",
        git_project="DEP_Components",
        git_repo="contrib_openssl",
        releases=[release],
    )
    ctx = _make_context(parser_config, client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)
    result = fetcher.fetch([comp])

    assert ("openssl", "3.0.0", "tech") in result.value


@pytest.mark.integration
def test_options_fetcher_invalid_json_does_not_raise_openssl_alias(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """OptionsFetcher не выбрасывает исключение при некорректном JSON; ключ релиза присутствует."""
    path = "/conan/ci-2.0/tech/options.json"
    client = _OptionsFileFakeTFSClient(
        items=_make_items_response([path]),
        content_bytes=b"NOT JSON",
    )
    release = Release(
        version="3.0.0",
        platform="2.0",
        channel="tech",
        profile_builds=[ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")],
    )
    comp = Component(
        name="openssl",
        git_project="DEP_Components",
        git_repo="contrib_openssl",
        releases=[release],
    )
    ctx = _make_context(parser_config, client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)
    result = fetcher.fetch([comp])

    assert ("openssl", "3.0.0", "tech") in result.value


class _BranchAwareOptionsFakeTFSClient(FakeTFSClient):
    """Отдаёт разные соответствия путь→содержимое в зависимости от запрошенной ветки.

    Каждая ветка релиза одного репозитория имеет свой набор файлов
    опций (например, ветка fast — ci-2.0/fast/options.json; ветка slow —
    ci-1.6/slow/options.json). Этот фейк отражает такую изоляцию по веткам.
    """

    def __init__(self, branch_to_paths: dict[str, dict[str, str]]) -> None:
        """
        Args:
            branch_to_paths: Соответствие {имя_ветки: {tfs_путь: json_содержимое}}.
        """
        self._map = branch_to_paths

    def get_items(self, items_url, branch, recursion=None, version_type=None):
        """Возвращает элементы только для путей, зарегистрированных под этой веткой."""
        paths = self._map.get(branch, {})
        return [{"path": p, "isFolder": False} for p in paths]

    def get_file_content(self, items_url, path, branch, version_type=None):
        """Возвращает ответ 200 с содержимым, зарегистрированным для этой ветки и пути."""
        content = self._map.get(branch, {}).get(path, "{}")
        resp = requests.Response()
        resp.status_code = 200
        resp._content = content.encode("utf-8")
        return resp


@pytest.mark.integration
def test_options_fetcher_icu_ci16_fallback_no_ci20_present(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
    resources_dir: Path,
) -> None:
    """Фетчер использует фоллбек ci-1.6 для icu, когда путь ci-2.0 в TFS отсутствует.

    Конкретные количества опций покрыты test_options_parser.py.
    """
    icu_bytes = _load_options_bytes(resources_dir, "icu_slow_options.json")
    path = "/conan/ci-1.6/options.json"
    client = _OptionsFileFakeTFSClient(
        items=_make_items_response([path]),
        content_bytes=icu_bytes,
    )
    comp = _make_component("icu", "contrib_icu", "67.1", "slow")
    ctx = _make_context(parser_config, client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)
    result = fetcher.fetch([comp])

    assert ("icu", "67.1", "slow") in result.value


@pytest.mark.integration
def test_options_fetcher_sqlite3_fast_channel_specific_options(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
    resources_dir: Path,
) -> None:
    """Фетчер разрешает опции sqlite3 из поддиректорий канала (ci-2.0/fast и ci-1.6/slow).

    У sqlite3 два релиза на разных ветках, каждая со своим options.json,
    специфичным для канала. После скачивания оба ключа релиза должны
    присутствовать в результате. Конкретные количества записей покрыты
    test_options_parser.py.
    """
    fast_text = _load_options_bytes(resources_dir, "sqlite3_fast_options.json").decode()
    slow_text = _load_options_bytes(resources_dir, "sqlite3_slow_options.json").decode()
    client = _BranchAwareOptionsFakeTFSClient(
        {
            "release_3.51.2": {"/conan/ci-2.0/fast/options.json": fast_text},
            "release_3.34.1": {"/conan/ci-1.6/slow/options.json": slow_text},
        }
    )
    fast_release = Release(
        version="3.51.2",
        platform="2.0",
        channel="fast",
        profile_builds=[ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")],
    )
    slow_release = Release(
        version="3.34.1",
        platform="2.0",
        channel="slow",
        profile_builds=[ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")],
    )
    comp = Component(
        name="sqlite3",
        git_project="DEP_Components",
        git_repo="contrib_sqlite3",
        releases=[fast_release, slow_release],
    )
    ctx = _make_context(parser_config, client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)
    result = fetcher.fetch([comp])

    assert ("sqlite3", "3.51.2", "fast") in result.value
    assert ("sqlite3", "3.34.1", "slow") in result.value


class _RaisingOnGetItemsFakeTFSClient(FakeTFSClient):
    """FakeTFSClient, чей get_items выбрасывает NetworkError."""

    def get_items(self, items_url, branch, recursion=None, version_type=None):
        """Имитирует сетевой сбой при получении списка элементов репозитория."""
        raise NetworkError("simulated network failure on get_items")


class _RaisingOnGetFileContentFakeTFSClient(FakeTFSClient):
    """FakeTFSClient, чей get_items отдаёт один путь, а get_file_content выбрасывает NetworkError."""

    def __init__(self, path: str = "/conan/ci-2.0/options.json") -> None:
        """
        Args:
            path: Путь к options.json, возвращаемый из get_items.
        """
        self._path = path

    def get_items(self, items_url, branch, recursion=None, version_type=None):
        """Возвращает единственный элемент options.json."""
        return [{"path": self._path, "isFolder": False}]

    def get_file_content(self, items_url, path, branch, version_type=None):
        """Имитирует сетевой сбой при скачивании содержимого файла."""
        raise NetworkError("simulated network failure on get_file_content")


class _NotFoundFakeTFSClient(FakeTFSClient):
    """FakeTFSClient, чей get_file_content отвечает 404 на единственный путь options.json."""

    def __init__(self, path: str = "/conan/ci-2.0/options.json") -> None:
        """
        Args:
            path: Путь к options.json, возвращаемый из get_items.
        """
        self._path = path

    def get_items(self, items_url, branch, recursion=None, version_type=None):
        """Возвращает единственный элемент options.json."""
        return [{"path": self._path, "isFolder": False}]

    def get_file_content(self, items_url, path, branch, version_type=None):
        """Возвращает ответ 404 с пустым JSON-телом."""
        resp = requests.Response()
        resp.status_code = 404
        resp._content = b"{}"
        return resp


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "make_client",
    [_RaisingOnGetItemsFakeTFSClient, _RaisingOnGetFileContentFakeTFSClient, _NotFoundFakeTFSClient],
    ids=["get_items-network-error", "get_file_content-network-error", "get_file_content-404"],
)
def test_options_fetcher_failure_modes_return_placeholder(
    make_client, parser_config: ParserConfigSchema, tmp_path: Path,
) -> None:
    """При любой ошибке доступа к TFS (сеть на get_items, сеть на
    get_file_content, 404 на get_file_content) OptionsFetcher возвращает
    плейсхолдер вместо падения."""
    client = make_client()
    comp = _make_component("somelib", "contrib_somelib", "1.0.0", "fast")
    ctx = _make_context(parser_config, client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)
    result = fetcher.fetch([comp])

    assert result.value[("somelib", "1.0.0", "fast")] == {"1": ""}


@pytest.mark.business_logic
def test_options_fetcher_component_without_git_repo_emits_warning(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """Компонент с пустым git_repo пропускается фетчером, а причина попадает в warnings."""
    client = FakeTFSClient()
    comp = Component(
        name="no_repo_lib",
        git_project="DEP_Components",
        git_repo="",
        releases=[
            Release(
                version="1.0.0",
                platform="2.0",
                channel="fast",
                profile_builds=[ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")],
            )
        ],
    )
    ctx = _make_context(parser_config, client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)
    result = fetcher.fetch([comp])

    assert ("no_repo_lib", "1.0.0", "fast") not in result.value
    assert any("no_repo_lib" in w for w in result.warnings)


@pytest.mark.business_logic
def test_options_fetcher_uses_branch_override_template(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """Компонент из component_branch_overrides использует шаблон ветки вместо release_{version}."""
    parser_config.component_branch_overrides = {"openssl": "custom_{version}_branch"}
    client = _BranchAwareOptionsFakeTFSClient(
        {"custom_1.2.3_branch": {"/conan/ci-2.0/options.json": "{}"}}
    )
    comp = _make_component("openssl", "contrib_openssl", "1.2.3", "tech")
    ctx = _make_context(parser_config, client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)
    result = fetcher.fetch([comp])

    assert ("openssl", "1.2.3", "tech") in result.value
