"""
Юнит-тесты для autodoc/parser/fetchers/docker_fetcher.py.

Стратегия: предоставляется фейковый TFS-клиент, чей get_file_content возвращает
управляемое содержимое YAML. DockerParser НЕ мокируется — тестируется вся
цепочка DockerFetcher → DockerParser.
"""

import pytest

from pathlib import Path

import requests
import yaml

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


class _ContentFakeTFSClient(FakeTFSClient):
    """FakeTFSClient, возвращающий настраиваемый ответ из get_file_content."""

    def __init__(self, content: bytes, status_code: int = 200) -> None:
        """
        Args:
            content: Байты, возвращаемые как тело ответа.
            status_code: HTTP-код статуса ответа.
        """
        self._content = content
        self._status_code = status_code

    def get_file_content(
        self, items_url: str, path: str, branch: str, version_type=None
    ) -> requests.Response:
        """Возвращает ответ с настроенным кодом статуса и содержимым."""
        resp = requests.Response()
        resp.status_code = self._status_code
        resp._content = self._content
        return resp


class _RaisingFakeTFSClient(FakeTFSClient):
    """FakeTFSClient, чей get_file_content вызывает requests.ConnectionError."""

    def get_file_content(
        self, items_url: str, path: str, branch: str, version_type=None
    ) -> requests.Response:
        """Имитирует сетевой сбой (перехватывается DockerFetcher)."""
        raise requests.ConnectionError("simulated connection error")


class _TrackingFakeTFSClient(FakeTFSClient):
    """FakeTFSClient, запоминающий ветку, переданную в каждый вызов get_file_content."""

    def __init__(self, content: bytes = b"", status_code: int = 200) -> None:
        """
        Args:
            content: Байты, возвращаемые как тело ответа.
            status_code: HTTP-код статуса ответа.
        """
        self._content = content
        self._status_code = status_code
        self.received_branches: list[str] = []

    def get_file_content(
        self, items_url: str, path: str, branch: str, version_type=None
    ) -> requests.Response:
        """Запоминает переданную ветку и возвращает настроенный ответ."""
        self.received_branches.append(branch)
        resp = requests.Response()
        resp.status_code = self._status_code
        resp._content = self._content
        return resp


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


@pytest.mark.integration
def test_docker_fetcher_extracts_links_from_yaml(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """DockerFetcher возвращает docker-ссылку для каждого профиля, найденного в YAML."""
    tfs_client = _ContentFakeTFSClient(content=YAML_CONTENT.encode())
    ctx = _make_context(parser_config, tfs_client, tmp_path)
    fetcher = DockerFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(urls=[_PROFILE_URL], target_platform="2.0")

    assert result.value["linux-x86_64-gcc10_2"] == "harbor.example.com/debian11:components"


@pytest.mark.integration
def test_docker_fetcher_empty_urls_returns_empty_links(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """DockerFetcher.fetch с пустым списком URL возвращает пустую карту ссылок."""
    tfs_client = FakeTFSClient()
    ctx = _make_context(parser_config, tfs_client, tmp_path)
    fetcher = DockerFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(urls=[], target_platform="2.0")

    assert result.value == {}


@pytest.mark.integration
def test_docker_fetcher_failed_url_produces_warning(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """DockerFetcher пропускает URL, когда get_file_content вызывает исключение сети."""
    ctx = _make_context(parser_config, _RaisingFakeTFSClient(), tmp_path)
    fetcher = DockerFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(urls=[_PROFILE_URL], target_platform="2.0")

    assert result.value == {}


@pytest.mark.integration
def test_docker_fetcher_invalid_yaml_produces_warning(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """DockerFetcher пропускает URL, когда тело ответа не является корректным YAML."""
    invalid_yaml: bytes = b"[unclosed: mapping: {"
    tfs_client = _ContentFakeTFSClient(content=invalid_yaml)
    ctx = _make_context(parser_config, tfs_client, tmp_path)
    fetcher = DockerFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(urls=[_PROFILE_URL], target_platform="2.0")

    assert result.value == {}


@pytest.mark.business_logic
def test_docker_fetcher_skips_url_without_git_segment(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """DockerFetcher молча пропускает URL, не содержащий сегмент /_git/."""
    url_without_git: str = "https://tfs.example.com/DEP_Components/profiles.yaml?path=/profiles.yaml"
    tfs_client = _TrackingFakeTFSClient(content=YAML_CONTENT.encode())
    ctx = _make_context(parser_config, tfs_client, tmp_path)
    fetcher = DockerFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(urls=[url_without_git], target_platform="2.0")

    assert result.value == {}
    assert tfs_client.received_branches == []


@pytest.mark.business_logic
def test_docker_fetcher_non_200_response_is_skipped(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """DockerFetcher пропускает URL, для которого get_file_content вернул не-200 статус без исключения."""
    tfs_client = _ContentFakeTFSClient(content=YAML_CONTENT.encode(), status_code=404)
    ctx = _make_context(parser_config, tfs_client, tmp_path)
    fetcher = DockerFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(urls=[_PROFILE_URL], target_platform="2.0")

    assert result.value == {}


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
