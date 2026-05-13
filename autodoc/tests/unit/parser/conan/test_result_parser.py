"""
Юнит-тесты для autodoc/parser/conan/result_parser.py.

Охватывает ConanResultParser.parse() — успешный путь (patchelf, nlohmann_json,
sqlite3, libnetfilter_queue), бинарник Missing (poco), отсутствующий узел,
пропуск корневого узла и извлечение полей.
JSON-фикстуры загружаются через общую фикстуру resources_dir.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.release import Release
from autodoc.parser.conan.result_parser import ConanResultParser
from autodoc.parser.conan.models.conan_task import ConanTask

# NULL_PACKAGE_ID — SHA1 пустой строки (header-only компоненты)
NULL_PACKAGE_ID: str = "da39a3ee5e6b4b0d3255bfef95601890afd80709"

# ---------------------------------------------------------------------------
# Fixtures — ConanTask per component
# ---------------------------------------------------------------------------


@pytest.fixture
def conan_task() -> ConanTask:
    """Minimal ConanTask for patchelf/0.18.0 from graph_info_success.json."""
    release = Release(version="0.18.0", platform="2.0", channel="tech", git_url="")
    pb = ProfileBuild(profile_name="crypto_alpine_gcc_x86_64.jinja")
    return ConanTask(
        cmd=["conan", "graph", "info"],
        comp_name="patchelf",
        version="0.18.0",
        channel="tech",
        profile_name="crypto_alpine_gcc_x86_64.jinja",
        option_id="1",
        option_str="",
        target_platform="2.0",
        artifactory_base_url="https://art.example.com",
        release=release,
        pb=pb,
    )


@pytest.fixture
def nlohmann_task() -> ConanTask:
    """Minimal ConanTask for nlohmann_json/3.9.1 (header-only)."""
    release = Release(version="3.9.1", platform="2.0", channel="slow", git_url="")
    pb = ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")
    return ConanTask(
        cmd=[],
        comp_name="nlohmann_json",
        version="3.9.1",
        channel="slow",
        profile_name="hw-linux-x86_64-gcc10_2",
        option_id="1",
        option_str="",
        target_platform="2.0",
        artifactory_base_url="https://art.example.com",
        release=release,
        pb=pb,
    )


@pytest.fixture
def sqlite3_task() -> ConanTask:
    """Minimal ConanTask for sqlite3/3.51.2 with tcl dependency."""
    release = Release(version="3.51.2", platform="2.0", channel="fast", git_url="")
    pb = ProfileBuild(profile_name="crypto_default_gcc_armv7hf.jinja")
    return ConanTask(
        cmd=[],
        comp_name="sqlite3",
        version="3.51.2",
        channel="fast",
        profile_name="crypto_default_gcc_armv7hf.jinja",
        option_id="1",
        option_str="",
        target_platform="2.0",
        artifactory_base_url="https://art.example.com",
        release=release,
        pb=pb,
    )


@pytest.fixture
def libnetfilter_queue_task() -> ConanTask:
    """Minimal ConanTask for libnetfilter_queue/1.0.5 (PRG_Quant project)."""
    release = Release(version="1.0.5", platform="2.0", channel="slow", git_url="")
    pb = ProfileBuild(profile_name="hw-linux-armv7-gcc10_2")
    return ConanTask(
        cmd=[],
        comp_name="libnetfilter_queue",
        version="1.0.5",
        channel="slow",
        profile_name="hw-linux-armv7-gcc10_2",
        option_id="1",
        option_str="",
        target_platform="2.0",
        artifactory_base_url="https://art.example.com",
        release=release,
        pb=pb,
    )


@pytest.fixture
def poco_task() -> ConanTask:
    """Minimal ConanTask for poco/1.10.0 where binary=Missing."""
    release = Release(version="1.10.0", platform="2.0", channel="slow", git_url="")
    pb = ProfileBuild(profile_name="hw-linux-armv7-gcc10_2")
    return ConanTask(
        cmd=[],
        comp_name="poco",
        version="1.10.0",
        channel="slow",
        profile_name="hw-linux-armv7-gcc10_2",
        option_id="1",
        option_str="",
        target_platform="2.0",
        artifactory_base_url="https://art.example.com",
        release=release,
        pb=pb,
    )


# ---------------------------------------------------------------------------
# Fixtures — parsed JSON graphs
# ---------------------------------------------------------------------------


@pytest.fixture
def success_json(resources_dir: Path) -> dict[str, Any]:
    """Parsed content of graph_info_success.json (patchelf, tech channel)."""
    return json.loads((resources_dir / "conan" / "graph_info_success.json").read_text())


@pytest.fixture
def missing_json(resources_dir: Path) -> dict[str, Any]:
    """Parsed content of graph_info_missing.json (libyang with binary=Missing)."""
    return json.loads((resources_dir / "conan" / "graph_info_missing.json").read_text())


@pytest.fixture
def nlohmann_json_graph(resources_dir: Path) -> dict[str, Any]:
    """Parsed content of graph_info_nlohmann_json.json (header-only, NULL_PACKAGE_ID)."""
    return json.loads((resources_dir / "conan" / "graph_info_nlohmann_json.json").read_text())


@pytest.fixture
def sqlite3_deps_graph(resources_dir: Path) -> dict[str, Any]:
    """Parsed content of graph_info_sqlite3_with_deps.json (sqlite3 with tcl dep)."""
    return json.loads((resources_dir / "conan" / "graph_info_sqlite3_with_deps.json").read_text())


@pytest.fixture
def libnetfilter_queue_graph(resources_dir: Path) -> dict[str, Any]:
    """Parsed content of graph_info_libnetfilter_queue.json (libmnl + libnfnetlink deps)."""
    return json.loads((resources_dir / "conan" / "graph_info_libnetfilter_queue.json").read_text())


@pytest.fixture
def poco_missing_graph(resources_dir: Path) -> dict[str, Any]:
    """Parsed content of graph_info_poco_missing.json (poco with binary=Missing)."""
    return json.loads((resources_dir / "conan" / "graph_info_poco_missing.json").read_text())


# ---------------------------------------------------------------------------
# patchelf — tech channel, real Alpine Linux profile
# ---------------------------------------------------------------------------


def test_result_parser_patchelf_returns_enrich_data(
    success_json: dict[str, Any],
    conan_task: ConanTask,
) -> None:
    """parse() returns ConanEnrichData with correct patchelf package_id on success."""
    result = ConanResultParser().parse(success_json, conan_task)

    assert result is not None
    assert result.package_id == "461534fe50686ce31d073dc24f005bd12e08c9fd"


def test_result_parser_patchelf_base_ref_no_hash(
    success_json: dict[str, Any],
    conan_task: ConanTask,
) -> None:
    """base_ref starts with 'patchelf/' and contains no '#' revision hash."""
    result = ConanResultParser().parse(success_json, conan_task)

    assert result is not None
    assert result.base_ref.startswith("patchelf/")
    assert "#" not in result.base_ref


def test_result_parser_patchelf_conan_settings_has_os_distro(
    success_json: dict[str, Any],
    conan_task: ConanTask,
) -> None:
    """conan_settings contains os.distro='alpine' from real Alpine Linux profile."""
    result = ConanResultParser().parse(success_json, conan_task)

    assert result is not None
    assert result.conan_settings.get("os.distro") == "alpine"


def test_result_parser_patchelf_empty_default_options(
    success_json: dict[str, Any],
    conan_task: ConanTask,
) -> None:
    """patchelf has no default_options in graph JSON — result must be an empty list."""
    result = ConanResultParser().parse(success_json, conan_task)

    assert result is not None
    assert result.default_options == []


# ---------------------------------------------------------------------------
# nlohmann_json — header-only (NULL_PACKAGE_ID)
# ---------------------------------------------------------------------------


def test_result_parser_nlohmann_json_null_package_id(
    nlohmann_json_graph: dict[str, Any],
    nlohmann_task: ConanTask,
) -> None:
    """nlohmann_json returns the SHA1 NULL_PACKAGE_ID characteristic of header-only libs."""
    result = ConanResultParser().parse(nlohmann_json_graph, nlohmann_task)

    assert result is not None
    assert result.package_id == NULL_PACKAGE_ID


def test_result_parser_nlohmann_json_no_default_options(
    nlohmann_json_graph: dict[str, Any],
    nlohmann_task: ConanTask,
) -> None:
    """nlohmann_json has empty default_options dict in JSON — result must be []."""
    result = ConanResultParser().parse(nlohmann_json_graph, nlohmann_task)

    assert result is not None
    assert result.default_options == []


def test_result_parser_nlohmann_json_no_dependencies(
    nlohmann_json_graph: dict[str, Any],
    nlohmann_task: ConanTask,
) -> None:
    """nlohmann_json has no dependency nodes — dependencies list must be empty."""
    result = ConanResultParser().parse(nlohmann_json_graph, nlohmann_task)

    assert result is not None
    assert result.dependencies == []


# ---------------------------------------------------------------------------
# sqlite3 — component with tcl dependency
# ---------------------------------------------------------------------------


def test_result_parser_sqlite3_has_tcl_dependency(
    sqlite3_deps_graph: dict[str, Any],
    sqlite3_task: ConanTask,
) -> None:
    """sqlite3 graph contains a tcl dependency node — it appears in result.dependencies."""
    result = ConanResultParser().parse(sqlite3_deps_graph, sqlite3_task)

    assert result is not None
    assert "tcl" in result.dependencies


def test_result_parser_sqlite3_has_default_options(
    sqlite3_deps_graph: dict[str, Any],
    sqlite3_task: ConanTask,
) -> None:
    """sqlite3 has multiple default_options including 'shared' — list must be non-empty."""
    result = ConanResultParser().parse(sqlite3_deps_graph, sqlite3_task)

    assert result is not None
    assert len(result.default_options) > 0
    names = [opt.name for opt in result.default_options]
    assert "shared" in names


def test_result_parser_sqlite3_dependency_nodes_not_matched(
    sqlite3_deps_graph: dict[str, Any],
    sqlite3_task: ConanTask,
) -> None:
    """parse() matches only node '1' (sqlite3); node '2' (tcl) is skipped as a dependency."""
    result = ConanResultParser().parse(sqlite3_deps_graph, sqlite3_task)

    assert result is not None
    assert result.package_id == "8c7b3c7905519eea8fda5ff9dde7fbefec90da76"


# ---------------------------------------------------------------------------
# libnetfilter_queue — PRG_Quant project with two deps
# ---------------------------------------------------------------------------


def test_result_parser_libnetfilter_queue_returns_result(
    libnetfilter_queue_graph: dict[str, Any],
    libnetfilter_queue_task: ConanTask,
) -> None:
    """libnetfilter_queue parse() returns a result with correct package_id."""
    result = ConanResultParser().parse(libnetfilter_queue_graph, libnetfilter_queue_task)

    assert result is not None
    assert result.package_id == "46bf0ba807876c7591c702abfa2ba19d3133f1af"


def test_result_parser_libnetfilter_queue_two_deps(
    libnetfilter_queue_graph: dict[str, Any],
    libnetfilter_queue_task: ConanTask,
) -> None:
    """libnetfilter_queue graph has libmnl and libnfnetlink nodes — both appear in dependencies."""
    result = ConanResultParser().parse(libnetfilter_queue_graph, libnetfilter_queue_task)

    assert result is not None
    assert "libmnl" in result.dependencies
    assert "libnfnetlink" in result.dependencies


# ---------------------------------------------------------------------------
# poco — binary=Missing returns None
# ---------------------------------------------------------------------------


def test_result_parser_poco_missing_binary_returns_none(
    poco_missing_graph: dict[str, Any],
    poco_task: ConanTask,
) -> None:
    """parse() returns None when the target node has binary='Missing' (poco case)."""
    result = ConanResultParser().parse(poco_missing_graph, poco_task)

    assert result is None


# ---------------------------------------------------------------------------
# Generic edge cases (KEEP)
# ---------------------------------------------------------------------------


def test_result_parser_returns_none_when_node_not_found(
    success_json: dict[str, Any],
    conan_task: ConanTask,
) -> None:
    """parse() returns None when no node matches the given comp_name."""
    object.__setattr__(conan_task, "comp_name", "nonexistent")
    result = ConanResultParser().parse(success_json, conan_task)

    assert result is None


def test_result_parser_returns_none_on_missing_binary(
    missing_json: dict[str, Any],
    conan_task: ConanTask,
) -> None:
    """parse() returns None when the target node has binary='Missing' (libyang case)."""
    object.__setattr__(conan_task, "comp_name", "libyang")
    result = ConanResultParser().parse(missing_json, conan_task)

    assert result is None


def test_result_parser_skips_root_node(conan_task: ConanTask) -> None:
    """Node '0' with name=null is never matched, even if it is the only node."""
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


def test_result_parser_handles_null_default_options(conan_task: ConanTask) -> None:
    """A node with default_options=null must return an empty list for default_options."""
    minimal_json: dict[str, Any] = {
        "graph": {
            "nodes": {
                "0": {"name": None, "binary": None},
                "1": {
                    "name": "patchelf",
                    "binary": "Download",
                    "ref": "patchelf/0.18.0@platform-2.0/tech#abc123",
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
