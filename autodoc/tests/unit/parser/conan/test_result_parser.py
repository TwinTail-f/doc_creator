"""
Юнит-тесты для autodoc/parser/conan/result_parser.py.

Охватывает ConanResultParser.parse() — успешный путь, отсутствующий
бинарник, отсутствующий узел, пропуск корневого узла и извлечение полей.
JSON-фикстуры загружаются через общую фикстуру resources_dir.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.release import Release
from autodoc.parser.conan.result_parser import ConanResultParser
from autodoc.models.conan_task import ConanTask

# ---------------------------------------------------------------------------
# Локальные фикстуры
# ---------------------------------------------------------------------------


@pytest.fixture
def conan_task() -> ConanTask:
    """Минимальный ConanTask для benchmark/1.9.4.549 из graph_info_success.json."""
    release = Release(version="1.9.4.549", platform="2.0", channel="tech", git_url="")
    pb = ProfileBuild(profile_name="hw-linux-armv7-gcc10_2")
    return ConanTask(
        cmd=["conan", "graph", "info"],
        comp_name="benchmark",
        version="1.9.4.549",
        channel="tech",
        profile_name="hw-linux-armv7-gcc10_2",
        option_id="1",
        option_str="shared=True",
        target_platform="2.0",
        artifactory_base_url="https://art.example.com",
        release=release,
        pb=pb,
    )


@pytest.fixture
def success_json(resources_dir: Path) -> dict[str, Any]:
    """Разобранное содержимое graph_info_success.json."""
    return json.loads((resources_dir / "conan" / "graph_info_success.json").read_text())


@pytest.fixture
def missing_json(resources_dir: Path) -> dict[str, Any]:
    """Разобранное содержимое graph_info_missing.json (libyang с binary=Missing)."""
    return json.loads((resources_dir / "conan" / "graph_info_missing.json").read_text())


# ---------------------------------------------------------------------------
# Успешный путь: parse() возвращает ConanEnrichData
# ---------------------------------------------------------------------------


def test_result_parser_returns_enrich_data_on_success(
    success_json: dict[str, Any],
    conan_task: ConanTask,
) -> None:
    """parse() возвращает ConanEnrichData с ожидаемым package_id при успехе."""
    result = ConanResultParser().parse(success_json, conan_task)

    assert result is not None
    assert result.package_id == "575ea8086554107ae2c0fdbb4909d62390c52b77"


# ---------------------------------------------------------------------------
# parse() возвращает None при binary=Missing
# ---------------------------------------------------------------------------


def test_result_parser_returns_none_on_missing_binary(
    missing_json: dict[str, Any],
    conan_task: ConanTask,
) -> None:
    """parse() возвращает None, когда целевой узел имеет binary='Missing'."""
    # graph_info_missing.json нацелен на libyang
    object.__setattr__(conan_task, "comp_name", "libyang")
    result = ConanResultParser().parse(missing_json, conan_task)

    assert result is None


# ---------------------------------------------------------------------------
# parse() возвращает None, если узел не найден
# ---------------------------------------------------------------------------


def test_result_parser_returns_none_when_node_not_found(
    success_json: dict[str, Any],
    conan_task: ConanTask,
) -> None:
    """parse() возвращает None, когда ни один узел не совпадает с comp_name."""
    object.__setattr__(conan_task, "comp_name", "nonexistent")
    result = ConanResultParser().parse(success_json, conan_task)

    assert result is None


# ---------------------------------------------------------------------------
# Корневой узел '0' никогда не совпадает
# ---------------------------------------------------------------------------


def test_result_parser_skips_root_node(conan_task: ConanTask) -> None:
    """Узел '0' с name=null никогда не совпадает, даже если он единственный."""
    minimal_json: dict[str, Any] = {
        "graph": {
            "nodes": {
                "0": {
                    "ref": "conanfile",
                    "name": None,
                    "binary": None,
                    "package_id": None,
                    "rrev": None,
                }
            }
        }
    }
    result = ConanResultParser().parse(minimal_json, conan_task)

    assert result is None


# ---------------------------------------------------------------------------
# Извлечение base_ref
# ---------------------------------------------------------------------------


def test_result_parser_extracts_base_ref(
    success_json: dict[str, Any],
    conan_task: ConanTask,
) -> None:
    """base_ref начинается с 'benchmark/' и не содержит хеша ревизии '#'."""
    result = ConanResultParser().parse(success_json, conan_task)

    assert result is not None
    assert result.base_ref.startswith("benchmark/")
    assert "#" not in result.base_ref


# ---------------------------------------------------------------------------
# Извлечение conan_settings
# ---------------------------------------------------------------------------


def test_result_parser_extracts_conan_settings(
    success_json: dict[str, Any],
    conan_task: ConanTask,
) -> None:
    """conan_settings — непустой словарь, содержащий как минимум 'os' или 'arch'."""
    result = ConanResultParser().parse(success_json, conan_task)

    assert result is not None
    assert isinstance(result.conan_settings, dict)
    assert result.conan_settings, "conan_settings must not be empty"
    assert "os" in result.conan_settings or "arch" in result.conan_settings


# ---------------------------------------------------------------------------
# Узел с default_options=null возвращает пустой список
# ---------------------------------------------------------------------------


def test_result_parser_handles_null_default_options(conan_task: ConanTask) -> None:
    """Узел с default_options=null должен возвращать пустой список default_options."""
    minimal_json: dict[str, Any] = {
        "graph": {
            "nodes": {
                "0": {"name": None, "binary": None},
                "1": {
                    "name": "benchmark",
                    "binary": "Download",
                    "ref": "benchmark/1.9.4.549@platform-2.0/tech#abc123",
                    "rrev": "abc123",
                    "package_id": "deadbeef",
                    "default_options": None,
                    "info": {"settings": {"os": "Linux"}, "options": {}},
                },
            }
        }
    }
    result = ConanResultParser().parse(minimal_json, conan_task)

    assert result is not None
    assert result.default_options == []
