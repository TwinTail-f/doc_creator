"""
Тесты RootPageResolver. Приоритет источников и name/id внутри источника — в _resolve_root_parent;
таблица сценариев — TestNameIdPriorityMatrix, кросс-source кейсы — TestResolveRequiredParent.
"""

import logging
from typing import Any

import pytest

from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.exceptions import ConfigError, ConfluenceError
from autodoc.publisher.clients.models.confluence_page import ConfluencePage
from autodoc.publisher.page_manager.root_page_resolver import RootPageResolver

SPACE: str = "TEST"

# Метод резолвера + поля конфигурации, специфичные для passports/release/profile.
_PASSPORTS_METHOD: str = "resolve_passports_root"
_RELEASE_METHOD: str = "resolve_release_parent"
_PROFILE_METHOD: str = "resolve_profile_parent"
_PASSPORTS_CONFIG_NAME_FIELD: str = "passports_root_parent_name"
_PASSPORTS_CONFIG_ID_FIELD: str = "passports_root_parent_id"
_RELEASE_CONFIG_NAME_FIELD: str = "release_docs_root_parent_name"
_RELEASE_CONFIG_ID_FIELD: str = "release_docs_root_parent_id"
_PROFILE_CONFIG_NAME_FIELD: str = "profile_docs_root_parent_name"
_PROFILE_CONFIG_ID_FIELD: str = "profile_docs_root_parent_id"


def _make_mock_client(
    mocker: Any,
    known_pages: dict[str, str],
    known_ids: set[str] | None = None,
) -> Any:
    """Мок ``ConfluenceClient`` с управляемыми ``find_page``/``get_page``.

    known_ids по умолчанию — все id из known_pages.
    """
    existing_ids = known_ids if known_ids is not None else set(known_pages.values())
    ids_to_titles = {page_id: title for title, page_id in known_pages.items()}

    def _find_page(title: str, space: str | None = None) -> ConfluencePage | None:
        page_id = known_pages.get(title)
        if page_id is None:
            return None
        return ConfluencePage(id=page_id, title=title)

    def _get_page(page_id: str, expand: str = "") -> ConfluencePage:
        if page_id not in existing_ids:
            raise ConfluenceError(f"Страница с ID={page_id!r} не найдена")
        return ConfluencePage(id=page_id, title=ids_to_titles.get(page_id, page_id))

    mock_client = mocker.MagicMock()
    mock_client.find_page.side_effect = _find_page
    mock_client.get_page.side_effect = _get_page
    return mock_client


def _make_resolver(
    mocker: Any,
    minimal_confluence_config: dict,
    known_pages: dict[str, str] | None = None,
    known_ids: set[str] | None = None,
    **config_overrides: Any,
) -> tuple[RootPageResolver, Any]:
    """``RootPageResolver`` поверх мок-клиента и конфига с переопределениями полей."""
    config_dict = {**minimal_confluence_config, **config_overrides}
    config = ConfluenceConfigSchema(**config_dict)
    mock_client = _make_mock_client(mocker, known_pages or {}, known_ids)
    resolver = RootPageResolver(mock_client, config)
    return resolver, mock_client


# _find_page_id / _page_id_exists — сырые обёртки над клиентом, без логики приоритетов.
@pytest.mark.infrastructure
def test_find_page_id_found(mocker: Any, minimal_confluence_config: dict) -> None:
    """Страница найдена по имени — возвращается её ID."""
    resolver, _ = _make_resolver(
        mocker, minimal_confluence_config, known_pages={"Root Page": "100001"}
    )

    assert resolver._find_page_id("Root Page") == "100001"


@pytest.mark.infrastructure
def test_find_page_id_not_found_returns_none(mocker: Any, minimal_confluence_config: dict) -> None:
    """Страница не найдена по имени — возвращается None."""
    resolver, _ = _make_resolver(mocker, minimal_confluence_config, known_pages={})

    assert resolver._find_page_id("Missing Page") is None


