"""
Юнит-тесты для autodoc.parser.parsers.options_parser.OptionsParser.

Охватывает: select_ci_prefix, parse_file (реальные JSON файлы), pick_options.
Реальные JSON файлы опций загружаются из директории фикстур resources/options/.
"""

from pathlib import Path

import pytest

from autodoc.parser.parsers.options_parser import OptionsParser
from tests.unit.parser.conftest import RESOURCES_DIR

CI_PREFIX_V2: str = "/ci-2.0/"
CI_PREFIX_V16: str = "/ci-1.6/"

PATH_V2_TECH: str = "/repo/ci-2.0/tech/options.json"

#: Директория resources/options/ с реальными JSON-файлами опций.
OPTIONS_DIR: Path = RESOURCES_DIR / "options"


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "paths, expected",
    [
        # только ci-1.6 -> выбирается единственный присутствующий префикс
        pytest.param(["/conan/ci-1.6/options.json"], CI_PREFIX_V16, id="ci16-alone"),
        # только ci-2.0 -> выбирается единственный присутствующий префикс
        pytest.param(["/conan/ci-2.0/options.json"], CI_PREFIX_V2, id="ci20-alone"),
        # ни одна из известных CI-директорий не найдена -> пустая строка
        pytest.param(["/repo/other/options.json"], "", id="no-match"),
        # пустой список путей -> пустая строка
        pytest.param([], "", id="empty-list"),
        # присутствуют оба префикса -> ci-2.0 приоритетнее ci-1.6 независимо от порядка путей
        pytest.param(
            [
                "/components/mylib/ci-1.6/global/options.json",
                "/components/mylib/ci-2.0/global/options.json",
            ],
            CI_PREFIX_V2,
            id="both-present-ci20-preferred",
        ),
    ],
)
def test_select_ci_prefix(paths: list[str], expected: str) -> None:
    """select_ci_prefix выбирает CI-директорию по приоритету ci-2.0 > ci-1.6, либо '' при отсутствии совпадений."""
    assert OptionsParser.select_ci_prefix(paths) == expected


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "filename, opt_path, ci_prefix, expected_channel, expected_cleaned",
    [
        # apr: единственный глобальный options.json без поддиректории канала (ci-1.6)
        pytest.param(
            "apr_options.json",
            "/conan/ci-1.6/options.json",
            CI_PREFIX_V16,
            None,
            {"1": "apr:shared=True"},
            id="apr-ci16-global",
        ),
        # sqlite3 fast: options.json в поддиректории канала ci-2.0/fast, 5 записей
        pytest.param(
            "sqlite3_fast_options.json",
            "/conan/ci-2.0/fast/options.json",
            CI_PREFIX_V2,
            "fast",
            {
                "1": "",
                "2": "sqlite3:enable_json1=True",
                "3": "sqlite3:enable_json1=True, sqlite3:RTree_patch_enable=True",
                "4": (
                    "sqlite3:RTree_patch_enable=True, sqlite3:enable_json1=True, "
                    "sqlite3:enable_fts3=True, sqlite3:enable_fts5=True, "
                    "sqlite3:enable_dbstat_vtab=True, sqlite3:enable_explain_comments=True"
                ),
                "5": "sqlite3:with_icu=True",
            },
            id="sqlite3-ci20-fast",
        ),
        # sqlite3 slow: options.json в поддиректории канала ci-1.6/slow, 12 записей
        pytest.param(
            "sqlite3_slow_options.json",
            "/conan/ci-1.6/slow/options.json",
            CI_PREFIX_V16,
            "slow",
            {
                "1": "",
                "2": "sqlite3:shared=True",
                "3": "sqlite3:enable_json1=True",
                "4": "sqlite3:enable_json1=True, sqlite3:RTree_patch_enable=True",
                "5": "sqlite3:enable_json1=True, sqlite3:shared=True",
                "6": "sqlite3:shared=True, sqlite3:RTree_patch_enable=True",
                "7": (
                    "sqlite3:enable_json1=True, sqlite3:RTree_patch_enable=True, "
                    "sqlite3:shared=True"
                ),
                "8": "sqlite3:shared=True, sqlite3:strip_binary=True",
                "9": "sqlite3:enable_json1=True, sqlite3:shared=True, sqlite3:strip_binary=True",
                "10": (
                    "sqlite3:shared=True, sqlite3:RTree_patch_enable=True, "
                    "sqlite3:strip_binary=True"
                ),
                "11": (
                    "sqlite3:enable_json1=True, sqlite3:RTree_patch_enable=True, "
                    "sqlite3:shared=True, sqlite3:strip_binary=True"
                ),
                "12": "sqlite3:with_icu=True",
            },
            id="sqlite3-ci16-slow",
        ),
        # icu fast: options.json в поддиректории канала ci-1.6/fast, 2 записи
        pytest.param(
            "icu_fast_options.json",
            "/conan/ci-1.6/fast/options.json",
            CI_PREFIX_V16,
            "fast",
            {"1": "", "2": "icu:mobile=True"},
            id="icu-ci16-fast",
        ),
        # nlohmann_json: плоский ci-2.0/options.json (без поддиректории канала), header-only компонент
        pytest.param(
            "nlohmann_json_options.json",
            "/conan/ci-2.0/options.json",
            CI_PREFIX_V2,
            None,
            {"1": ""},
            id="nlohmann-ci20-global",
        ),
        # patchelf: плоский ci-1.6/options.json (без поддиректории канала)
        pytest.param(
            "patchelf_options.json",
            "/conan/ci-1.6/options.json",
            CI_PREFIX_V16,
            None,
            {"1": ""},
            id="patchelf-ci16-global",
        ),
        # openssl: options.json в поддиректории канала ci-2.0/trusted
        pytest.param(
            "openssl_options.json",
            "/ci-2.0/trusted/options.json",
            CI_PREFIX_V2,
            "trusted",
            {"1": "", "2": "openssl:shared=True"},
            id="openssl-ci20-trusted",
        ),
        # zlib: options.json в поддиректории канала ci-2.0/fast, единственная пустая опция
        pytest.param(
            "zlib_options.json",
            "/ci-2.0/fast/options.json",
            CI_PREFIX_V2,
            "fast",
            {"1": ""},
            id="zlib-ci20-fast",
        ),
    ],
)
def test_parse_file_real_options_files(
    filename: str,
    opt_path: str,
    ci_prefix: str,
    expected_channel: str | None,
    expected_cleaned: dict[str, str],
) -> None:
    """parse_file на реальных options.json из resources/options/ возвращает ожидаемые channel и cleaned."""
    text = (OPTIONS_DIR / filename).read_text(encoding="utf-8")
    channel, cleaned = OptionsParser.parse_file(text, opt_path=opt_path, ci_prefix=ci_prefix)
    assert channel == expected_channel
    assert cleaned == expected_cleaned


