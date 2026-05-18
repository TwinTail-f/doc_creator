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
    release = Release(version="0.18.0", platform="2.0", channel="tech")
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
    release = Release(version="3.9.1", platform="2.0", channel="slow")
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
    release = Release(version="3.51.2", platform="2.0", channel="fast")
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
    release = Release(version="1.0.5", platform="2.0", channel="slow")
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
    release = Release(version="1.10.0", platform="2.0", channel="slow")
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
    return json.loads(
        (resources_dir / "conan" / "graph_info_nlohmann_json.json").read_text()
    )


@pytest.fixture
def sqlite3_deps_graph(resources_dir: Path) -> dict[str, Any]:
    """Parsed content of graph_info_sqlite3_with_deps.json (sqlite3 with tcl dep)."""
    return json.loads(
        (resources_dir / "conan" / "graph_info_sqlite3_with_deps.json").read_text()
    )


@pytest.fixture
def libnetfilter_queue_graph(resources_dir: Path) -> dict[str, Any]:
    """Parsed content of graph_info_libnetfilter_queue.json (libmnl + libnfnetlink deps)."""
    return json.loads(
        (resources_dir / "conan" / "graph_info_libnetfilter_queue.json").read_text()
    )


@pytest.fixture
def poco_missing_graph(resources_dir: Path) -> dict[str, Any]:
    """Parsed content of graph_info_poco_missing.json (poco with binary=Missing)."""
    return json.loads(
        (resources_dir / "conan" / "graph_info_poco_missing.json").read_text()
    )


# ---------------------------------------------------------------------------
# patchelf — tech channel, real Alpine Linux profile
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_result_parser_patchelf_returns_enrich_data(
    success_json: dict[str, Any],
    conan_task: ConanTask,
) -> None:
    """parse() returns ConanEnrichData with correct patchelf package_id on success."""
    result = ConanResultParser().parse(success_json, conan_task)

    assert result is not None
    assert result.package_id == "461534fe50686ce31d073dc24f005bd12e08c9fd"


@pytest.mark.business_logic
def test_result_parser_patchelf_base_ref_no_hash(
    success_json: dict[str, Any],
    conan_task: ConanTask,
) -> None:
    """base_ref starts with 'patchelf/' and contains no '#' revision hash."""
    result = ConanResultParser().parse(success_json, conan_task)

    assert result is not None
    assert result.base_ref.startswith("patchelf/")
    assert "#" not in result.base_ref


@pytest.mark.business_logic
def test_result_parser_patchelf_conan_settings_has_os_distro(
    success_json: dict[str, Any],
    conan_task: ConanTask,
) -> None:
    """conan_settings contains os.distro='alpine' from real Alpine Linux profile."""
    result = ConanResultParser().parse(success_json, conan_task)

    assert result is not None
    assert result.conan_settings.get("os.distro") == "alpine"


@pytest.mark.business_logic
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


@pytest.mark.business_logic
def test_result_parser_nlohmann_json_null_package_id(
    nlohmann_json_graph: dict[str, Any],
    nlohmann_task: ConanTask,
) -> None:
    """nlohmann_json returns the SHA1 NULL_PACKAGE_ID characteristic of header-only libs."""
    result = ConanResultParser().parse(nlohmann_json_graph, nlohmann_task)

    assert result is not None
    assert result.package_id == NULL_PACKAGE_ID


@pytest.mark.business_logic
def test_result_parser_nlohmann_json_no_default_options(
    nlohmann_json_graph: dict[str, Any],
    nlohmann_task: ConanTask,
) -> None:
    """nlohmann_json has empty default_options dict in JSON — result must be []."""
    result = ConanResultParser().parse(nlohmann_json_graph, nlohmann_task)

    assert result is not None
    assert result.default_options == []


@pytest.mark.business_logic
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


@pytest.mark.business_logic
def test_result_parser_sqlite3_has_tcl_dependency(
    sqlite3_deps_graph: dict[str, Any],
    sqlite3_task: ConanTask,
) -> None:
    """sqlite3 graph contains a tcl dependency node — it appears in result.dependencies."""
    result = ConanResultParser().parse(sqlite3_deps_graph, sqlite3_task)

    assert result is not None
    assert "tcl" in result.dependencies


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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


@pytest.mark.business_logic
def test_result_parser_libnetfilter_queue_returns_result(
    libnetfilter_queue_graph: dict[str, Any],
    libnetfilter_queue_task: ConanTask,
) -> None:
    """libnetfilter_queue parse() returns a result with correct package_id."""
    result = ConanResultParser().parse(
        libnetfilter_queue_graph, libnetfilter_queue_task
    )

    assert result is not None
    assert result.package_id == "46bf0ba807876c7591c702abfa2ba19d3133f1af"


