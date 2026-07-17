"""
Юнит-тесты для autodoc/publisher/clients/models/confluence_page.py.

Фокус — на ветках ``from_api``, не покрытых сценариями «страница найдена
целиком» в test_confluence_client.py: отсутствие/некорректность блока
``version`` и отсутствие ``ancestors``/``body``.
"""

import pytest

from autodoc.publisher.clients.models.confluence_page import ConfluencePage


@pytest.mark.business_logic
def test_from_api_defaults_version_to_zero_when_version_block_missing() -> None:
    """from_api проставляет version=0, если ключ 'version' отсутствует в ответе API
    (страница запрошена без expand=version)."""
    page = ConfluencePage.from_api({"id": "123", "title": "My Page"})

    assert page.version == 0


@pytest.mark.business_logic
def test_from_api_defaults_version_to_zero_when_number_is_non_numeric() -> None:
    """from_api перехватывает TypeError/ValueError при int(version.number) и
    откатывается на version=0, если Confluence вернул нечисловое значение."""
    page = ConfluencePage.from_api(
        {"id": "123", "title": "My Page", "version": {"number": "not-a-number"}}
    )

    assert page.version == 0


@pytest.mark.business_logic
def test_from_api_defaults_version_to_zero_when_number_is_none() -> None:
    """from_api откатывается на version=0, если version.number явно равен None."""
    page = ConfluencePage.from_api({"id": "123", "title": "My Page", "version": {"number": None}})

    assert page.version == 0


@pytest.mark.business_logic
def test_from_api_parses_valid_version_number() -> None:
    """from_api корректно разбирает валидный числовой version.number."""
    page = ConfluencePage.from_api({"id": "123", "title": "My Page", "version": {"number": 7}})

    assert page.version == 7


@pytest.mark.business_logic
def test_from_api_defaults_ancestors_and_body_when_absent() -> None:
    """from_api возвращает пустые ancestor_ids/body_html, если соответствующие
    ключи в ответе API отсутствуют вовсе (не запрошены через expand)."""
    page = ConfluencePage.from_api({"id": "123", "title": "My Page"})

    assert page.ancestor_ids == ()
    assert page.body_html == ""
