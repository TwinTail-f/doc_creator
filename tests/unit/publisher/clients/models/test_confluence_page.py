"""
Юнит-тесты для autodoc/publisher/clients/models/confluence_page.py.

Фокус — на ветках ``from_api``, не покрытых сценариями «страница найдена
целиком» в test_confluence_client.py: отсутствие/некорректность блока
``version`` и отсутствие ``ancestors``/``body``.
"""

import pytest

from autodoc.publisher.clients.models.confluence_page import ConfluencePage


@pytest.mark.contract
@pytest.mark.parametrize(
    "data, expected_version",
    [
        pytest.param(
            {"id": "123", "title": "My Page"},
            0,
            id="version_block_missing",
        ),
        pytest.param(
            {"id": "123", "title": "My Page", "version": {"number": "not-a-number"}},
            0,
            id="number_is_non_numeric",
        ),
        pytest.param(
            {"id": "123", "title": "My Page", "version": {"number": None}},
            0,
            id="number_is_none",
        ),
        pytest.param(
            {"id": "123", "title": "My Page", "version": {"number": 7}},
            7,
            id="valid_number_parsed",
        ),
    ],
)
def test_from_api_resolves_version_number(data: dict, expected_version: int) -> None:
    """
    from_api разбирает version.number, откатываясь на 0 при отсутствии ключа
    'version' (страница запрошена без expand=version) или при нечисловом/None
    значении number (перехват TypeError/ValueError при int(...)).
    """
    page = ConfluencePage.from_api(data)

    assert page.version == expected_version


@pytest.mark.contract
def test_from_api_defaults_ancestors_and_body_when_absent() -> None:
    """
    from_api возвращает пустые ancestor_ids/body_html, если соответствующие
    ключи в ответе API отсутствуют вовсе (не запрошены через expand).
    """
    page = ConfluencePage.from_api({"id": "123", "title": "My Page"})

    assert page.ancestor_ids == ()
    assert page.body_html == ""
