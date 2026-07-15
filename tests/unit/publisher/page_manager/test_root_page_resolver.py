"""
Тесты для autodoc.publisher.page_manager.root_page_resolver.RootPageResolver.

Стратегия тестирования:
- RootPageResolver тестируется в полной изоляции от ConfluenceClient: его
  роль играет mocker.MagicMock, у которого find_page() настроен возвращать
  реальный ConfluencePage для известных заголовков и None для неизвестных.
  Это позволяет каждому тесту напрямую проверять обе ветки — «найдено» и
  «не найдено», — не затрагивая вопросы HTTP/транспорта (они относятся к
  test_confluence_transport.py).
- Фикстура minimal_confluence_config берётся из tests/unit/publisher/conftest.py.
"""

from __future__ import annotations

from typing import Any

import pytest

from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.exceptions import ConfigError
from autodoc.publisher.clients.models.confluence_page import ConfluencePage
from autodoc.publisher.page_manager.root_page_resolver import RootPageResolver

SPACE: str = "TEST"


def _make_mock_client(mocker: Any, known_pages: dict[str, str]) -> Any:
    """
    Создаёт мок ``ConfluenceClient`` с управляемым поведением ``find_page``.

    Args:
        mocker: Фикстура pytest-mock.
        known_pages: Отображение ``{title: page_id}`` — страницы, которые
                     find_page должен "находить"; заголовки вне этого
                     отображения приводят к возврату ``None``.

    Returns:
        Мок клиента с реализацией ``find_page(title, space=...)``.
    """

    def _find_page(title: str, space: str | None = None) -> ConfluencePage | None:
        page_id = known_pages.get(title)
        if page_id is None:
            return None
        return ConfluencePage(id=page_id, title=title)

    mock_client = mocker.MagicMock()
    mock_client.find_page.side_effect = _find_page
    return mock_client


def _make_resolver(
    mocker: Any,
    minimal_confluence_config: dict,
    known_pages: dict[str, str] | None = None,
    **config_overrides: Any,
) -> tuple[RootPageResolver, Any]:
    """
    Создаёт ``RootPageResolver`` поверх мок-клиента и конфигурации с переопределениями.

    Args:
        mocker: Фикстура pytest-mock.
        minimal_confluence_config: Базовый словарь конфигурации.
        known_pages: Страницы, которые должен "находить" мок-клиент.
        **config_overrides: Поля, переопределяющие значения из базового словаря.

    Returns:
        Пара ``(resolver, mock_client)``.
    """
    config_dict = {**minimal_confluence_config, **config_overrides}
    config = ConfluenceConfigSchema(**config_dict)
    mock_client = _make_mock_client(mocker, known_pages or {})
    resolver = RootPageResolver(mock_client, config)
    return resolver, mock_client