@pytest.mark.infrastructure
def test_page_id_exists_true_for_known_id(mocker: Any, minimal_confluence_config: dict) -> None:
    """Известный ID — страница считается существующей."""
    resolver, _ = _make_resolver(mocker, minimal_confluence_config, known_ids={"100002"})

    assert resolver._page_id_exists("100002") is True


@pytest.mark.infrastructure
def test_page_id_exists_false_for_unknown_id(mocker: Any, minimal_confluence_config: dict) -> None:
    """Неизвестный ID — страница считается несуществующей."""
    resolver, _ = _make_resolver(mocker, minimal_confluence_config, known_ids=set())

    assert resolver._page_id_exists("100003") is False


# Smoke-тесты _resolve_root_parent напрямую; полная матрица — в TestNameIdPriorityMatrix.
@pytest.mark.business_logic
def test_cli_name_resolved_value_passed_through(
    mocker: Any, minimal_confluence_config: dict
) -> None:
    """CLI-имя резолвится — возвращается найденный ID."""
    resolver, _ = _make_resolver(
        mocker, minimal_confluence_config, known_pages={"Root Page": "100001"}
    )

    result = resolver._resolve_root_parent(
        "Root Page", None, None, None, "release_docs_root_parent"
    )

    assert result == "100001"


@pytest.mark.business_logic
def test_nothing_set_anywhere_raises_config_error_with_field_label(
    mocker: Any, minimal_confluence_config: dict
) -> None:
    """Ничего не задано — ConfigError с именем поля."""
    resolver, _ = _make_resolver(mocker, minimal_confluence_config)

    with pytest.raises(ConfigError) as exc_info:
        resolver._resolve_root_parent(None, None, None, None, "release_docs_root_parent")

    assert "release_docs_root_parent" in str(exc_info.value)


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
    """Приоритет CLI/конфиг для обязательных родителей (passports, release, profile)."""

    @pytest.mark.business_logic
    def test_cli_name_wins_over_config_id(
        self,
        mocker: Any,
        minimal_confluence_config: dict,
        method_name: str,
        config_name_field: str,
        config_id_field: str,
    ) -> None:
        """CLI-имя побеждает, даже если в конфиге задан ID."""
        resolver, _ = _make_resolver(
            mocker,
            minimal_confluence_config,
            known_pages={"CLI Parent": "200001"},
            **{config_id_field: "200002"},
        )

        result = getattr(resolver, method_name)("CLI Parent", None)

        assert result == "200001"

    @pytest.mark.business_logic
    def test_cli_name_unresolved_ignores_config_id_entirely(
        self,
        mocker: Any,
        minimal_confluence_config: dict,
        method_name: str,
        config_name_field: str,
        config_id_field: str,
    ) -> None:
        """CLI-имя не резолвится — отката на config id нет (источник «всё или ничего»)."""
        resolver, mock_client = _make_resolver(
            mocker,
            minimal_confluence_config,
            known_pages={},
            known_ids={"200003"},
            **{config_id_field: "200003"},
        )

        with pytest.raises(ConfigError):
            getattr(resolver, method_name)("Nonexistent Parent", None)

        mock_client.get_page.assert_not_called()

    @pytest.mark.business_logic
    def test_cli_value_set_silences_conflicting_config_no_warning(
        self,
        mocker: Any,
        minimal_confluence_config: dict,
        caplog: pytest.LogCaptureFixture,
        method_name: str,
        config_name_field: str,
        config_id_field: str,
    ) -> None:
        """CLI-значение задано — конфликт name/id в конфиге не проверяется и не логируется."""
        resolver, mock_client = _make_resolver(
            mocker,
            minimal_confluence_config,
            known_pages={"CLI Parent": "200001", "Config Parent": "200004"},
            **{config_name_field: "Config Parent", config_id_field: "200005"},
        )

        with caplog.at_level(logging.WARNING):
            result = getattr(resolver, method_name)("CLI Parent", None)

        assert result == "200001"
        mock_client.find_page.assert_called_once_with("CLI Parent", space=SPACE)
        assert not any(r.levelno == logging.WARNING for r in caplog.records)