@pytest.mark.business_logic
def test_result_parser_libnetfilter_queue_two_deps(
    libnetfilter_queue_graph: dict[str, Any],
    libnetfilter_queue_task: ConanTask,
) -> None:
    """libnetfilter_queue graph has libmnl and libnfnetlink nodes — both appear in dependencies."""
    result = ConanResultParser().parse(
        libnetfilter_queue_graph, libnetfilter_queue_task
    )

    assert result is not None
    assert "libmnl" in result.dependencies
    assert "libnfnetlink" in result.dependencies


# ---------------------------------------------------------------------------
# poco — binary=Missing returns None
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
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


@pytest.mark.business_logic
def test_result_parser_returns_none_when_node_not_found(
    success_json: dict[str, Any],
    conan_task: ConanTask,
) -> None:
    """parse() returns None when no node matches the given comp_name."""
    object.__setattr__(conan_task, "comp_name", "nonexistent")
    result = ConanResultParser().parse(success_json, conan_task)

    assert result is None


@pytest.mark.business_logic
def test_result_parser_returns_none_on_missing_binary(
    missing_json: dict[str, Any],
    conan_task: ConanTask,
) -> None:
    """parse() returns None when the target node has binary='Missing' (libyang case)."""
    object.__setattr__(conan_task, "comp_name", "libyang")
    result = ConanResultParser().parse(missing_json, conan_task)

    assert result is None


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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


@pytest.mark.business_logic
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


# ---------------------------------------------------------------------------
# UC-G-1 — Header-only: NULL_PACKAGE_ID is SHA1 of empty string
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_result_parser_nlohmann_json_package_id_equals_null_sha1(
    nlohmann_json_graph: dict[str, Any],
    nlohmann_task: ConanTask,
) -> None:
    """NULL_PACKAGE_ID value is the SHA1 of empty string — confirms header-only detection."""
    result = ConanResultParser().parse(nlohmann_json_graph, nlohmann_task)
    assert result is not None
    assert result.package_id == "da39a3ee5e6b4b0d3255bfef95601890afd80709"
    assert len(result.package_id) == 40


# ---------------------------------------------------------------------------
# UC-G-2 — Two versions, same channel: patchelf 0.16.1 matches same graph node
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_result_parser_patchelf_016_version_uses_same_channel(
    success_json: dict[str, Any],
) -> None:
    """ConanResultParser handles patchelf 0.16.1/tech the same way as 0.18.0/tech.

    Re-uses graph_info_success.json (which has a patchelf node) but with a task
    whose version is '0.16.1'. The parser matches on name, not version, so the
    same graph node is found and parsed successfully.
    """
    release = Release(version="0.16.1", platform="2.0", channel="tech")
    pb = ProfileBuild(profile_name="crypto_alpine_gcc_x86_64.jinja")
    task_016 = ConanTask(
        cmd=[],
        comp_name="patchelf",
        version="0.16.1",
        channel="tech",
        profile_name="crypto_alpine_gcc_x86_64.jinja",
        option_id="1",
        option_str="",
        target_platform="2.0",
        artifactory_base_url="https://art.example.com",
        release=release,
        pb=pb,
    )
    result = ConanResultParser().parse(success_json, task_016)
    assert result is not None
    assert result.base_ref.startswith("patchelf/")
    assert result.conan_settings.get("os.distro") == "alpine"


# ---------------------------------------------------------------------------
# UC-G-3 — Standard component, one version per channel: sqlite3 fast base_ref
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_result_parser_sqlite3_fast_base_ref_format(
    sqlite3_deps_graph: dict[str, Any],
    sqlite3_task: ConanTask,
) -> None:
    """sqlite3 fast base_ref has format 'sqlite3/<version>@platform-2.0/fast' without rrev hash."""
    result = ConanResultParser().parse(sqlite3_deps_graph, sqlite3_task)
    assert result is not None
    assert result.base_ref.startswith("sqlite3/")
    assert "@platform-2.0/fast" in result.base_ref
    assert "#" not in result.base_ref


# ---------------------------------------------------------------------------
# UC-G-4 — Pure fast channel, no dependencies: apr/1.7.6
# ---------------------------------------------------------------------------


@pytest.fixture
def apr_task() -> ConanTask:
    """Minimal ConanTask for apr/1.7.6 (fast channel, no dependencies)."""
    release = Release(version="1.7.6", platform="2.0", channel="fast")
    pb = ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")
    return ConanTask(
        cmd=[],
        comp_name="apr",
        version="1.7.6",
        channel="fast",
        profile_name="hw-linux-x86_64-gcc10_2",
        option_id="1",
        option_str="apr:shared=True",
        target_platform="2.0",
        artifactory_base_url="https://art.example.com",
        release=release,
        pb=pb,
    )


