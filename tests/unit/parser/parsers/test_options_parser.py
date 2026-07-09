"""Юнит-тесты для autodoc.parser.parsers.options_parser.OptionsParser.

Охватывает: select_ci_prefix, parse_file (реальные JSON файлы), pick_options.
Реальные JSON файлы опций загружаются из директории фиксчур resources/options/.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autodoc.parser.parsers.options_parser import OptionsParser

CI_PREFIX_V2: str = "/ci-2.0/"
CI_PREFIX_V16: str = "/ci-1.6/"

PATH_V2_TECH: str = "/repo/ci-2.0/tech/options.json"
PATH_V16_TECH: str = "/repo/ci-1.6/tech/options.json"
PATH_OTHER: str = "/repo/other/options.json"


@pytest.fixture
def options_dir(resources_dir: Path) -> Path:
    """Путь к директории resources/options/ содержащей реальные JSON файлы опций."""
    return resources_dir / "options"


@pytest.mark.business_logic
def test_select_ci_prefix_uses_ci_16_alone() -> None:
    """select_ci_prefix возвращает '/ci-1.6/', если присутствуют только пути ci-1.6."""
    paths = ["/conan/ci-1.6/options.json"]
    result = OptionsParser.select_ci_prefix(paths)
    assert result == CI_PREFIX_V16


@pytest.mark.business_logic
def test_select_ci_prefix_no_match_returns_empty_string() -> None:
    """select_ci_prefix возвращает '', если ни одна из известных CI-директорий не найдена."""
    result = OptionsParser.select_ci_prefix([PATH_OTHER])
    assert result == ""


@pytest.mark.business_logic
def test_select_ci_prefix_empty_list_returns_empty_string() -> None:
    """select_ci_prefix возвращает '' для пустого списка путей."""
    result = OptionsParser.select_ci_prefix([])
    assert result == ""


@pytest.mark.integration
def test_parse_file_apr_single_option(options_dir: Path) -> None:
    """parse_file на apr_options.json возвращает словарь из 1 записи 'apr:shared=True'."""
    text = (options_dir / "apr_options.json").read_text(encoding="utf-8")
    channel, cleaned = OptionsParser.parse_file(
        text,
        opt_path="/conan/ci-1.6/options.json",
        ci_prefix=CI_PREFIX_V16,
    )
    # Глобальный файл (нет поддиректории после ci-префикса) -> channel is None
    assert channel is None
    assert cleaned == {"1": "apr:shared=True"}


@pytest.mark.integration
def test_parse_file_sqlite3_fast_five_options(options_dir: Path) -> None:
    """parse_file на sqlite3_fast_options.json возвращает словарь из 5 записей; ключ '5' содержит 'with_icu'."""
    text = (options_dir / "sqlite3_fast_options.json").read_text(encoding="utf-8")
    channel, cleaned = OptionsParser.parse_file(
        text,
        opt_path="/conan/ci-2.0/fast/options.json",
        ci_prefix=CI_PREFIX_V2,
    )
    assert channel == "fast"
    assert len(cleaned) == 5
    assert "with_icu" in cleaned["5"]


@pytest.mark.integration
def test_parse_file_sqlite3_slow_twelve_options(options_dir: Path) -> None:
    """parse_file на sqlite3_slow_options.json возвращает словарь из 12 записей; ключ '12' содержит 'with_icu'."""
    text = (options_dir / "sqlite3_slow_options.json").read_text(encoding="utf-8")
    channel, cleaned = OptionsParser.parse_file(
        text,
        opt_path="/conan/ci-1.6/slow/options.json",
        ci_prefix=CI_PREFIX_V16,
    )
    assert channel == "slow"
    assert len(cleaned) == 12
    assert "with_icu" in cleaned["12"]


@pytest.mark.integration
def test_parse_file_icu_fast_two_options(options_dir: Path) -> None:
    """parse_file на icu_fast_options.json возвращает словарь из 2 записей; '2' == 'icu:mobile=True'."""
    text = (options_dir / "icu_fast_options.json").read_text(encoding="utf-8")
    channel, cleaned = OptionsParser.parse_file(
        text,
        opt_path="/conan/ci-1.6/fast/options.json",
        ci_prefix=CI_PREFIX_V16,
    )
    assert channel == "fast"
    assert len(cleaned) == 2
    assert cleaned["2"] == "icu:mobile=True"


@pytest.mark.integration
def test_parse_file_nlohmann_single_empty_option(options_dir: Path) -> None:
    """parse_file на nlohmann_json_options.json возвращает {'1': ''} для header-only компонента."""
    text = (options_dir / "nlohmann_json_options.json").read_text(encoding="utf-8")
    channel, cleaned = OptionsParser.parse_file(
        text,
        opt_path="/conan/ci-2.0/options.json",
        ci_prefix=CI_PREFIX_V2,
    )
    assert cleaned == {"1": ""}


@pytest.mark.business_logic
def test_parse_file_invalid_json_returns_empty() -> None:
    """parse_file возвращает (None, {}), если текст JSON не может быть разобран.

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
    channel, cleaned = OptionsParser.parse_file(
        "{}",
        opt_path=PATH_V2_TECH,
        ci_prefix=CI_PREFIX_V2,
    )
    assert cleaned == {}


