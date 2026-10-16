"""
Тесты RootPageResolver. Приоритет источников и name/id внутри источника — в _resolve_root_parent;
таблица сценариев — TestNameIdPriorityMatrix, кросс-source кейсы — TestResolveRequiredParent.
"""

import logging
from collections.abc import Callable
from typing import Any

import pytest
from pytest_mock import MockerFixture

from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.exceptions import ConfigError, ConfluenceError
from autodoc.publisher.clients.models.confluence_page import ConfluencePage
from autodoc.publisher.page_manager.root_page_resolver import RootPageResolver

SPACE: str = "TEST"


def _call_passports(resolver: RootPageResolver, name: str | None, page_id: str | None) -> str:
    return resolver.resolve_parent("passports", name, page_id)


def _call_release(resolver: RootPageResolver, name: str | None, page_id: str | None) -> str:
    return resolver.resolve_parent("release", name, page_id)


def _call_profile(resolver: RootPageResolver, name: str | None, page_id: str | None) -> str:
    return resolver.resolve_parent("profile_centric", name, page_id)


# section: имя секции в strategies (совпадает с "profile" для читаемости id теста,
# хотя сама секция в конфиге называется profile_centric — см. _SECTION_CONFIG_KEY)
_CALLERS: dict[str, Callable[[RootPageResolver, str | None, str | None], str]] = {
    "passports": _call_passports,
    "release": _call_release,
    "profile": _call_profile,
}
_SECTION_CONFIG_KEY: dict[str, str] = {
    "passports": "passports",
    "release": "release",
    "profile": "profile_centric",
}


def _config_overrides(
    section: str, *, name: str | None = None, id_value: str | None = None
) -> dict:
    """
    Строит overrides для _make_resolver(): {"strategies": {<config_key>: {...}}}.
    Пропускает поля, равные None, чтобы не перезаписывать root_parent_id/name пустым
    значением там, где вызывающий тест их не задавал.
    """
    fields = {}
    if name is not None:
        fields["root_parent_name"] = name
    if id_value is not None:
        fields["root_parent_id"] = id_value
    return {"strategies": {_SECTION_CONFIG_KEY[section]: fields}} if fields else {}