@pytest.fixture
def apr_graph(resources_dir: Path) -> dict[str, Any]:
    """Parsed content of graph_info_apr.json (apr 1.7.6, fast channel, no deps)."""
    return json.loads((resources_dir / "conan" / "graph_info_apr.json").read_text())


@pytest.mark.business_logic
def test_result_parser_apr_returns_enrich_data(
    apr_graph: dict[str, Any],
    apr_task: ConanTask,
) -> None:
    """apr/1.7.6 (fast, no deps) parse() returns ConanEnrichData with correct package_id."""
    result = ConanResultParser().parse(apr_graph, apr_task)
    assert result is not None
    assert result.package_id == "7741115342fe6159bd16463d6d349e4c02e33237"


@pytest.mark.business_logic
def test_result_parser_apr_no_dependencies(
    apr_graph: dict[str, Any],
    apr_task: ConanTask,
) -> None:
    """apr has no dependency nodes — dependencies list must be empty."""
    result = ConanResultParser().parse(apr_graph, apr_task)
    assert result is not None
    assert result.dependencies == []


@pytest.mark.business_logic
def test_result_parser_apr_fast_channel_in_base_ref(
    apr_graph: dict[str, Any],
    apr_task: ConanTask,
) -> None:
    """apr base_ref must contain '@platform-2.0/fast' (fast channel, not slow or tech)."""
    result = ConanResultParser().parse(apr_graph, apr_task)
    assert result is not None
    assert "@platform-2.0/fast" in result.base_ref


@pytest.mark.business_logic
def test_result_parser_apr_has_default_options(
    apr_graph: dict[str, Any],
    apr_task: ConanTask,
) -> None:
    """apr node carries default_options (shared, fPIC, …) — list must be non-empty."""
    result = ConanResultParser().parse(apr_graph, apr_task)
    assert result is not None
    assert len(result.default_options) > 0
    names = [opt.name for opt in result.default_options]
    assert "shared" in names


# ---------------------------------------------------------------------------
# UC-G-5 — Dependencies: libnetfilter_queue dep names are plain (no version/@)
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_result_parser_libnetfilter_queue_deps_are_plain_names(
    libnetfilter_queue_graph: dict[str, Any],
    libnetfilter_queue_task: ConanTask,
) -> None:
    """Dependency entries in result.dependencies are bare component names (no version or @)."""
    result = ConanResultParser().parse(
        libnetfilter_queue_graph, libnetfilter_queue_task
    )
    assert result is not None
    for dep in result.dependencies:
        assert (
            "/" not in dep
        ), f"dependency '{dep}' should be a bare name, not a reference"
        assert "@" not in dep, f"dependency '{dep}' contains a conan reference part"


# ---------------------------------------------------------------------------
# UC-G-7 — Version-range resolution error: stunnel
# ---------------------------------------------------------------------------


@pytest.fixture
def stunnel_error_graph(resources_dir: Path) -> dict[str, Any]:
    """Parsed content of graph_info_stunnel_error.json (version range could not be resolved)."""
    return json.loads(
        (resources_dir / "conan" / "graph_info_stunnel_error.json").read_text()
    )


@pytest.fixture
def stunnel_task() -> ConanTask:
    """Minimal ConanTask for stunnel/5.77 where version range resolution fails."""
    release = Release(version="5.77", platform="2.0", channel="fast")
    pb = ProfileBuild(profile_name="crypto_default_gcc_x86_64.jinja")
    return ConanTask(
        cmd=[],
        comp_name="stunnel",
        version="5.77",
        channel="fast",
        profile_name="crypto_default_gcc_x86_64.jinja",
        option_id="1",
        option_str="",
        target_platform="2.0",
        artifactory_base_url="https://art.example.com",
        release=release,
        pb=pb,
    )


@pytest.mark.business_logic
def test_result_parser_stunnel_error_graph_returns_none(
    stunnel_error_graph: dict[str, Any],
    stunnel_task: ConanTask,
) -> None:
    """parse() returns None when the graph contains only root node and a graph.error block.

    This simulates a version-range resolution failure (e.g. stunnel/[~5.77,...] not found).
    The parser must not raise and must return None — no stunnel node exists in the graph.
    """
    result = ConanResultParser().parse(stunnel_error_graph, stunnel_task)
    assert result is None


@pytest.mark.business_logic
def test_result_parser_stunnel_error_graph_has_error_field(
    stunnel_error_graph: dict[str, Any],
) -> None:
    """The stunnel error fixture contains a non-null graph.error block."""
    error_block = stunnel_error_graph.get("graph", {}).get("error")
    assert error_block is not None
    assert "could not be resolved" in error_block.get("error", "")