@pytest.mark.business_logic
def test_parse_file_no_channel_segment_returns_none() -> None:
    """parse_file возвращает channel=None, если после CI-префикса нет поддиректории."""
    channel, _ = OptionsParser.parse_file(
        '{"1": "shared=True"}',
        opt_path="/repo/ci-2.0/options.json",
        ci_prefix=CI_PREFIX_V2,
    )
    assert channel is None


@pytest.mark.business_logic
def test_parse_file_strips_whitespace_from_values() -> None:
    """parse_file удаляет начальные и конечные пробелы из каждого значения опции."""
    _, cleaned = OptionsParser.parse_file(
        '{"1": "  shared=True  "}',
        opt_path=PATH_V2_TECH,
        ci_prefix=CI_PREFIX_V2,
    )
    assert cleaned["1"] == "shared=True"


@pytest.mark.business_logic
def test_parse_file_non_string_values_excluded() -> None:
    """parse_file пропускает записи, значение которых не является строкой (например, числа)."""
    _, cleaned = OptionsParser.parse_file(
        '{"1": "shared=True", "count": 42}',
        opt_path=PATH_V2_TECH,
        ci_prefix=CI_PREFIX_V2,
    )
    assert "1" in cleaned
    assert "count" not in cleaned


@pytest.mark.business_logic
def test_pick_options_selects_channel_specific_over_global() -> None:
    """pick_options возвращает специфичную для канала запись, если она есть, игнорируя global."""
    repo_data = {
        "global": {"1": ""},
        "channels": {"fast": {"1": "", "2": "x=True"}},
    }
    result = OptionsParser.pick_options(repo_data, "fast")
    assert result == {"1": "", "2": "x=True"}


@pytest.mark.business_logic
def test_pick_options_falls_back_to_global_when_no_channel_match() -> None:
    """pick_options возвращает глобальную запись, если запрошенный канал отсутствует."""
    repo_data = {
        "global": {"1": "apr:shared=True"},
        "channels": {},
    }
    result = OptionsParser.pick_options(repo_data, "tech")
    assert result == {"1": "apr:shared=True"}


@pytest.mark.business_logic
def test_pick_options_returns_default_when_no_data() -> None:
    """pick_options возвращает {'1': ''}, если repo_data пуст."""
    result = OptionsParser.pick_options({}, "fast")
    assert result == {"1": ""}


@pytest.mark.business_logic
def test_pick_options_empty_channel_uses_global() -> None:
    """pick_options возвращается к global, если channel — пустая строка."""
    data: dict = {"channels": {"tech": {"1": "x"}}, "global": {"1": "y"}}
    result = OptionsParser.pick_options(data, "")
    assert result == {"1": "y"}


@pytest.mark.integration
def test_options_parser_parses_real_openssl_options(resources_dir: Path) -> None:
    """OptionsParser.parse_file читает реальный options.json openssl и возвращает корректный маппинг."""
    options_file = resources_dir / "options" / "openssl_options.json"
    text = options_file.read_text(encoding="utf-8")
    channel, cleaned = OptionsParser.parse_file(
        text, opt_path="/ci-2.0/trusted/options.json", ci_prefix=CI_PREFIX_V2
    )
    assert channel == "trusted"
    assert "1" in cleaned
    assert cleaned["1"] == ""
    assert "2" in cleaned
    assert cleaned["2"] == "openssl:shared=True"


@pytest.mark.integration
def test_options_parser_parses_zlib_single_empty_option(resources_dir: Path) -> None:
    """OptionsParser.parse_file корректно обрабатывает файл с одной пустой опцией."""
    options_file = resources_dir / "options" / "zlib_options.json"
    text = options_file.read_text(encoding="utf-8")
    channel, cleaned = OptionsParser.parse_file(
        text, opt_path="/ci-2.0/fast/options.json", ci_prefix=CI_PREFIX_V2
    )
    assert channel == "fast"
    assert "1" in cleaned
    assert cleaned["1"] == ""


@pytest.mark.business_logic
def test_select_ci_prefix_uses_ci_20_alone() -> None:
    """select_ci_prefix возвращает '/ci-2.0/', если присутствуют только пути ci-2.0 (без ci-1.6)."""
    paths = ["/conan/ci-2.0/options.json"]
    result = OptionsParser.select_ci_prefix(paths)
    assert result == CI_PREFIX_V2