@pytest.mark.business_logic
def test_parse_file_invalid_json_returns_empty() -> None:
    """
    parse_file возвращает (None, {}), если текст JSON не может быть разобран.

    Маркер business_logic: некорректный options.json — это домен-специфичный
    сценарий (повреждённый файл в репозитории компонента), а не сбой
    инфраструктуры, поэтому тест проверяет предусмотренное правило graceful-деградации.
    """
    result = OptionsParser.parse_file(
        "NOT JSON",
        opt_path=PATH_V2_TECH,
        ci_prefix=CI_PREFIX_V2,
    )
    assert result == (None, {})


@pytest.mark.business_logic
def test_parse_file_empty_json_object() -> None:
    """parse_file возвращает пустой словарь опций для '{}' без исключений."""
    _, cleaned = OptionsParser.parse_file(
        "{}",
        opt_path=PATH_V2_TECH,
        ci_prefix=CI_PREFIX_V2,
    )
    assert cleaned == {}


@pytest.mark.business_logic
def test_parse_file_strips_whitespace_from_values() -> None:
    """parse_file удаляет начальные и конечные пробелы из каждого значения опции."""
    _, cleaned = OptionsParser.parse_file(
        '{"1": "  shared=True  "}',
        opt_path=PATH_V2_TECH,
        ci_prefix=CI_PREFIX_V2,
    )
    assert cleaned == {"1": "shared=True"}


