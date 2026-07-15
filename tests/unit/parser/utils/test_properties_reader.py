"""Юнит-тесты для autodoc/parser/utils/properties_reader.py.

Покрывают продолжение строк, определение разделителя и граничные случаи,
незаметные при тестировании через ManifestParser. Весь файловый ввод-вывод
использует tmp_path — фикстурные файлы с диска не используются.
"""

from pathlib import Path

import pytest

from autodoc.parser.utils.properties_reader import (
    _detect_separator,
    read_properties,
)

_KEY_NAME: str = "component.name"
_KEY_VERSION: str = "component.version"
_VALUE_URL: str = "https://example.com/path:8080/resource"
_VALUE_LONG: str = "first-part-second-part"

_SEP_EQ: str = "="
_SEP_COLON: str = ":"


@pytest.mark.infrastructure
def test_properties_reader_line_continuation(tmp_path: Path) -> None:
    """Значение, разбитое на две физические строки, склеивается в одно логическое значение."""
    props_file: Path = tmp_path / "component.properties"
    props_file.write_text(
        f"{_KEY_NAME}=first-part-\\\nsecond-part\n",
        encoding="utf-8",
    )
    result: dict[str, str] = read_properties(props_file)
    assert _KEY_NAME in result
    assert result[_KEY_NAME] == _VALUE_LONG
    assert "\\" not in result[_KEY_NAME]


@pytest.mark.business_logic
def test_properties_reader_colon_in_value_with_equals_separator(
    tmp_path: Path,
) -> None:
    """Двоеточие внутри значения не считается разделителем ключ-значение при разделителе '='."""
    props_file: Path = tmp_path / "component.properties"
    props_file.write_text(
        f"component.url={_VALUE_URL}\n",
        encoding="utf-8",
    )
    result: dict[str, str] = read_properties(props_file)
    assert result["component.url"] == _VALUE_URL


@pytest.mark.infrastructure
def test_properties_reader_file_without_trailing_newline(tmp_path: Path) -> None:
    """Последний ключ разбирается корректно, даже если файл не заканчивается переводом строки."""
    props_file: Path = tmp_path / "component.properties"
    props_file.write_bytes(b"component.name=mylib")  # без завершающего \n
    result: dict[str, str] = read_properties(props_file)
    assert _KEY_NAME in result
    assert result[_KEY_NAME] == "mylib"


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "sep",
    [
        # '=' — новый формат манифестов
        pytest.param(_SEP_EQ, id="equals"),
        # ':' — устаревший формат
        pytest.param(_SEP_COLON, id="colon"),
    ],
)
def test_properties_reader_detect_separator(tmp_path: Path, sep: str) -> None:
    """Строки вида 'key<sep>value' используют <sep> в качестве разделителя ключ-значение."""
    props_file: Path = tmp_path / "component.properties"
    props_file.write_text(
        f"{_KEY_NAME}{sep}mylib\n{_KEY_VERSION}{sep}1.0.0\n",
        encoding="utf-8",
    )
    result: dict[str, str] = read_properties(props_file)
    assert result[_KEY_NAME] == "mylib"
    assert result[_KEY_VERSION] == "1.0.0"
    assert _detect_separator(f"{_KEY_NAME}{sep}mylib") == sep


@pytest.mark.business_logic
def test_properties_reader_mixed_separators_uses_documented_rule(
    tmp_path: Path,
) -> None:
    """Каждая строка файла разбирается независимо своим собственным разделителем."""
    props_file: Path = tmp_path / "mixed.properties"
    # Строка 1 использует '='; строка 2 использует ':'.
    props_file.write_text(
        f"{_KEY_NAME}=mylib\n{_KEY_VERSION}:1.0.0\n",
        encoding="utf-8",
    )
    result: dict[str, str] = read_properties(props_file)
    assert result[_KEY_NAME] == "mylib"
    assert result[_KEY_VERSION] == "1.0.0"


@pytest.mark.business_logic
def test_properties_reader_skips_comment_lines(tmp_path: Path) -> None:
    """Строки-комментарии (начинающиеся с '#') не попадают в результат разбора."""
    props_file: Path = tmp_path / "component.properties"
    props_file.write_text(
        f"# это комментарий\n{_KEY_NAME}=mylib\n# ещё один комментарий\n",
        encoding="utf-8",
    )
    result: dict[str, str] = read_properties(props_file)
    assert result == {_KEY_NAME: "mylib"}


@pytest.mark.business_logic
def test_properties_reader_skips_blank_lines(tmp_path: Path) -> None:
    """Пустые строки между записями игнорируются и не влияют на результат."""
    props_file: Path = tmp_path / "component.properties"
    props_file.write_text(
        f"{_KEY_NAME}=mylib\n\n\n{_KEY_VERSION}=1.0.0\n",
        encoding="utf-8",
    )
    result: dict[str, str] = read_properties(props_file)
    assert result == {_KEY_NAME: "mylib", _KEY_VERSION: "1.0.0"}


@pytest.mark.business_logic
def test_properties_reader_line_without_separator_is_skipped(tmp_path: Path) -> None:
    """Строка без '=' и без ':' молча пропускается и не попадает в результат."""
    props_file: Path = tmp_path / "component.properties"
    props_file.write_text(
        f"garbage line without separator\n{_KEY_NAME}=mylib\n",
        encoding="utf-8",
    )
    result: dict[str, str] = read_properties(props_file)
    assert result == {_KEY_NAME: "mylib"}