class TestResolvePageId:
    """Тесты общего низкоуровневого метода resolve_page_id.

    resolve_page_id — get-подобный метод: имя ищется в Confluence (план А),
    а если имя не задано, без похода в Confluence возвращается ``default``
    (план Б). За решение о том, что делать с пустым результатом (в т.ч.
    поднимать ли ConfigError с учётом конкретного поля конфигурации),
    отвечает вызывающий код — см. TestResolveOrRaise.
    """

    @pytest.mark.business_logic
    def test_name_found_returns_page_id(self, mocker: Any, minimal_confluence_config: dict) -> None:
        """Если страница с заданным именем найдена — возвращается её ID."""
        resolver, _ = _make_resolver(
            mocker, minimal_confluence_config, known_pages={"Root Page": "page-1"}
        )

        result = resolver.resolve_page_id("Root Page", None)

        assert result == "page-1"

    @pytest.mark.business_logic
    def test_name_not_found_raises_config_error(self, mocker: Any, minimal_confluence_config: dict) -> None:
        """Если страница с заданным именем не найдена — поднимается ConfigError с описанием поиска."""
        resolver, _ = _make_resolver(mocker, minimal_confluence_config, known_pages={})

        with pytest.raises(ConfigError) as exc_info:
            resolver.resolve_page_id("Missing Page", None)

        message = str(exc_info.value)
        assert "Missing Page" in message
        assert minimal_confluence_config["space"] in message

    @pytest.mark.business_logic
    def test_no_name_returns_default_without_lookup(
        self, mocker: Any, minimal_confluence_config: dict
    ) -> None:
        """Если имя не задано — возвращается default без обращения к find_page."""
        resolver, mock_client = _make_resolver(mocker, minimal_confluence_config)

        result = resolver.resolve_page_id(None, "explicit-id")

        assert result == "explicit-id"
        mock_client.find_page.assert_not_called()

    @pytest.mark.business_logic
    def test_nothing_set_returns_none_without_lookup(
        self, mocker: Any, minimal_confluence_config: dict
    ) -> None:
        """Если ни имя, ни default не заданы — возвращается None, ConfigError не поднимается.

        resolve_page_id сам по себе не решает, обязательно ли значение —
        это забота конкретного поля конфигурации (см. TestResolveOrRaise).
        """
        resolver, mock_client = _make_resolver(mocker, minimal_confluence_config)

        result = resolver.resolve_page_id(None, None)

        assert result is None
        mock_client.find_page.assert_not_called()


class TestResolveOrRaise:
    """Тесты _resolve_or_raise — обёртки, требующей непустой результат."""

    @pytest.mark.business_logic
    def test_resolved_value_passed_through(
        self, mocker: Any, minimal_confluence_config: dict
    ) -> None:
        """Если resolve_page_id вернул значение — оно возвращается как есть."""
        resolver, _ = _make_resolver(
            mocker, minimal_confluence_config, known_pages={"Root Page": "page-1"}
        )

        result = resolver._resolve_or_raise("Root Page", None, "release_docs_root_parent")

        assert result == "page-1"

    @pytest.mark.business_logic
    def test_nothing_set_raises_config_error_with_field_label(
        self, mocker: Any, minimal_confluence_config: dict
    ) -> None:
        """Если ни имя, ни default не заданы — поднимается ConfigError с именем поля."""
        resolver, _ = _make_resolver(mocker, minimal_confluence_config)

        with pytest.raises(ConfigError) as exc_info:
            resolver._resolve_or_raise(None, None, "release_docs_root_parent")

        assert "release_docs_root_parent" in str(exc_info.value)


# Каждый набор описывает: имя метода резолвера, а также имена CLI-совместимых
# полей конфигурации, специфичных для passports/release/profile.
_PASSPORTS_METHOD: str = "resolve_passports_root"
_RELEASE_METHOD: str = "resolve_release_parent"
_PROFILE_METHOD: str = "resolve_profile_parent"
_PASSPORTS_CONFIG_NAME_FIELD: str = "passports_root_parent_name"
_PASSPORTS_CONFIG_ID_FIELD: str = "passports_root_parent_id"
_RELEASE_CONFIG_NAME_FIELD: str = "release_docs_root_parent_name"
_RELEASE_CONFIG_ID_FIELD: str = "release_docs_root_parent_id"
_PROFILE_CONFIG_NAME_FIELD: str = "profile_docs_root_parent_name"
_PROFILE_CONFIG_ID_FIELD: str = "profile_docs_root_parent_id"


