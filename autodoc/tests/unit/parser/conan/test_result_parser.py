"""
Unit tests for autodoc/parser/conan/result_parser.py.

Covers ConanResultParser.parse() — happy path, missing-binary,
missing-node, root-node skipping, and field extraction.
JSON fixtures are loaded via the shared resources_dir fixture.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from autodoc.models.component import ProfileBuild, Release
from autodoc.parser.conan.result_parser import ConanResultParser
from autodoc.parser.conan.task_builder import ConanTask

# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def conan_task() -> ConanTask:
    """Minimal ConanTask targeting benchmark/1.9.4.549 in graph_info_success.json."""
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
    """Parsed contents of graph_info_success.json."""
    return json.loads((resources_dir / "conan" / "graph_info_success.json").read_text())


@pytest.fixture
def missing_json(resources_dir: Path) -> dict[str, Any]:
    """Parsed contents of graph_info_missing.json (libyang with binary=Missing)."""
    return json.loads((resources_dir / "conan" / "graph_info_missing.json").read_text())


# ---------------------------------------------------------------------------
# 2.1
# ---------------------------------------------------------------------------


def test_result_parser_returns_enrich_data_on_success(
    success_json: dict[str, Any],
    conan_task: ConanTask,
) -> None:
    """parse() returns ConanEnrichData with the expected package_id on success."""
    result = ConanResultParser().parse(success_json, conan_task)

    assert result is not None
    assert result.package_id == "575ea8086554107ae2c0fdbb4909d62390c52b77"


# ---------------------------------------------------------------------------
# 2.2
# ---------------------------------------------------------------------------


def test_result_parser_returns_none_on_missing_binary(
    missing_json: dict[str, Any],
    conan_task: ConanTask,
) -> None:
    """parse() returns None when the target node has binary='Missing'."""
    # graph_info_missing.json targets libyang
    object.__setattr__(conan_task, "comp_name", "libyang")
    result = ConanResultParser().parse(missing_json, conan_task)

    assert result is None


# ---------------------------------------------------------------------------
# 2.3
# ---------------------------------------------------------------------------


def test_result_parser_returns_none_when_node_not_found(
    success_json: dict[str, Any],
    conan_task: ConanTask,
) -> None:
    """parse() returns None when no node matches comp_name."""
    object.__setattr__(conan_task, "comp_name", "nonexistent")
    result = ConanResultParser().parse(success_json, conan_task)

    assert result is None


# ---------------------------------------------------------------------------
# 2.4
# ---------------------------------------------------------------------------


def test_result_parser_skips_root_node(conan_task: ConanTask) -> None:
    """Node '0' with name=null is never matched, even when it's the only node."""
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
# 2.5
# ---------------------------------------------------------------------------


def test_result_parser_extracts_base_ref(
    success_json: dict[str, Any],
    conan_task: ConanTask,
) -> None:
    """base_ref starts with 'benchmark/' and contains no '#' revision hash."""
    result = ConanResultParser().parse(success_json, conan_task)

    assert result is not None
    assert result.base_ref.startswith("benchmark/")
    assert "#" not in result.base_ref


# ---------------------------------------------------------------------------
# 2.6
# ---------------------------------------------------------------------------


def test_result_parser_extracts_conan_settings(
    success_json: dict[str, Any],
    conan_task: ConanTask,
) -> None:
    """conan_settings is a non-empty dict containing at least 'os' or 'arch'."""
    result = ConanResultParser().parse(success_json, conan_task)

    assert result is not None
    assert isinstance(result.conan_settings, dict)
    assert result.conan_settings, "conan_settings must not be empty"
    assert "os" in result.conan_settings or "arch" in result.conan_settings


# ---------------------------------------------------------------------------
# 2.7
# ---------------------------------------------------------------------------


def test_result_parser_handles_null_default_options(conan_task: ConanTask) -> None:
    """A node with default_options=null must yield an empty default_options list."""
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
