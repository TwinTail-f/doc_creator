"""
Юнит-тесты для autodoc/parser/fetchers/docker_fetcher.py.
"""

from pathlib import Path

import pytest
import requests

from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.parser.fetchers.docker_fetcher import DockerFetcher
from autodoc.parser.pipeline.context import PipelineContext
from tests.unit.parser.conftest import FakeTFSClient

# Корректный TFS URL, содержащий /_git/, чтобы DockerFetcher его не пропустил.
# Параметры запроса: path (путь к YAML-файлу) и version (ветка с префиксом GB).
_PROFILE_URL: str = (
    "https://tfs.example.com/DEP_Components/_git/platform-profiles"
    "?path=/profiles.yaml&version=GBdevelop"
)

YAML_CONTENT: str = """
archs:
  linux-x86_64-gcc10_2:
    revision: 1
    profile_host: linux-x86_64-gcc10_2
    profile_build: linux-x86_64-gcc10_2
    docker: harbor.example.com/debian11:components
"""


class _TrackingFakeTFSClient(FakeTFSClient):
    """FakeTFSClient, запоминающий ветку, переданную в каждый вызов get_file_content."""

    def __init__(self, content: bytes = b"", status_code: int = 200) -> None:
        super().__init__(content=content, status_code=status_code)
        self.received_branches: list[str] = []

    def get_file_content(
        self, items_url: str, path: str, branch: str, version_type=None
    ) -> requests.Response:
        """Запоминает переданную ветку и возвращает настроенный ответ."""
        self.received_branches.append(branch)
        return super().get_file_content(items_url, path, branch, version_type)


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


@pytest.mark.business_logic
def test_docker_fetcher_extracts_links_from_yaml(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """DockerFetcher возвращает docker-ссылку для каждого профиля, найденного в YAML."""
    tfs_client = FakeTFSClient(content=YAML_CONTENT.encode())
    ctx = _make_context(parser_config, tfs_client, tmp_path)
    fetcher = DockerFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(urls=[_PROFILE_URL], target_platform="2.0")

    assert result.value["linux-x86_64-gcc10_2"] == "harbor.example.com/debian11:components"


@pytest.mark.business_logic
def test_docker_fetcher_empty_urls_returns_empty_links(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """DockerFetcher.fetch с пустым списком URL возвращает пустую карту ссылок.

    TFS и DockerParser не вызываются вовсе — это собственное правило
    DockerFetcher на пустом входе, а не путь двух коллабораторов."""
    tfs_client = FakeTFSClient()
    ctx = _make_context(parser_config, tfs_client, tmp_path)
    fetcher = DockerFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(urls=[], target_platform="2.0")

    assert result.value == {}


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "make_client",
    [
        # get_file_content выбрасывает сетевое исключение
        lambda: FakeTFSClient(exception=requests.ConnectionError("simulated connection error")),
        # тело ответа — некорректный YAML
        lambda: FakeTFSClient(content=b"[unclosed: mapping: {"),
        # get_file_content вернул не-200 статус без исключения
        lambda: FakeTFSClient(content=YAML_CONTENT.encode(), status_code=404),
    ],
    ids=["network-error", "invalid-yaml", "http-404"],
)
def test_docker_fetcher_skips_url_on_fetch_failure(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
    make_client,
) -> None:
    """DockerFetcher пропускает URL при сетевой ошибке, некорректном YAML или не-200
    статусе ответа; в этих сценариях DockerParser не вызывается (ошибка перехватывается
    раньше), поэтому это не путь двух коллабораторов, а собственное правило DockerFetcher.
    Ошибка только логируется — FetchResult.warnings при этом не заполняется."""
    ctx = _make_context(parser_config, make_client(), tmp_path)
    fetcher = DockerFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(urls=[_PROFILE_URL], target_platform="2.0")

    assert result.value == {}
    assert result.warnings == []


@pytest.mark.business_logic
def test_docker_fetcher_skips_url_without_git_segment(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """DockerFetcher молча пропускает URL, не содержащий сегмент /_git/."""
    url_without_git: str = (
        "https://tfs.example.com/DEP_Components/profiles.yaml?path=/profiles.yaml"
    )
    tfs_client = _TrackingFakeTFSClient(content=YAML_CONTENT.encode())
    ctx = _make_context(parser_config, tfs_client, tmp_path)
    fetcher = DockerFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(urls=[url_without_git], target_platform="2.0")

    assert result.value == {}
    assert tfs_client.received_branches == []


@pytest.mark.business_logic
def test_docker_fetcher_uses_target_platform_when_version_param_missing(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """При отсутствии параметра version в URL DockerFetcher использует target_platform как ветку."""
    url_without_version: str = (
        "https://tfs.example.com/DEP_Components/_git/platform-profiles?path=/profiles.yaml"
    )
    tfs_client = _TrackingFakeTFSClient(content=YAML_CONTENT.encode())
    ctx = _make_context(parser_config, tfs_client, tmp_path)
    fetcher = DockerFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(urls=[url_without_version], target_platform="2.0")

    assert tfs_client.received_branches == ["2.0"]
    assert result.value["linux-x86_64-gcc10_2"] == "harbor.example.com/debian11:components"