@pytest.mark.business_logic
def test_parse_file_non_string_values_excluded() -> None:
    """parse_file пропускает записи, значение которых не является строкой (например, числа)."""
    _, cleaned = OptionsParser.parse_file(
        '{"1": "shared=True", "count": 42}',
        opt_path=PATH_V2_TECH,
        ci_prefix=CI_PREFIX_V2,
    )
    assert cleaned == {"1": "shared=True"}


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "repo_data, channel, expected",
    [
        # канал присутствует среди channels -> используется channel-specific набор, а не global;
        # при наличии нескольких каналов выбирается именно запрошенный (fast), а не slow
        pytest.param(
            {
                "global": {"1": ""},
                "channels": {
                    "fast": {"1": "", "2": "x=True"},
                    "slow": {"1": "", "2": "y=True"},
                },
            },
            "fast",
            {"1": "", "2": "x=True"},
            id="channel-found-overrides-global-and-selects-among-multiple",
        ),
        # запрошенный канал отсутствует среди channels -> используется global
        pytest.param(
            {"global": {"1": "apr:shared=True"}, "channels": {}},
            "tech",
            {"1": "apr:shared=True"},
            id="no-channel-match-uses-global",
        ),
        # channel — пустая строка, среди channels есть только непустые ключи -> используется global
        pytest.param(
            {"channels": {"tech": {"1": "x"}}, "global": {"1": "y"}},
            "",
            {"1": "y"},
            id="empty-channel-uses-global",
        ),
    ],
)
def test_pick_options_channel_selection_and_global_fallback(
    repo_data: dict, channel: str, expected: dict[str, str]
) -> None:
    """
    pick_options возвращает channel-specific набор, если запрошенный канал есть
    среди channels, и падает обратно на global, если такого канала нет.
    """
    assert OptionsParser.pick_options(repo_data, channel) == expected


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "opt_path, ci_prefix, expected_channel",
    [
        # нет поддиректории после ci-префикса -> канал не определён
        pytest.param("/repo/ci-2.0/options.json", CI_PREFIX_V2, None, id="no-channel-segment"),
        # канал извлекается из поддиректории после ci-2.0/
        pytest.param(
            "/conan/ci-2.0/fast/options.json", CI_PREFIX_V2, "fast", id="ci20-channel-fast"
        ),
        # канал извлекается из поддиректории после ci-1.6/
        pytest.param(
            "/conan/ci-1.6/slow/options.json", CI_PREFIX_V16, "slow", id="ci16-channel-slow"
        ),
    ],
)
def test_parse_file_channel_extraction(
    opt_path: str, ci_prefix: str, expected_channel: str | None
) -> None:
    """parse_file извлекает имя канала из первой поддиректории после ci-префикса, либо None при её отсутствии."""
    channel, _ = OptionsParser.parse_file('{"1": ""}', opt_path=opt_path, ci_prefix=ci_prefix)
    assert channel == expected_channel


@pytest.mark.business_logic
@pytest.mark.parametrize("channel", ["fast", "slow", "tech", ""])
def test_pick_options_apr_global_returned_for_any_channel(channel: str) -> None:
    """
    pick_options возвращает глобальные опции apr независимо от запрошенного канала.

    У apr есть только плоский ci-1.6/options.json (без разбивки по каналам),
    поэтому один и тот же набор опций {'1': 'apr:shared=True'} должен
    возвращаться для 'fast', 'slow', 'tech' и пустой строки.
    """
    repo_data = {
        "global": {"1": "apr:shared=True"},
        "channels": {},
    }
    result = OptionsParser.pick_options(repo_data, channel)
    assert result == {"1": "apr:shared=True"}


@pytest.mark.business_logic
def test_parse_file_ci_prefix_not_in_path_raises_or_is_guarded() -> None:
    """
    parse_file поднимает IndexError, если ci_prefix отсутствует в opt_path (текущее поведение кода).

    Найденный баг (не исправлен по гарантийным условиям задачи): в
    OptionsParser.parse_file выражение opt_path.split(ci_prefix)[1] не
    защищено от случая, когда ci_prefix не встречается в opt_path — str.split
    тогда возвращает список из одного элемента, и обращение к индексу 1
    приводит к необработанному IndexError. См. autodoc/parser/parsers/options_parser.py,
    метод parse_file.
    """
    with pytest.raises(IndexError):
        OptionsParser.parse_file(
            '{"1": ""}',
            opt_path="/repo/no-ci-prefix-here/options.json",
            ci_prefix=CI_PREFIX_V2,
        )


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "repo_data, channel",
    [
        # repo_data полностью пуст
        pytest.param({}, "fast", id="empty-repo-data"),
        # channels присутствует и не содержит запрошенный канал, но ключ 'global' отсутствует
        pytest.param({"channels": {"fast": {"1": "x=True"}}}, "slow", id="missing-global-key"),
        # channels присутствует и не содержит запрошенный канал, а 'global' явно None
        pytest.param(
            {"global": None, "channels": {"fast": {"1": "x=True"}}},
            "slow",
            id="explicit-none-global",
        ),
    ],
)
def test_pick_options_returns_default_placeholder(repo_data: dict, channel: str) -> None:
    """pick_options возвращает плейсхолдер {'1': ''}, если нет ни подходящего канала, ни данных global."""
    assert OptionsParser.pick_options(repo_data, channel) == {"1": ""}