def _make_mock_client(
    mocker: MockerFixture,
    known_pages: dict[str, str],
    known_ids: set[str] | None = None,
) -> Any:
    """
    Мок ``ConfluenceClient`` с управляемыми ``find_page``/``get_page``.

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
    mocker: MockerFixture,
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
def test_find_page_id_found(mocker: MockerFixture, minimal_confluence_config: dict) -> None:
    """Страница найдена по имени — возвращается её ID."""
    resolver, _ = _make_resolver(
        mocker, minimal_confluence_config, known_pages={"Root Page": "100001"}
    )

    assert resolver._find_page_id("Root Page") == "100001"


@pytest.mark.infrastructure
def test_find_page_id_not_found_returns_none(
    mocker: MockerFixture, minimal_confluence_config: dict
) -> None:
    """Страница не найдена по имени — возвращается None."""
    resolver, _ = _make_resolver(mocker, minimal_confluence_config, known_pages={})

    assert resolver._find_page_id("Missing Page") is None


@pytest.mark.infrastructure
def test_page_id_exists_true_for_known_id(
    mocker: MockerFixture, minimal_confluence_config: dict
) -> None:
    """Известный ID — страница считается существующей."""
    resolver, _ = _make_resolver(mocker, minimal_confluence_config, known_ids={"100002"})

    assert resolver._page_id_exists("100002") is True


@pytest.mark.infrastructure
def test_page_id_exists_false_for_unknown_id(
    mocker: MockerFixture, minimal_confluence_config: dict
) -> None:
    """Неизвестный ID — страница считается несуществующей."""
    resolver, _ = _make_resolver(mocker, minimal_confluence_config, known_ids=set())

    assert resolver._page_id_exists("100003") is False


# Smoke-тесты _resolve_root_parent напрямую; полная матрица — в TestNameIdPriorityMatrix.
@pytest.mark.business_logic
def test_cli_name_resolved_value_passed_through(
    mocker: MockerFixture, minimal_confluence_config: dict
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
    mocker: MockerFixture, minimal_confluence_config: dict
) -> None:
    """Ничего не задано — ConfigError с именем поля."""
    resolver, _ = _make_resolver(mocker, minimal_confluence_config)

    with pytest.raises(ConfigError) as exc_info:
        resolver._resolve_root_parent(None, None, None, None, "release_docs_root_parent")

    assert "release_docs_root_parent" in str(exc_info.value)


@pytest.mark.parametrize(
    "section",
    ["passports", "release", "profile"],
    ids=["passports", "release", "profile"],
)
class TestResolveRequiredParent:
    """Приоритет CLI/конфиг для обязательных родителей (passports, release, profile)."""

    @pytest.mark.business_logic
    def test_cli_name_wins_over_config_id(
        self,
        mocker: MockerFixture,
        minimal_confluence_config: dict,
        section: str,
    ) -> None:
        """CLI-имя побеждает, даже если в конфиге задан ID."""
        resolver, _ = _make_resolver(
            mocker,
            minimal_confluence_config,
            known_pages={"CLI Parent": "200001"},
            **_config_overrides(section, id_value="200002"),
        )

        result = _CALLERS[section](resolver, "CLI Parent", None)

        assert result == "200001"

    @pytest.mark.business_logic
    def test_cli_name_unresolved_ignores_config_id_entirely(
        self,
        mocker: MockerFixture,
        minimal_confluence_config: dict,
        section: str,
    ) -> None:
        """CLI-имя не резолвится — отката на config id нет (источник «всё или ничего»)."""
        resolver, mock_client = _make_resolver(
            mocker,
            minimal_confluence_config,
            known_pages={},
            known_ids={"200003"},
            **_config_overrides(section, id_value="200003"),
        )

        with pytest.raises(ConfigError):
            _CALLERS[section](resolver, "Nonexistent Parent", None)

        mock_client.get_page.assert_not_called()

    @pytest.mark.business_logic
    def test_cli_value_set_silences_conflicting_config_no_warning(
        self,
        mocker: MockerFixture,
        minimal_confluence_config: dict,
        caplog: pytest.LogCaptureFixture,
        section: str,
    ) -> None:
        """CLI-значение задано — конфликт name/id в конфиге не проверяется и не логируется."""
        resolver, mock_client = _make_resolver(
            mocker,
            minimal_confluence_config,
            known_pages={"CLI Parent": "200001", "Config Parent": "200004"},
            **_config_overrides(section, name="Config Parent", id_value="200005"),
        )

        with caplog.at_level(logging.WARNING):
            result = _CALLERS[section](resolver, "CLI Parent", None)

        assert result == "200001"
        mock_client.find_page.assert_called_once_with("CLI Parent", space=SPACE)
        assert not any(r.levelno == logging.WARNING for r in caplog.records)


def _build_resolver_for_source(
    mocker: MockerFixture,
    minimal_confluence_config: dict,
    source: str,
    name: str | None,
    id_value: str | None,
    section: str,
    known_pages: dict[str, str],
    known_ids: set[str] | None,
) -> tuple[RootPageResolver, Any, str | None, str | None]:
    """
    Резолвер + (call_name, call_id) для указанного источника: для CLI — сами
    name/id_value, для Config — они "вшиваются" в конфиг, а вызов идёт с (None, None).
    """
    if source == "CLI":
        resolver, mock_client = _make_resolver(
            mocker,
            minimal_confluence_config,
            known_pages=known_pages,
            known_ids=known_ids,
        )
        return resolver, mock_client, name, id_value

    resolver, mock_client = _make_resolver(
        mocker,
        minimal_confluence_config,
        known_pages=known_pages,
        known_ids=known_ids,
        **_config_overrides(section, name=name, id_value=id_value),
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
    "section",
    ["passports", "release", "profile"],
    ids=["passports", "release", "profile"],
)
@pytest.mark.parametrize("source", ["CLI", "Config"])
class TestNameIdPriorityMatrix:
    """
    Матрица _NAME_ID_PRIORITY_CASES x 2 источника x 3 секции = 54 прогона.
    Кросс-source кейсы — в TestResolveRequiredParent.
    """

    @pytest.mark.business_logic
    @pytest.mark.parametrize(
        "name,id_value,known_pages,known_ids,expects_error,expected_result,expect_warning",
        _NAME_ID_PRIORITY_CASES,
    )
    def test_name_id_priority(
        self,
        mocker: MockerFixture,
        minimal_confluence_config: dict,
        caplog: pytest.LogCaptureFixture,
        section: str,
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
            section,
            known_pages,
            known_ids,
        )

        if expects_error:
            with pytest.raises(ConfigError):
                _CALLERS[section](resolver, call_name, call_id)
            return

        with caplog.at_level(logging.WARNING):
            result = _CALLERS[section](resolver, call_name, call_id)

        assert result == expected_result
        if name is None:
            mock_client.find_page.assert_not_called()

        warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        if expect_warning:
            assert any(source in w for w in warnings)
        else:
            assert warnings == []


@pytest.mark.business_logic
def test_resolve_parent_profile_centric_reads_its_own_config_section(
    mocker: MockerFixture, minimal_confluence_config: dict
) -> None:
    """
    resolve_parent('profile_centric', ...) читает
    strategies.profile_centric, а не strategies.release.
    """
    resolver, mock_client = _make_resolver(
        mocker,
        minimal_confluence_config,
        known_pages={"Profile Parent Page": "400001"},
        strategies={
            "profile_centric": {"root_parent_name": "Profile Parent Page"},
            "release": {"root_parent_name": "Release Parent Page"},
        },
    )

    result = resolver.resolve_parent("profile_centric", None, None)

    assert result == "400001"
    mock_client.find_page.assert_called_once_with("Profile Parent Page", space=SPACE)


# resolve_parent: диспетчеризация через registry.STRATEGIES
@pytest.mark.contract
def test_resolve_parent_rejects_unregistered_strategy_type(
    mocker: MockerFixture,
    minimal_confluence_config: dict,
) -> None:
    """
    Неизвестный strategy_type останавливает резолвинг явной ошибкой ConfigError.

    Опечатка в ключе не должна молча превращаться в обращение к несуществующей секции
    конфига. Ключ обязан попасть в текст ошибки (в виде repr), чтобы его было видно
    пользователю. Ключ ``passports`` при этом валиден: IS_SINGLE_PAGE резолвер
    больше не проверяет — это забота публичного ``publish_single_page``.
    """
    resolver, _ = _make_resolver(mocker, minimal_confluence_config)

    with pytest.raises(ConfigError, match="'some_other_strategy'"):
        resolver.resolve_parent("some_other_strategy", "Some Name", None)


@pytest.mark.business_logic
@pytest.mark.parametrize("strategy_type", ["kit_pinned", "kit_latest"])
def test_resolve_parent_kit_strategies_read_their_own_config_section(
    mocker: MockerFixture, minimal_confluence_config: dict, strategy_type: str
) -> None:
    """
    resolve_parent('kit_pinned'/'kit_latest', None, None) читает
    собственную секцию strategies.<strategy_type>, а не секцию соседней kit-стратегии.

    ``publish all`` резолвит родителей обеих страниц комплекта только по конфигу,
    поэтому у каждой секции своя родительская страница.
    """
    other_type = "kit_latest" if strategy_type == "kit_pinned" else "kit_pinned"
    resolver, mock_client = _make_resolver(
        mocker,
        minimal_confluence_config,
        known_pages={"Own Parent": "400011", "Other Parent": "400012"},
        strategies={
            strategy_type: {"root_parent_name": "Own Parent"},
            other_type: {"root_parent_name": "Other Parent"},
        },
    )

    result = resolver.resolve_parent(strategy_type, None, None)

    assert result == "400011"
    mock_client.find_page.assert_called_once_with("Own Parent", space=SPACE)


@pytest.mark.business_logic
@pytest.mark.parametrize("strategy_type", ["kit_pinned", "kit_latest"])
def test_resolve_parent_kit_strategy_without_config_section_raises_config_error(
    mocker: MockerFixture, minimal_confluence_config: dict, strategy_type: str
) -> None:
    """
    Если секции kit-стратегии нет в конфиге и родитель не передан, резолв завершается ``ConfigError``.

    Это условие, при котором ``publish all`` останавливается до начала публикации:
    в конфиге обязаны быть секции ``kit_pinned`` и ``kit_latest`` с родительской страницей.
    """
    resolver, _ = _make_resolver(mocker, minimal_confluence_config)

    with pytest.raises(ConfigError, match=f"strategies.{strategy_type}.root_parent"):
        resolver.resolve_parent(strategy_type, None, None)
