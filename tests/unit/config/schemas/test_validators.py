"""
Юнит-тесты для собственных pydantic-валидаторов autodoc в схемах конфигурации.

Это тесты категории «собственный валидатор проекта» (не категория A из чек-листа
антипаттернов): здесь проверяется, что именно autodoc поднимает контролируемую
ошибку валидации на пустое значение конкретного поля, а не то, что pydantic вообще
умеет валидировать данные.
"""

import pytest
from pydantic import ValidationError

from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.config.schemas.parser_config import ParserConfigSchema

# valid_confluence_config / valid_parser_config — фикстуры из корневого
# tests/conftest.py, читающие tests/unit/config/resources/*.json. Локальные
# копии этих словарей здесь не заводим, чтобы не разъезжаться с каноническим
# источником при изменении обязательных полей схем.


@pytest.mark.contract
@pytest.mark.parametrize(
    "empty_url",
    [
        pytest.param("", id="empty-string"),
        pytest.param("   ", id="whitespace-only"),
    ],
)
def test_confluence_config_rejects_empty_url(
    valid_confluence_config: dict, empty_url: str,
) -> None:
    """ConfluenceConfigSchema._normalize_url поднимает ValidationError, если url пуст
    или состоит только из пробелов — собственная проверка autodoc
    (``if not v or not v.strip()``), а не встроенная в pydantic валидация строк."""
    payload = {**valid_confluence_config, "url": empty_url}
    with pytest.raises(ValidationError, match="url не может быть пустым"):
        ConfluenceConfigSchema(**payload)


@pytest.mark.business_logic
def test_confluence_config_strips_trailing_slash_from_url(valid_confluence_config: dict) -> None:
    """ConfluenceConfigSchema._normalize_url убирает завершающий слэш у непустого url."""
    payload = {**valid_confluence_config, "url": "https://confluence.example.com/"}
    config = ConfluenceConfigSchema(**payload)
    assert config.url == "https://confluence.example.com"


@pytest.mark.contract
def test_parser_config_rejects_empty_tfs_token(valid_parser_config: dict) -> None:
    """ParserConfigSchema.tfs_token_not_empty поднимает ValidationError на пустой tfs_token —
    собственная проверка autodoc (PAT для TFS не может быть пустой строкой)."""
    payload = {**valid_parser_config, "tfs_token": ""}
    with pytest.raises(ValidationError, match="tfs_token не может быть пустой строкой"):
        ParserConfigSchema(**payload)


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "field_name",
    [
        pytest.param("tfs_collection_url", id="tfs_collection_url"),
        pytest.param("artifactory_components_conan2_url", id="artifactory_components_conan2_url"),
        pytest.param("conan_config_url", id="conan_config_url"),
    ],
)
def test_parser_config_normalize_url_strips_whitespace_and_trailing_slash(
    valid_parser_config: dict, field_name: str,
) -> None:
    """ParserConfigSchema.normalize_url убирает пробелы по краям и завершающий слэш.

    Один и тот же валидатор навешан сразу на три поля (tfs_collection_url,
    artifactory_components_conan2_url, conan_config_url) — параметризуем по имени
    поля вместо трёх копий одного и того же теста.
    """
    payload = {**valid_parser_config, field_name: "  https://example.com/path/  "}
    config = ParserConfigSchema(**payload)
    assert getattr(config, field_name) == "https://example.com/path"