def _build_resolver_for_source(
    mocker: Any,
    minimal_confluence_config: dict,
    source: str,
    name: str | None,
    id_value: str | None,
    config_name_field: str,
    config_id_field: str,
    known_pages: dict[str, str],
    known_ids: set[str] | None,
) -> tuple[RootPageResolver, Any, str | None, str | None]:
    """Резолвер + (call_name, call_id) для указанного источника: для CLI — сами
    name/id_value, для Config — они "вшиваются" в конфиг, а вызов идёт с (None, None)."""
    if source == "CLI":
        resolver, mock_client = _make_resolver(
            mocker,
            minimal_confluence_config,
            known_pages=known_pages,
            known_ids=known_ids,
        )
        return resolver, mock_client, name, id_value

    overrides: dict[str, str] = {}
    if name is not None:
        overrides[config_name_field] = name
    if id_value is not None:
        overrides[config_id_field] = id_value
    resolver, mock_client = _make_resolver(
        mocker,
        minimal_confluence_config,
        known_pages=known_pages,
        known_ids=known_ids,
        **overrides,
    )
    return resolver, mock_client, None, None


# Матрица приоритета name/id внутри одного источника: (name, id_value,
# known_pages, known_ids, expects_error, expected_result, expect_warning).
_NAME_ID_PRIORITY_CASES = [
    pytest.param(
        "Parent",
        None,
        {"Parent": "300001"},
        None,
        False,
        "300001",
        False,
        id="name_resolves_no_id",
    ),
    pytest.param(
        "Parent",
        "300001",
        {"Parent": "300001"},
        None,
        False,
        "300001",
        False,
        id="name_resolves_id_matches_no_warning",
    ),
    pytest.param(
        "Parent",
        "300002",
        {"Parent": "300001"},
        None,
        False,
        "300001",
        True,
        id="name_resolves_id_mismatches_warns_name_wins",
    ),
    pytest.param(
        "Parent",
        "300002",
        {},
        {"300002"},
        False,
        "300002",
        True,
        id="name_unresolved_valid_id_fallback_warns",
    ),
    pytest.param(
        "Parent",
        "300002",
        {},
        set(),
        True,
        None,
        False,
        id="name_unresolved_id_also_invalid_raises",
    ),
    pytest.param(
        "Parent",
        None,
        {},
        set(),
        True,
        None,
        False,
        id="name_unresolved_no_id_at_all_raises",
    ),
    pytest.param(
        None,
        "300001",
        {},
        {"300001"},
        False,
        "300001",
        False,
        id="only_id_valid",
    ),
    pytest.param(
        None,
        "300001",
        {},
        set(),
        True,
        None,
        False,
        id="only_id_invalid_raises",
    ),
    pytest.param(
        None,
        None,
        {},
        set(),
        True,
        None,
        False,
        id="nothing_set_raises",
    ),
]


@pytest.mark.parametrize(
    "method_name,config_name_field,config_id_field",
    [
        (_PASSPORTS_METHOD, _PASSPORTS_CONFIG_NAME_FIELD, _PASSPORTS_CONFIG_ID_FIELD),
        (_RELEASE_METHOD, _RELEASE_CONFIG_NAME_FIELD, _RELEASE_CONFIG_ID_FIELD),
        (_PROFILE_METHOD, _PROFILE_CONFIG_NAME_FIELD, _PROFILE_CONFIG_ID_FIELD),
    ],
    ids=["passports", "release", "profile"],
)
@pytest.mark.parametrize("source", ["CLI", "Config"])
class TestNameIdPriorityMatrix:
    """Матрица _NAME_ID_PRIORITY_CASES x 2 источника x 3 поля = 54 прогона.
    Кросс-source кейсы — в TestResolveRequiredParent."""

    @pytest.mark.business_logic
    @pytest.mark.parametrize(
        "name,id_value,known_pages,known_ids,expects_error,expected_result,expect_warning",
        _NAME_ID_PRIORITY_CASES,
    )
    def test_name_id_priority(
        self,
        mocker: Any,
        minimal_confluence_config: dict,
        caplog: pytest.LogCaptureFixture,
        method_name: str,
        config_name_field: str,
        config_id_field: str,
        source: str,
        name: str | None,
        id_value: str | None,
        known_pages: dict[str, str],
        known_ids: set[str] | None,
        expects_error: bool,
        expected_result: str | None,
        expect_warning: bool,
    ) -> None:
        resolver, mock_client, call_name, call_id = _build_resolver_for_source(
            mocker,
            minimal_confluence_config,
            source,
            name,
            id_value,
            config_name_field,
            config_id_field,
            known_pages,
            known_ids,
        )

        if expects_error:
            with pytest.raises(ConfigError):
                getattr(resolver, method_name)(call_name, call_id)
            return

        with caplog.at_level(logging.WARNING):
            result = getattr(resolver, method_name)(call_name, call_id)

        assert result == expected_result
        if name is None:
            mock_client.find_page.assert_not_called()

        warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        if expect_warning:
            assert any(source in w for w in warnings)
        else:
            assert warnings == []


