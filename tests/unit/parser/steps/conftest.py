"""Общие фикстуры для парсера step unit tests."""

from pathlib import Path

import pytest
import requests

from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.parser.fetchers.models.fetch_result import FetchResult
from autodoc.parser.pipeline.context import PipelineContext


# Фикстура контекста пайплайна (используется только в steps/*)
@pytest.fixture
def parser_pipeline_context(parser_config: ParserConfigSchema, tmp_path: Path) -> PipelineContext:
    """Полностью инициализированный PipelineContext на основе parser_config и tmp_path."""
    return PipelineContext(config=parser_config, tmp_dir=tmp_path)


# Фейковый клиент Artifactory (используется в тестах validation_step)
class FakeArtifactoryClient:
    """Минимальная заглушка клиента Artifactory, записывающая вызовы check_url().

    Код статуса по умолчанию фиксирован (``status_code``), но определяется через
    переопределяемый ``_status_for()``, чтобы подклассы с URL-зависимой логикой
    (см. ``_MixedClient`` в test_validation_step.py) могли переиспользовать
    ``check_url()`` целиком, не копируя сборку ``requests.Response``.
    """

    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code
        self.called_urls: list[str] = []

    def check_url(self, url: str) -> requests.Response:
        self.called_urls.append(url)
        resp = requests.Response()
        resp.status_code = self._status_for(url)
        return resp

    def _status_for(self, url: str) -> int:
        """Возвращает HTTP-код статуса для данного URL. По умолчанию — фиксированный ``self.status_code``."""
        return self.status_code


class _FakeFetcher:
    """Управляемый фейковый fetcher для юнит-тестов шагов."""

    def __init__(self, value: list, warnings: list[str] | None = None) -> None:
        self.value = value
        self.warnings: list[str] = warnings or []
        self.configure_called: bool = False
        self.fetch_called: bool = False

    def configure(self, ctx: object) -> None:
        """Фиксирует факт вызова configure()."""
        self.configure_called = True

    def fetch(self, *args: object, **kwargs: object) -> FetchResult:
        """Возвращает заранее заданный FetchResult."""
        self.fetch_called = True
        return FetchResult(value=self.value, warnings=self.warnings)


@pytest.fixture()
def make_fake_fetcher():
    """Фабрика-фикстура — возвращает callable, создающий экземпляры _FakeFetcher."""
    return _FakeFetcher