@pytest.mark.parametrize(
    "method_name,config_name_field,config_id_field",
    [
        (_PASSPORTS_METHOD, _PASSPORTS_CONFIG_NAME_FIELD, _PASSPORTS_CONFIG_ID_FIELD),
        (_RELEASE_METHOD, _RELEASE_CONFIG_NAME_FIELD, _RELEASE_CONFIG_ID_FIELD),
        (_PROFILE_METHOD, _PROFILE_CONFIG_NAME_FIELD, _PROFILE_CONFIG_ID_FIELD),
    ],
    ids=["passports", "release", "profile"],
)
class TestResolveRequiredParent:
    """Общая логика приоритета CLI/конфиг и имя/ID для обязательных родителей (passports, release и profile)."""

    @pytest.mark.business_logic
    def test_cli_name_wins_over_config_id(
        self,
        mocker: Any,
        minimal_confluence_config: dict,
        method_name: str,
        config_name_field: str,
        config_id_field: str,
    ) -> None:
        """CLI-имя побеждает целиком, даже если в конфиге задан ID."""
        resolver, _ = _make_resolver(
            mocker,
            minimal_confluence_config,
            known_pages={"CLI Parent": "cli-page-id"},
            **{config_id_field: "config-id-should-be-ignored"},
        )

        result = getattr(resolver, method_name)("CLI Parent", None)

        assert result == "cli-page-id"

    @pytest.mark.business_logic
    def test_cli_name_not_found_raises(
        self,
        mocker: Any,
        minimal_confluence_config: dict,
        method_name: str,
        config_name_field: str,
        config_id_field: str,
    ) -> None:
        """CLI-имя не найдено — поднимается ConfigError, даже если в конфиге есть запасной ID."""
        resolver, _ = _make_resolver(
            mocker,
            minimal_confluence_config,
            known_pages={},
            **{config_id_field: "config-id-should-be-ignored"},
        )

        with pytest.raises(ConfigError):
            getattr(resolver, method_name)("Nonexistent Parent", None)

    @pytest.mark.business_logic
    def test_only_cli_id_returns_id_without_lookup(
        self,
        mocker: Any,
        minimal_confluence_config: dict,
        method_name: str,
        config_name_field: str,
        config_id_field: str,
    ) -> None:
        """Только CLI-ID задан — возвращается сам ID, без вызова find_page."""
        resolver, mock_client = _make_resolver(mocker, minimal_confluence_config)

        result = getattr(resolver, method_name)(None, "cli-id-only")

        assert result == "cli-id-only"
        mock_client.find_page.assert_not_called()

    @pytest.mark.business_logic
    def test_config_name_used_when_no_cli(
        self,
        mocker: Any,
        minimal_confluence_config: dict,
        method_name: str,
        config_name_field: str,
        config_id_field: str,
    ) -> None:
        """CLI-значения не заданы, в конфиге есть имя — оно ищется и возвращается его ID."""
        resolver, mock_client = _make_resolver(
            mocker,
            minimal_confluence_config,
            known_pages={"Config Parent": "config-page-id"},
            **{config_name_field: "Config Parent"},
        )

        result = getattr(resolver, method_name)(None, None)

        assert result == "config-page-id"
        mock_client.find_page.assert_called_once_with("Config Parent", space=SPACE)

    @pytest.mark.business_logic
    def test_config_id_only_returns_id_without_lookup(
        self,
        mocker: Any,
        minimal_confluence_config: dict,
        method_name: str,
        config_name_field: str,
        config_id_field: str,
    ) -> None:
        """CLI-значения не заданы, в конфиге только ID — он возвращается без поиска."""
        resolver, mock_client = _make_resolver(
            mocker,
            minimal_confluence_config,
            **{config_id_field: "config-id-only"},
        )

        result = getattr(resolver, method_name)(None, None)

        assert result == "config-id-only"
        mock_client.find_page.assert_not_called()

    @pytest.mark.business_logic
    def test_nothing_set_anywhere_raises_config_error(
        self,
        mocker: Any,
        minimal_confluence_config: dict,
        method_name: str,
        config_name_field: str,
        config_id_field: str,
    ) -> None:
        """Ничего не задано нигде — поднимается ConfigError (родитель обязателен)."""
        resolver, _ = _make_resolver(mocker, minimal_confluence_config)

        with pytest.raises(ConfigError):
            getattr(resolver, method_name)(None, None)