@pytest.mark.business_logic
def test_resolve_profile_parent_reads_its_own_config_fields(
    mocker: Any, minimal_confluence_config: dict
) -> None:
    """Читает profile_docs_root_parent_*, а не release_docs_root_parent_*."""
    resolver, mock_client = _make_resolver(
        mocker,
        minimal_confluence_config,
        known_pages={"Profile Parent Page": "400001"},
        profile_docs_root_parent_name="Profile Parent Page",
        release_docs_root_parent_name="Release Parent Page",
    )

    result = resolver.resolve_profile_parent(None, None)

    assert result == "400001"
    mock_client.find_page.assert_called_once_with("Profile Parent Page", space=SPACE)


# resolve_single_page_parent: диспетчеризация по strategy_type
@pytest.mark.business_logic
@pytest.mark.parametrize(
    "strategy_type, patched_method_name, return_value",
    [
        pytest.param("release", "resolve_release_parent", "400002", id="release"),
        pytest.param(
            "profile_centric", "resolve_profile_parent", "400003", id="profile_centric"
        ),
        pytest.param(
            "some_other_strategy",
            "resolve_release_parent",
            "400002",
            id="unknown-falls-back-to-release",
        ),
    ],
)
def test_resolve_single_page_parent_delegates_by_strategy_type(
    mocker: Any,
    minimal_confluence_config: dict,
    strategy_type: str,
    patched_method_name: str,
    return_value: str,
) -> None:
    """resolve_single_page_parent() делегирует resolve_release_parent/resolve_profile_parent по strategy_type, с release как значением по умолчанию для неизвестных типов."""
    resolver, _ = _make_resolver(mocker, minimal_confluence_config)
    mock_method = mocker.patch.object(resolver, patched_method_name, return_value=return_value)

    result = resolver.resolve_single_page_parent(strategy_type, "Some Name", None)

    assert result == return_value
    mock_method.assert_called_once_with("Some Name", None)


# resolve_root_pages: паспорта + релиз
@pytest.mark.business_logic
def test_happy_path_returns_both_resolved_ids(mocker: Any, minimal_confluence_config: dict) -> None:
    """Оба значения резолвятся, возвращается кортеж (паспорта, релиз)."""
    resolver, _ = _make_resolver(
        mocker,
        minimal_confluence_config,
        known_pages={"Passports Root": "400004", "Release Parent": "400002"},
    )

    resolved_root, resolved_release_parent = resolver.resolve_root_pages(
        "Passports Root", None, "Release Parent", None
    )

    assert resolved_root == "400004"
    assert resolved_release_parent == "400002"


@pytest.mark.business_logic
def test_missing_passports_root_propagates_config_error(
    mocker: Any, minimal_confluence_config: dict
) -> None:
    """Отсутствие корневой страницы паспортов пробрасывает ConfigError."""
    resolver, _ = _make_resolver(mocker, minimal_confluence_config)

    with pytest.raises(ConfigError):
        resolver.resolve_root_pages(None, None, None, None)
