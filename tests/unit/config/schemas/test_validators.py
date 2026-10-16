"""
Юнит-тесты для собственных pydantic-валидаторов в схемах конфигурации.
"""

import pytest
from pydantic import ValidationError

from autodoc.config.schemas.confluence_config import (
    ConfluenceConfigSchema,
    PublishAllConfig,
    StrategiesConfig,
)
from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.publisher.strategies.publish_plan import PUBLISH_PLAN


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
    или состоит только из пробелов
    """
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
    (PAT для TFS не может быть пустой строкой).
    """
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
    значения по умолчанию, включая дефолтный page_title у release.
    """
    config = ConfluenceConfigSchema(**valid_confluence_config)
    assert config.strategies.release.page_title == "Сборки компонентов Платформы"
    assert config.strategies.release.root_parent_id is None
    assert config.strategies.release.root_parent_name is None
    assert config.strategies.profile_centric.page_title == "Документация от профилей"
    assert config.strategies.profile_centric.root_parent_id is None
    assert config.strategies.profile_centric.root_parent_name is None
    assert config.strategies.passports.root_parent_id is None
    assert config.strategies.passports.root_parent_name is None
    assert config.strategies.kit_pinned.page_title == "Комплект для встраивания компонентов platform"
    assert config.strategies.kit_pinned.root_parent_id is None
    assert config.strategies.kit_pinned.root_parent_name is None
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
    теряется при частично заданной секции.
    """
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
        pytest.param("kit_pinned", id="kit_pinned"),
        pytest.param("kit_latest", id="kit_latest"),
    ],
)
def test_strategies_config_section_without_root_parent_raises(
    valid_confluence_config: dict,
    section_name: str,
) -> None:
    """
    Секция release/profile_centric/kit_pinned/kit_latest, присутствующая в
    конфиге без root_parent_name и root_parent_id (хотя бы с одним полем,
    например page_title) — невалидна.
    """
    payload = {**valid_confluence_config, "strategies": {section_name: {"page_title": "X"}}}
    with pytest.raises(ValidationError, match=f"strategies.{section_name}"):
        ConfluenceConfigSchema(**payload)


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "section_name, default_title",
    [
        pytest.param(
            "kit_pinned",
            "Комплект для встраивания компонентов platform",
            id="kit_pinned",
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
    Секция kit_pinned/kit_latest с заданным root_parent_name (без явного
    page_title) — валидна, дефолт page_title сохраняется.
    """
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
    считается явно указанной — root_parent_name/root_parent_id обязательны.
    """
    with pytest.raises(ValidationError, match="strategies.passports"):
        StrategiesConfig(**{"passports": {}})


@pytest.mark.business_logic
@pytest.mark.parametrize("section_name", ["release", "profile_centric", "kit_pinned", "kit_latest"])
@pytest.mark.parametrize(
    "bad_title",
    [
        pytest.param(None, id="none"),
        pytest.param("", id="empty"),
        pytest.param("   ", id="blank"),
    ],
)
def test_single_page_section_rejects_missing_or_blank_page_title(
    valid_confluence_config: dict,
    section_name: str,
    bad_title: str | None,
) -> None:
    """
    ``page_title`` секций release, profile_centric, kit_pinned и kit_latest обязан быть
    непустой строкой: ``None``, пустое значение и пробелы отклоняются при загрузке конфига.

    Проверка выполняется для любой из этих секций, независимо от ``publish_all.targets``:
    страница с пустым заголовком не публикуется ни одной командой.
    """
    payload = {
        **valid_confluence_config,
        "strategies": {section_name: {"root_parent_name": "X", "page_title": bad_title}},
    }

    with pytest.raises(ValidationError, match=f"strategies.{section_name}.page_title"):
        ConfluenceConfigSchema(**payload)


@pytest.mark.business_logic
def test_publish_all_targets_default_to_all_types_and_config_stays_valid_without_sections(
    valid_confluence_config: dict,
) -> None:
    """
    Без ключа ``publish_all`` выбраны все пять типов, но конфиг без секций с родителями валиден.

    Такой конфиг может использоваться только отдельными командами ``publish ...``, поэтому
    при загрузке схема на отсутствие родителей не реагирует. Полноту родителей для
    ``publish all`` показывает ``missing_root_parents_error()``: в нём перечислены все четыре
    секции, у которых родитель берётся из конфига, а ``profile_centric`` не упоминается —
    профильная страница публикуется дочерней к релизу.
    """
    config = ConfluenceConfigSchema(**valid_confluence_config)

    assert config.publish_all.targets == [
        "passports",
        "release",
        "profile_centric",
        "kit_pinned",
        "kit_latest",
    ]
    error = config.missing_root_parents_error()
    assert error is not None
    for section in ("passports", "release", "kit_pinned", "kit_latest"):
        assert f"strategies.{section}" in error
    assert "strategies.profile_centric" not in error


@pytest.mark.contract
@pytest.mark.parametrize(
    "targets, message",
    [
        pytest.param([], "at least 1 item", id="empty"),
        pytest.param(["release", "release"], "повторяющиеся типы: release", id="duplicates"),
        pytest.param(["profile_centric"], "добавьте 'release'", id="profile-without-release"),
        pytest.param(["release", "unknown"], "неизвестные типы: unknown", id="unknown-type"),
    ],
)
def test_publish_all_config_rejects_invalid_targets(targets: list[str], message: str) -> None:
    """
    ``PublishAllConfig`` отклоняет пустой список, повторы, неизвестные типы и ``profile_centric``
    без ``release``.

    Профильная страница публикуется дочерней к странице релиза, поэтому без ``release`` у неё
    нет родителя; ошибка выявляется при загрузке конфига, а не в середине публикации.
    """
    with pytest.raises(ValidationError, match=message):
        PublishAllConfig(targets=targets)


@pytest.mark.business_logic
def test_explicit_publish_all_requires_root_parent_for_selected_types_with_own_parent(
    valid_confluence_config: dict,
) -> None:
    """
    Если ``publish_all`` указан явно, у каждого выбранного типа обязан быть родитель в конфиге.

    Выбраны release, kit_pinned и kit_latest, а родитель задан только у release. Ошибка
    называет сразу обе недостающие секции и подсказывает, как её устранить.
    """
    payload = {
        **valid_confluence_config,
        "strategies": {"release": {"root_parent_name": "R"}},
        "publish_all": {"targets": ["release", "kit_pinned", "kit_latest"]},
    }

    with pytest.raises(ValidationError) as exc_info:
        ConfluenceConfigSchema(**payload)

    message = str(exc_info.value)
    assert "strategies.kit_pinned, strategies.kit_latest" in message
    assert "strategies.release" not in message


@pytest.mark.business_logic
def test_explicit_publish_all_does_not_require_sections_of_unselected_types(
    valid_confluence_config: dict,
) -> None:
    """
    Секции невыбранных типов в конфиге не нужны, а ``profile_centric`` родителя не требует.

    Выбраны release и profile_centric: родитель задан только у release, и конфиг валиден,
    потому что профильная страница получает родителем страницу релиза.
    """
    payload = {
        **valid_confluence_config,
        "strategies": {"release": {"root_parent_name": "R"}},
        "publish_all": {"targets": ["release", "profile_centric"]},
    }

    config = ConfluenceConfigSchema(**payload)

    assert config.missing_root_parents_error() is None


@pytest.mark.business_logic
def test_profile_centric_page_title_defaults_to_non_empty_title(
    valid_confluence_config: dict,
) -> None:
    """
    У профильной страницы есть непустой заголовок по умолчанию, поэтому ``publish all``
    не требует настраивать секцию ``profile_centric`` ради одного заголовка.
    """
    config = ConfluenceConfigSchema(**valid_confluence_config)

    assert config.strategies.profile_centric.page_title == "Документация от профилей"


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "key, parent_key",
    [
        pytest.param(node.key, node.parent_from, id=node.key)
        for node in PUBLISH_PLAN
        if node.parent_from is not None
    ],
)
def test_publish_all_targets_validation_follows_publish_plan_parents(
    key: str,
    parent_key: str,
) -> None:
    """Валидация ``targets`` обобщена по ``parent_from`` из ``PUBLISH_PLAN``.

    Для каждого узла плана с ``parent_from`` проверяются два сценария: выбор узла без
    его родителя отклоняется с подсказкой ``добавьте '<родитель>'``, а выбор узла
    вместе с родителем валиден. Тест параметризован планом, поэтому новый дочерний
    тип автоматически получает ту же проверку без правок валидатора.
    """
    with pytest.raises(ValidationError, match=f"добавьте '{parent_key}'"):
        PublishAllConfig(targets=[key])

    assert PublishAllConfig(targets=[parent_key, key]).targets == [parent_key, key]
