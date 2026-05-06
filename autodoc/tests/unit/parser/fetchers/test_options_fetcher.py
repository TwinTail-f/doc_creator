"""
Юнит-тесты для autodoc/parser/fetchers/options_fetcher.py.

Стратегия: наследуемся от FakeTFSClient, чтобы управлять возвращаемыми
значениями get_items и get_file_content, затем проверяем OptionsMap.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import requests

from autodoc.config.parser_config_schema import ParserConfigSchema
from autodoc.models.component import Component
from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.release import Release
from autodoc.parser.fetchers.options_fetcher import OptionsFetcher
from autodoc.parser.pipeline.context import PipelineContext
from autodoc.tests.unit.parser.conftest import FakeTFSClient

# ---------------------------------------------------------------------------
# Константы путей, удовлетворяющие фильтрам путей OptionsParser:
#   - должны заканчиваться на "options.json"
#   - должны содержать "/conan/"
#   - должны содержать "/ci-2.0/" для выбора CI-префикса
# ---------------------------------------------------------------------------

_OPTIONS_PATH: str = "/conan/ci-2.0/tech/options.json"


# ---------------------------------------------------------------------------
# Локальные фейковые TFS-клиенты
# ---------------------------------------------------------------------------


class _ItemsAndContentFakeTFSClient(FakeTFSClient):
    """
    FakeTFSClient, чьи get_items и get_file_content возвращают настраиваемые данные.

    Полезен для тестирования всего пайплайна OptionsFetcher.
    """

    def __init__(self, items: list, content: bytes) -> None:
        """
        Args:
            items: Список словарей элементов, возвращаемых get_items.
            content: Сырые байты, возвращаемые как тело ответа get_file_content.
        """
        self._items = items
        self._content = content

    def get_items(
        self, items_url: str, branch: str, recursion=None, version_type=None
    ) -> list:
        """Возвращает заранее настроенный список элементов."""
        return self._items

    def get_file_content(
        self, items_url: str, path: str, branch: str, version_type=None
    ):
        """Возвращает ответ 200 с заранее настроенным содержимым."""
        resp = requests.Response()
        resp.status_code = 200
        resp._content = self._content
        return resp


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


def _make_component(
    name: str = "openssl",
    git_repo: str = "contrib_openssl",
    version: str = "3.0.0",
    channel: str = "tech",
) -> Component:
    """Строит минимальный Component с одним Release."""
    release = Release(
        version=version,
        platform="2.0",
        channel=channel,
        git_url="DEP_Components/_git/contrib_openssl",
        profile_builds=[ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")],
    )
    return Component(
        name=name,
        description="Test component",
        git_project="DEP_Components",
        git_repo=git_repo,
        releases=[release],
    )


def _make_context(
    parser_config: ParserConfigSchema,
    tfs_client: FakeTFSClient,
    tmp_path: Path,
) -> PipelineContext:
    """Строит минимальный PipelineContext с заданным фейковым TFS-клиентом."""
    return PipelineContext(
        config=parser_config,
        tmp_dir=tmp_path / "tmp",
        tfs_client=tfs_client,
    )


# ---------------------------------------------------------------------------
# Успешный путь: опции извлекаются для релиза компонента
# ---------------------------------------------------------------------------


def test_options_fetcher_extracts_options_for_release(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """OptionsFetcher отображает (name, version, channel) → разобранные опции при успехе."""
    component = _make_component()
    tfs_client = _ItemsAndContentFakeTFSClient(
        items=[{"path": _OPTIONS_PATH, "isFolder": False}],
        content=json.dumps({"1": "shared=True"}).encode(),
    )
    ctx = _make_context(parser_config, tfs_client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch([component])

    key = ("openssl", "3.0.0", "tech")
    assert key in result.value
    assert result.value[key] == {"1": "shared=True"}


# ---------------------------------------------------------------------------
# get_items возвращает пустой список → опции по умолчанию в карте
# ---------------------------------------------------------------------------


def test_options_fetcher_empty_items_returns_empty_map(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """
    Когда get_items не возвращает элементов, OptionsFetcher добавляет запись опций по умолчанию.

    Запасной вариант OptionsParser.pick_options возвращает {"1": ""}, если нет
    канало-специфичных или глобальных опций.
    """
    component = _make_component()
    tfs_client = _ItemsAndContentFakeTFSClient(items=[], content=b"{}")
    ctx = _make_context(parser_config, tfs_client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch([component])

    # Без исключений; ключ существует со значением запасного варианта.
    assert ("openssl", "3.0.0", "tech") in result.value


# ---------------------------------------------------------------------------
# Нераспознаваемое JSON-содержимое молча пропускается
# ---------------------------------------------------------------------------


def test_options_fetcher_skips_on_invalid_json(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """
    OptionsFetcher не вызывает исключений, когда get_file_content возвращает некорректный JSON.

    OptionsParser логирует предупреждение внутри и возвращает пустой словарь опций.
    Fetcher продолжает работу и возвращает значение по умолчанию для данного релиза.
    """
    component = _make_component()
    tfs_client = _ItemsAndContentFakeTFSClient(
        items=[{"path": _OPTIONS_PATH, "isFolder": False}],
        content=b"NOT JSON",
    )
    ctx = _make_context(parser_config, tfs_client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch([component])

    # Fetcher не должен вызывать исключений; ключ релиза должен присутствовать.
    assert ("openssl", "3.0.0", "tech") in result.value
