"""Unit tests for autodoc/parser/utils/properties_reader.py.

Tests cover line continuation, separator detection, and edge cases
that are invisible when testing through ManifestParser.
All file I/O uses tmp_path — no fixture files from disk.
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


def test_properties_reader_line_continuation(tmp_path: Path) -> None:
    """A value split over two physical lines is joined into one logical value.

    Guards against regressions in the backslash-continuation parser: the
    concatenated value must equal the expected string and contain no backslash.
    """
    props_file: Path = tmp_path / "component.properties"
    props_file.write_text(
        f"{_KEY_NAME}=first-part-\\\nsecond-part\n",
        encoding="utf-8",
    )
    result: dict[str, str] = read_properties(props_file)
    assert _KEY_NAME in result
    assert result[_KEY_NAME] == _VALUE_LONG
    assert "\\" not in result[_KEY_NAME]


def test_properties_reader_colon_in_value_with_equals_separator(
    tmp_path: Path,
) -> None:
    """A colon inside the value is not treated as a key-value separator.

    When the line uses '=' as separator, the colon in a URL value must survive
    intact — only the first '=' should split the line.
    """
    props_file: Path = tmp_path / "component.properties"
    props_file.write_text(
        f"component.url={_VALUE_URL}\n",
        encoding="utf-8",
    )
    result: dict[str, str] = read_properties(props_file)
    assert result["component.url"] == _VALUE_URL


def test_properties_reader_file_without_trailing_newline(tmp_path: Path) -> None:
    """The last key is parsed even when the file has no trailing newline.

    Some editors and Git operations strip the final newline; the parser must
    not silently drop the last entry in that case.
    """
    props_file: Path = tmp_path / "component.properties"
    props_file.write_bytes(b"component.name=mylib")  # no trailing \n
    result: dict[str, str] = read_properties(props_file)
    assert _KEY_NAME in result
    assert result[_KEY_NAME] == "mylib"


def test_properties_reader_detect_separator_equals(tmp_path: Path) -> None:
    """Files with 'key=value' lines use '=' as the separator.

    Ensures that _detect_separator correctly identifies '=' when it
    appears before any ':' in the line.
    """
    props_file: Path = tmp_path / "component.properties"
    props_file.write_text(
        f"{_KEY_NAME}=mylib\n{_KEY_VERSION}=1.0.0\n",
        encoding="utf-8",
    )
    result: dict[str, str] = read_properties(props_file)
    # Separator must have been '=': both keys are parsed correctly.
    assert result[_KEY_NAME] == "mylib"
    assert result[_KEY_VERSION] == "1.0.0"
    # Also test _detect_separator directly.
    assert _detect_separator(f"{_KEY_NAME}=mylib") == _SEP_EQ


def test_properties_reader_detect_separator_colon(tmp_path: Path) -> None:
    """Files with 'key:value' lines use ':' as the separator.

    Verifies the legacy colon-separator format is handled correctly when
    no '=' character appears in the line.
    """
    props_file: Path = tmp_path / "component.properties"
    props_file.write_text(
        f"{_KEY_NAME}:mylib\n{_KEY_VERSION}:1.0.0\n",
        encoding="utf-8",
    )
    result: dict[str, str] = read_properties(props_file)
    assert result[_KEY_NAME] == "mylib"
    assert result[_KEY_VERSION] == "1.0.0"
    # Also test _detect_separator directly.
    assert _detect_separator(f"{_KEY_NAME}:mylib") == _SEP_COLON


def test_properties_reader_mixed_separators_uses_documented_rule(
    tmp_path: Path,
) -> None:
    """Mixed separators: each line is resolved independently — the separator
    with the earlier position wins (= before : → use =; only : present → use :).

    The implementation uses _detect_separator per-line, which applies the
    following rule: if '=' appears before ':', use '='; if only ':' is present,
    use ':'. This is tested by mixing one '='-line and one ':'-line and asserting
    both keys are parsed correctly under their respective separators.
    """
    props_file: Path = tmp_path / "mixed.properties"
    # Line 1 uses '='; line 2 uses ':'.
    props_file.write_text(
        f"{_KEY_NAME}=mylib\n{_KEY_VERSION}:1.0.0\n",
        encoding="utf-8",
    )
    result: dict[str, str] = read_properties(props_file)
    # Each line is split by its own detected separator.
    assert result[_KEY_NAME] == "mylib"
    assert result[_KEY_VERSION] == "1.0.0"
