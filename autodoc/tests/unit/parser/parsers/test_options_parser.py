"""Юнит-тесты для autodoc.parser.parsers.options_parser.OptionsParser.

Охватывает: select_ci_prefix, parse_file, pick_options.
Реальные JSON-файлы опций читаются из фикстуры resources_dir.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autodoc.parser.parsers.options_parser import OptionsParser

# ---------------------------------------------------------------------------
# Константы уровня модуля
# ---------------------------------------------------------------------------

CI_PREFIX_V2: str = "/ci-2.0/"
CI_PREFIX_V16: str = "/ci-1.6/"

PATH_V2_TECH: str = "/repo/ci-2.0/tech/options.json"
PATH_V16_TECH: str = "/repo/ci-1.6/tech/options.json"
PATH_OTHER: str = "/repo/other/options.json"

JSON_TWO_OPTIONS: str = '{"1": "shared=True", "2": "shared=False"}'
JSON_ONE_PADDED: str = '{"1": "  shared=True  "}'
JSON_MIXED_TYPES: str = '{"1": "shared=True", "count": 42}'
JSON_INVALID: str = "not-json"


# ===========================================================================
# select_ci_prefix: /ci-2.0/ предпочтительнее /ci-1.6/
# ===========================================================================


def test_select_ci_prefix_prefers_v2() -> None:
    """select_ci_prefix возвращает '/ci-2.0/', когда присутствуют пути v2 и v1.6."""
    paths = [PATH_V2_TECH, PATH_V16_TECH]
    result = OptionsParser.select_ci_prefix(paths)
    assert result == CI_PREFIX_V2


# ===========================================================================
# select_ci_prefix: присутствует только /ci-1.6/
# ===========================================================================


def test_select_ci_prefix_falls_back_to_v1_6() -> None:
    """select_ci_prefix возвращает '/ci-1.6/', когда присутствуют только пути v1.6."""
    paths = ["/repo/ci-1.6/tech/options.json"]
    result = OptionsParser.select_ci_prefix(paths)
    assert result == CI_PREFIX_V16


# ===========================================================================
# select_ci_prefix: нет совпадения → пустая строка
# ===========================================================================


def test_select_ci_prefix_no_match_returns_empty_string() -> None:
    """select_ci_prefix возвращает '', когда не найдена ни одна известная CI-директория."""
    result = OptionsParser.select_ci_prefix([PATH_OTHER])
    assert result == ""


# ===========================================================================
# select_ci_prefix: пустой список → пустая строка
# ===========================================================================


def test_select_ci_prefix_empty_list_returns_empty_string() -> None:
    """select_ci_prefix возвращает '' для пустого входного списка."""
    result = OptionsParser.select_ci_prefix([])
    assert result == ""


# ===========================================================================
# parse_file: корректный JSON извлекает имя канала
# ===========================================================================


def test_parse_file_valid_json_extracts_channel() -> None:
    """parse_file корректно извлекает сегмент канала из пути."""
    channel, cleaned = OptionsParser.parse_file(
        JSON_TWO_OPTIONS,
        opt_path=PATH_V2_TECH,
        ci_prefix=CI_PREFIX_V2,
    )
    assert channel == "tech"
    assert cleaned == {"1": "shared=True", "2": "shared=False"}


# ===========================================================================
# parse_file: нет подсегмента после префикса → channel равен None
# ===========================================================================


def test_parse_file_no_channel_segment_returns_none() -> None:
    """parse_file возвращает channel=None, когда путь не имеет поддиректории после префикса."""
    channel, _ = OptionsParser.parse_file(
        JSON_TWO_OPTIONS,
        opt_path="/repo/ci-2.0/options.json",
        ci_prefix=CI_PREFIX_V2,
    )
    assert channel is None


# ===========================================================================
# parse_file: некорректный JSON → пустой словарь и None channel
# ===========================================================================


def test_parse_file_invalid_json_returns_empty() -> None:
    """parse_file возвращает (None, {}), когда JSON-текст не может быть разобран."""
    result = OptionsParser.parse_file(
        JSON_INVALID,
        opt_path=PATH_V2_TECH,
        ci_prefix=CI_PREFIX_V2,
    )
    assert result == (None, {})


# ===========================================================================
# parse_file: удаляет пробелы из строковых значений
# ===========================================================================


def test_parse_file_strips_whitespace_from_values() -> None:
    """parse_file удаляет ведущие и завершающие пробелы из каждого строкового значения опции."""
    _, cleaned = OptionsParser.parse_file(
        JSON_ONE_PADDED,
        opt_path=PATH_V2_TECH,
        ci_prefix=CI_PREFIX_V2,
    )
    assert cleaned["1"] == "shared=True"


# ===========================================================================
# parse_file: нестроковые значения исключаются
# ===========================================================================


def test_parse_file_non_string_values_excluded() -> None:
    """parse_file пропускает записи, значение которых не является строкой (например, целые числа)."""
    _, cleaned = OptionsParser.parse_file(
        JSON_MIXED_TYPES,
        opt_path=PATH_V2_TECH,
        ci_prefix=CI_PREFIX_V2,
    )
    assert "1" in cleaned
    assert "count" not in cleaned


# ===========================================================================
# pick_options: канало-специфичные опции возвращаются при совпадении канала
# ===========================================================================


def test_pick_options_returns_channel_specific() -> None:
    """pick_options возвращает channels[channel], когда ключ канала существует."""
    data: dict = {"channels": {"tech": {"1": "shared=True"}}, "global": {"1": ""}}
    result = OptionsParser.pick_options(data, "tech")
    assert result == {"1": "shared=True"}


# ===========================================================================
# pick_options: использует global, если канал не найден
# ===========================================================================


def test_pick_options_falls_back_to_global() -> None:
    """pick_options возвращает запись 'global', когда запрошенный канал отсутствует."""
    data: dict = {"channels": {}, "global": {"1": "shared=False"}}
    result = OptionsParser.pick_options(data, "tech")
    assert result == {"1": "shared=False"}


# ===========================================================================
# pick_options: использует {"1": ""} когда оба отсутствуют
# ===========================================================================


def test_pick_options_defaults_to_empty_option_set() -> None:
    """pick_options возвращает {'1': ''}, когда отсутствуют и channels, и global."""
    result = OptionsParser.pick_options({}, "tech")
    assert result == {"1": ""}


# ===========================================================================
# pick_options: пустая строка канала использует global
# ===========================================================================


def test_pick_options_empty_channel_uses_global() -> None:
    """pick_options использует global, когда channel — пустая строка."""
    data: dict = {"channels": {"tech": {"1": "x"}}, "global": {"1": "y"}}
    result = OptionsParser.pick_options(data, "")
    assert result == {"1": "y"}


# ===========================================================================
# Реальный openssl_options.json разбирается корректно (использует resources_dir)
# ===========================================================================


def test_options_parser_parses_real_openssl_options(resources_dir: Path) -> None:
    """OptionsParser.parse_file читает реальный options.json и возвращает корректное отображение."""
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


# ===========================================================================
# Реальный zlib_options.json: одна пустая опция (использует resources_dir)
# ===========================================================================


def test_options_parser_parses_zlib_single_empty_option(resources_dir: Path) -> None:
    """OptionsParser.parse_file обрабатывает файл с одной пустой опцией без ошибок."""
    options_file = resources_dir / "options" / "zlib_options.json"
    text = options_file.read_text(encoding="utf-8")
    channel, cleaned = OptionsParser.parse_file(
        text, opt_path="/ci-2.0/fast/options.json", ci_prefix=CI_PREFIX_V2
    )
    assert channel == "fast"
    assert "1" in cleaned
    assert cleaned["1"] == ""
