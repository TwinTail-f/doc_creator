"""
Общие тестовые фикстуры и заглушки для autodoc/tests/unit/parser/.

FakeTFSClient — заглушка-пустышка для реального TFSClient. Отдельные тестовые
модули наследуются от него и переопределяют только нужные методы, делая
тестовую поверхность минимальной и явной.
"""

import unittest.mock as mock
from pathlib import Path

import pytest
import requests

from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.models.component import Component
from autodoc.models.conan_variant import ConanVariant, ProfileBuild
from autodoc.models.release import Release
from autodoc.parser.pipeline.context import PipelineContext

# ---------------------------------------------------------------------------
# Фикстуры конфигурации / путей
# ---------------------------------------------------------------------------


@pytest.fixture
def parser_config() -> ParserConfigSchema:
    """Минимальная корректная ParserConfigSchema для юнит-тестов (без реальных сетевых вызовов)."""
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


@pytest.fixture
def resources_dir() -> Path:
    """Путь к общим тестовым ресурсам в tests/unit/parser/resources/."""
    return Path(__file__).parent / "resources"


# ---------------------------------------------------------------------------
# Фикстура контекста пайплайна (используется в steps/ и test_pipeline.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def parser_pipeline_context(
    parser_config: ParserConfigSchema, tmp_path: Path
) -> PipelineContext:
    """Полностью инициализированный PipelineContext на основе parser_config и tmp_path."""
    return PipelineContext(config=parser_config, tmp_dir=tmp_path)


# ---------------------------------------------------------------------------
# Фикстуры Component / Release (общие для steps/, enrichment/, test_pipeline.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def manifest_release() -> Release:
    """Release для openssl 1.0.0 на платформе 2.0 / канал 'tech'."""
    pb = ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")
    return Release(
        version="1.0.0",
        platform="2.0",
        channel="tech",
        git_url="DEP_Components/_git/contrib_openssl",
        profile_builds=[pb],
    )


@pytest.fixture
def manifest_component(manifest_release: Release) -> Component:
    """Component с именем 'openssl', оборачивающий manifest_release."""
    return Component(name="openssl", releases=[manifest_release])


# ---------------------------------------------------------------------------
# Фейковый клиент Artifactory (используется в тестах validation_step)
# ---------------------------------------------------------------------------


class _FakeArtifactoryClient:
    """Минимальная заглушка клиента Artifactory, записывающая вызовы head()."""

    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code
        self.called_urls: list[str] = []

    def head(self, url: str) -> requests.Response:
        self.called_urls.append(url)
        resp = requests.Response()
        resp.status_code = self.status_code
        return resp


@pytest.fixture
def artifactory_client() -> _FakeArtifactoryClient:
    """Фейковый клиент Artifactory по умолчанию (200 OK); тесты используют .__class__(status_code=N) для вариантов."""
    return _FakeArtifactoryClient(status_code=200)


class FakeTFSClient:
    """
    Заглушка-пустышка для TFSClient.

    Каждый метод возвращает безопасное пустое значение по умолчанию, чтобы
    подклассам нужно было переопределять только один-два метода, нужных для теста.

    Сигнатуры методов зеркалируют реальный TFSClient, поэтому код с проверкой
    типов может использовать FakeTFSClient как замену в тестах.
    """

    def get_file_content(
        self,
        items_url: str,
        path: str,
        branch: str,
        version_type=None,
    ) -> requests.Response:
        """Возвращает пустой ответ 200 по умолчанию."""
        resp = mock.MagicMock(spec=requests.Response)
        resp.status_code = 200
        resp.content = b""
        resp.text = ""
        resp.raise_for_status.return_value = None
        return resp

    def get_items(
        self,
        items_url: str,
        branch: str,
        recursion=None,
        version_type=None,
    ) -> list:
        """Возвращает пустой список элементов по умолчанию."""
        return []

    def download_properties(
        self,
        items_url: str,
        remote_path: str,
        branch: str,
        output_dir: str,
        version_type=None,
    ) -> None:
        """Ничего не делает по умолчанию (файлы не записываются)."""