@pytest.mark.integration
def test_parse_file_patchelf_ci16_flat_global(options_dir: Path) -> None:
    """patchelf использует ci-1.6/options.json (без поддиректории канала); channel is None, 1 запись."""
    text = (options_dir / "patchelf_options.json").read_text(encoding="utf-8")
    channel, cleaned = OptionsParser.parse_file(
        text,
        opt_path="/conan/ci-1.6/options.json",
        ci_prefix=CI_PREFIX_V16,
    )
    assert channel is None
    assert cleaned == {"1": ""}


@pytest.mark.business_logic
def test_pick_options_tech_channel_falls_back_to_global_ci16() -> None:
    """pick_options с channel='tech' и без ключа 'tech' возвращает глобальную запись (случай patchelf)."""
    repo_data = {
        "global": {"1": ""},
        "channels": {},
    }
    result = OptionsParser.pick_options(repo_data, "tech")
    assert result == {"1": ""}


@pytest.mark.business_logic
def test_pick_options_sqlite3_fast_selected_over_slow() -> None:
    """pick_options с channel='fast' выбирает запись fast, а не slow, когда присутствуют обе."""
    repo_data = {
        "global": None,
        "channels": {
            "fast": {"1": "", "2": "sqlite3:enable_json1=True"},
            "slow": {"1": "", "2": "sqlite3:shared=True"},
        },
    }
    result = OptionsParser.pick_options(repo_data, "fast")
    assert "enable_json1" in result["2"]
    assert "shared" not in result["2"]


@pytest.mark.business_logic
def test_parse_file_channel_extracted_from_ci20_path() -> None:
    """parse_file корректно извлекает канал 'fast' из пути /ci-2.0/fast/options.json."""
    channel, _ = OptionsParser.parse_file(
        '{"1": ""}',
        opt_path="/conan/ci-2.0/fast/options.json",
        ci_prefix=CI_PREFIX_V2,
    )
    assert channel == "fast"


@pytest.mark.business_logic
def test_parse_file_channel_extracted_from_ci16_path() -> None:
    """parse_file корректно извлекает канал 'slow' из пути /ci-1.6/slow/options.json."""
    channel, _ = OptionsParser.parse_file(
        '{"1": ""}',
        opt_path="/conan/ci-1.6/slow/options.json",
        ci_prefix=CI_PREFIX_V16,
    )
    assert channel == "slow"


@pytest.mark.business_logic
def test_pick_options_apr_global_returned_for_any_channel() -> None:
    """pick_options возвращает глобальные опции apr независимо от запрошенного канала.

    У apr есть только плоский ci-1.6/options.json (без разбивки по каналам),
    поэтому один и тот же набор опций {'1': 'apr:shared=True'} должен
    возвращаться для 'fast', 'slow' и 'tech'.
    """
    repo_data = {
        "global": {"1": "apr:shared=True"},
        "channels": {},
    }
    for channel in ("fast", "slow", "tech", ""):
        result = OptionsParser.pick_options(repo_data, channel)
        assert result == {"1": "apr:shared=True"}, f"failed for channel={channel!r}"


@pytest.mark.integration
def test_parse_file_nlohmann_ci20_flat_returns_none_channel(options_dir: Path) -> None:
    """Плоский nlohmann_json ci-2.0/options.json возвращает channel=None и одну пустую запись."""
    text = (options_dir / "nlohmann_json_options.json").read_text(encoding="utf-8")
    channel, cleaned = OptionsParser.parse_file(
        text,
        opt_path="/conan/ci-2.0/options.json",
        ci_prefix=CI_PREFIX_V2,
    )
    assert channel is None
    assert len(cleaned) == 1
    assert cleaned.get("1") == ""


@pytest.mark.business_logic
def test_pick_options_missing_global_key_returns_default() -> None:
    """pick_options возвращает {'1': ''}, если в repo_data есть channels, но нет ключа 'global'."""
    repo_data = {"channels": {"fast": {"1": "x=True"}}}
    result = OptionsParser.pick_options(repo_data, "slow")
    assert result == {"1": ""}


@pytest.mark.business_logic
def test_ci20_preferred_over_ci16_when_both_present() -> None:
    """select_ci_prefix выбирает ci-2.0, если присутствуют пути и ci-2.0, и ci-1.6, независимо от их порядка."""
    paths = [
        "/components/mylib/ci-1.6/global/options.json",
        "/components/mylib/ci-2.0/global/options.json",
    ]

    selected = OptionsParser.select_ci_prefix(paths)

    assert selected == "/ci-2.0/"


@pytest.mark.business_logic
def test_parse_file_ci_prefix_not_in_path_raises_or_is_guarded() -> None:
    """parse_file поднимает IndexError, если ci_prefix отсутствует в opt_path (текущее поведение кода).

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
def test_pick_options_no_channel_match_and_none_global_returns_default() -> None:
    """pick_options возвращает плейсхолдер {'1': ''}, если global is None и канал не найден."""
    repo_data = {"global": None, "channels": {"fast": {"1": "x=True"}}}
    result = OptionsParser.pick_options(repo_data, "slow")
    assert result == {"1": ""}