@pytest.mark.business_logic
def test_resolve_profile_parent_reads_its_own_config_fields(
    mocker: Any, minimal_confluence_config: dict
) -> None:
    """resolve_profile_parent читает profile_docs_root_parent_*, а не release_docs_root_parent_*."""
    resolver, mock_client = _make_resolver(
        mocker,
        minimal_confluence_config,
        known_pages={"Profile Parent Page": "profile-page-id"},
        profile_docs_root_parent_name="Profile Parent Page",
        release_docs_root_parent_name="Release Parent Page",
    )

    result = resolver.resolve_profile_parent(None, None)

    assert result == "profile-page-id"
    mock_client.find_page.assert_called_once_with("Profile Parent Page", space=SPACE)


class TestResolveSinglePageParent:
    """Диспетчеризация по strategy_type в resolve_single_page_parent."""

    @pytest.mark.business_logic
    def test_release_strategy_delegates_to_resolve_release_parent(
        self, mocker: Any, minimal_confluence_config: dict
    ) -> None:
        """strategy_type='release' делегирует в resolve_release_parent."""
        resolver, _ = _make_resolver(mocker, minimal_confluence_config)
        mock_release = mocker.patch.object(resolver, "resolve_release_parent", return_value="release-id")

        result = resolver.resolve_single_page_parent("release", "Some Name", None)

        assert result == "release-id"
        mock_release.assert_called_once_with("Some Name", None)

    @pytest.mark.business_logic
    def test_profile_centric_strategy_delegates_to_resolve_profile_parent(
        self, mocker: Any, minimal_confluence_config: dict
    ) -> None:
        """strategy_type='profile_centric' делегирует в resolve_profile_parent."""
        resolver, _ = _make_resolver(mocker, minimal_confluence_config)
        mock_profile = mocker.patch.object(resolver, "resolve_profile_parent", return_value="profile-id")

        result = resolver.resolve_single_page_parent("profile_centric", "Some Name", None)

        assert result == "profile-id"
        mock_profile.assert_called_once_with("Some Name", None)

    @pytest.mark.business_logic
    def test_unknown_strategy_type_falls_through_to_release(
        self, mocker: Any, minimal_confluence_config: dict
    ) -> None:
        """Любой strategy_type, отличный от 'profile_centric', намеренно попадает в release-путь по умолчанию."""
        resolver, _ = _make_resolver(mocker, minimal_confluence_config)
        mock_release = mocker.patch.object(resolver, "resolve_release_parent", return_value="release-id")

        result = resolver.resolve_single_page_parent("some_other_strategy", "Some Name", None)

        assert result == "release-id"
        mock_release.assert_called_once_with("Some Name", None)


class TestResolveRootPages:
    """Комбинированное разрешение корневых страниц паспортов и релиза."""

    @pytest.mark.business_logic
    def test_happy_path_returns_both_resolved_ids(
        self, mocker: Any, minimal_confluence_config: dict
    ) -> None:
        """Оба значения успешно резолвятся и возвращаются в виде кортежа (паспорта, релиз)."""
        resolver, _ = _make_resolver(
            mocker,
            minimal_confluence_config,
            known_pages={"Passports Root": "passports-id", "Release Parent": "release-id"},
        )

        resolved_root, resolved_release_parent = resolver.resolve_root_pages(
            "Passports Root", None, "Release Parent", None
        )

        assert resolved_root == "passports-id"
        assert resolved_release_parent == "release-id"

    @pytest.mark.business_logic
    def test_missing_passports_root_propagates_config_error(
        self, mocker: Any, minimal_confluence_config: dict
    ) -> None:
        """Отсутствие обязательной корневой страницы паспортов пробрасывает ConfigError наружу."""
        resolver, _ = _make_resolver(mocker, minimal_confluence_config)

        with pytest.raises(ConfigError):
            resolver.resolve_root_pages(None, None, None, None)
