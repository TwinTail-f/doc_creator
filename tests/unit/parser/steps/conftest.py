"""Общие фикстуры для парсера step unit tests."""

import pytest

from autodoc.parser.fetchers.models.fetch_result import FetchResult


class _FakeFetcher:
    """Controllable fake fetcher for step unit tests."""

    def __init__(self, value: list, warnings: list[str] | None = None) -> None:
        self.value = value
        self.warnings: list[str] = warnings or []
        self.configure_called: bool = False
        self.fetch_called: bool = False

    def configure(self, ctx: object) -> None:
        """Record that configure was called."""
        self.configure_called = True

    def fetch(self, *args: object, **kwargs: object) -> FetchResult:
        """Return the controlled FetchResult."""
        self.fetch_called = True
        return FetchResult(value=self.value, warnings=self.warnings)


@pytest.fixture()
def make_fake_fetcher():
    """Factory fixture — returns a callable that creates _FakeFetcher instances."""
    return _FakeFetcher
