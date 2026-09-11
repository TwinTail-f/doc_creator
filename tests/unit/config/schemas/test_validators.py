"""
Юнит-тесты для собственных pydantic-валидаторов в схемах конфигурации.
"""

import pytest
from pydantic import ValidationError

from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema, StrategiesConfig
from autodoc.config.schemas.parser_config import ParserConfigSchema


@pytest.mark.contract
@pytest.mark.parametrize(
    "empty_url",
    [
        pytest.param("", id="empty-string"),
        pytest.param("   ", id="whitespace-only"),
    ],
)
def test_confluence_config_rejects_empty_url(
    valid_confluence_config: dict,
    empty_url: str,
) -> None:
    """
    ConfluenceConfigSchema._normalize_url поднимает ValidationError, если url пуст
    или состоит только из пробелов"""
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
    """
    ParserConfigSchema.tfs_token_not_empty поднимает ValidationError на пустой tfs_token
    (PAT для TFS не может быть пустой строкой)."""
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
    valid_parser_config: dict,
    field_name: str,
) -> None:
    """ParserConfigSchema.normalize_url убирает пробелы по краям и завершающий слэш."""
    payload = {**valid_parser_config, field_name: "  https://example.com/path/  "}
    config = ParserConfigSchema(**payload)
    assert getattr(config, field_name) == "https://example.com/path"


@pytest.mark.business_logic
def test_strategies_config_absent_uses_defaults_for_all_sections(
    valid_confluence_config: dict,
) -> None:
    """
    Если ключ strategies в конфиге отсутствует вовсе — все три секции берут
    значения по умолчанию, включая дефолтный page_title у release."""
    config = ConfluenceConfigSchema(**valid_confluence_config)
    assert config.strategies.release.page_title == "Сборки компонентов Платформы"
    assert config.strategies.release.root_parent_id is None
    assert config.strategies.release.root_parent_name is None
    assert config.strategies.profile_centric.page_title is None
    assert config.strategies.profile_centric.root_parent_id is None
    assert config.strategies.profile_centric.root_parent_name is None
    assert config.strategies.passports.root_parent_id is None
    assert config.strategies.passports.root_parent_name is None
    assert config.strategies.kit_fixed.page_title == "Комплект для встраивания компонентов platform"
    assert config.strategies.kit_fixed.root_parent_id is None
    assert config.strategies.kit_fixed.root_parent_name is None
    assert (
        config.strategies.kit_latest.page_title
        == "Встраивание последних версий компонентов платформы"
    )
    assert config.strategies.kit_latest.root_parent_id is None
    assert config.strategies.kit_latest.root_parent_name is None


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "section_fields",
    [
        pytest.param({"root_parent_name": "X"}, id="name-only"),
        pytest.param({"root_parent_id": "123"}, id="id-only"),
        pytest.param({"root_parent_name": "X", "root_parent_id": "123"}, id="both"),
    ],
)
def test_strategies_config_release_section_with_root_parent_keeps_default_page_title(
    valid_confluence_config: dict,
    section_fields: dict,
) -> None:
    """
    Секция release с заданным root_parent_name или root_parent_id (без явного
    page_title) — валидна, заданное поле сохраняется как есть, второе из пары
    (root_parent_name/root_parent_id) остаётся None, а дефолт page_title не
    теряется при частично заданной секции (см. раздел 2.3 спеки)."""
    payload = {**valid_confluence_config, "strategies": {"release": section_fields}}
    config = ConfluenceConfigSchema(**payload)

    release = config.strategies.release
    assert release.page_title == "Сборки компонентов Платформы"
    assert release.root_parent_name == section_fields.get("root_parent_name")
    assert release.root_parent_id == section_fields.get("root_parent_id")


@pytest.mark.contract
@pytest.mark.parametrize(
    "section_name",
    [
        pytest.param("release", id="release"),
        pytest.param("profile_centric", id="profile_centric"),
        pytest.param("kit_fixed", id="kit_fixed"),
        pytest.param("kit_latest", id="kit_latest"),
    ],
)
def test_strategies_config_section_without_root_parent_raises(
    valid_confluence_config: dict,
    section_name: str,
) -> None:
    """
    Секция release/profile_centric/kit_fixed/kit_latest, присутствующая в
    конфиге без root_parent_name и root_parent_id (хотя бы с одним полем,
    например page_title) — невалидна."""
    payload = {**valid_confluence_config, "strategies": {section_name: {"page_title": "X"}}}
    with pytest.raises(ValidationError, match=f"strategies.{section_name}"):
        ConfluenceConfigSchema(**payload)


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "section_name, default_title",
    [
        pytest.param(
            "kit_fixed",
            "Комплект для встраивания компонентов platform",
            id="kit_fixed",
        ),
        pytest.param(
            "kit_latest",
            "Встраивание последних версий компонентов платформы",
            id="kit_latest",
        ),
    ],
)
def test_strategies_config_kit_sections_with_root_parent_keep_default_page_title(
    valid_confluence_config: dict,
    section_name: str,
    default_title: str,
) -> None:
    """
    Секция kit_fixed/kit_latest с заданным root_parent_name (без явного
    page_title) — валидна, дефолт page_title сохраняется."""
    payload = {
        **valid_confluence_config,
        "strategies": {section_name: {"root_parent_name": "X"}},
    }
    config = ConfluenceConfigSchema(**payload)

    section = getattr(config.strategies, section_name)
    assert section.page_title == default_title
    assert section.root_parent_name == "X"


@pytest.mark.contract
def test_strategies_config_passports_empty_section_raises() -> None:
    """
    Секция passports, присутствующая в конфиге как пустой словарь, всё равно
    считается явно указанной — root_parent_name/root_parent_id обязательны."""
    with pytest.raises(ValidationError, match="strategies.passports"):
        StrategiesConfig(**{"passports": {}})


@pytest.mark.business_logic
def test_strategies_config_explicit_none_page_title_overrides_class_default(
    valid_confluence_config: dict,
) -> None:
    """
    Явный page_title=None в секции release побеждает дефолт класса
    ReleaseDocsFields.page_title."""
    payload = {
        **valid_confluence_config,
        "strategies": {"release": {"root_parent_name": "X", "page_title": None}},
    }
    config = ConfluenceConfigSchema(**payload)
    assert config.strategies.release.page_title is None
