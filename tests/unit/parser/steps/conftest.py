"""Общие фикстуры для парсера step unit tests."""

import pytest

from autodoc.parser.fetchers.models.fetch_result import FetchResult


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
