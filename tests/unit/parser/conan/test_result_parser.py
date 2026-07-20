"""
Юнит-тесты для autodoc/parser/conan/conan2_result_parser.py.

Охватывает Conan2ResultParser.parse() — успешный путь (patchelf, nlohmann_json,
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
from autodoc.parser.conan.conan2_result_parser import Conan2ResultParser
from autodoc.parser.conan.models.conan_task import ConanTask

# SHA1 пустой строки — используется для header-only компонентов
NULL_PACKAGE_ID: str = "da39a3ee5e6b4b0d3255bfef95601890afd80709"


@pytest.fixture
def conan_task() -> ConanTask:
    """Минимальный ConanTask для patchelf/0.18.0 из graph_info_success.json."""
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
    """Минимальный ConanTask для nlohmann_json/3.9.1 (header-only)."""
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
    """Минимальный ConanTask для sqlite3/3.51.2 с зависимостью tcl."""
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
    """Минимальный ConanTask для libnetfilter_queue/1.0.5 (проект PRG_Quant)."""
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
    """Минимальный ConanTask для poco/1.10.0, у которого binary=Missing."""
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


@pytest.fixture
def success_json(resources_dir: Path) -> dict[str, Any]:
    """Содержимое graph_info_success.json (patchelf, канал tech)."""
    return json.loads((resources_dir / "conan" / "graph_info_success.json").read_text())


@pytest.fixture
def missing_json(resources_dir: Path) -> dict[str, Any]:
    """Содержимое graph_info_missing.json (libyang с binary=Missing)."""
    return json.loads((resources_dir / "conan" / "graph_info_missing.json").read_text())


@pytest.fixture
def nlohmann_json_graph(resources_dir: Path) -> dict[str, Any]:
    """Содержимое graph_info_nlohmann_json.json (header-only, NULL_PACKAGE_ID)."""
    return json.loads((resources_dir / "conan" / "graph_info_nlohmann_json.json").read_text())


@pytest.fixture
def sqlite3_deps_graph(resources_dir: Path) -> dict[str, Any]:
    """Содержимое graph_info_sqlite3_with_deps.json (sqlite3 с зависимостью tcl)."""
    return json.loads((resources_dir / "conan" / "graph_info_sqlite3_with_deps.json").read_text())


@pytest.fixture
def libnetfilter_queue_graph(resources_dir: Path) -> dict[str, Any]:
    """Содержимое graph_info_libnetfilter_queue.json (зависимости libmnl + libnfnetlink)."""
    return json.loads((resources_dir / "conan" / "graph_info_libnetfilter_queue.json").read_text())


@pytest.fixture
def poco_missing_graph(resources_dir: Path) -> dict[str, Any]:
    """Содержимое graph_info_poco_missing.json (poco с binary=Missing)."""
    return json.loads((resources_dir / "conan" / "graph_info_poco_missing.json").read_text())


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "graph_fixture, task_fixture, expected_package_id",
    [
        pytest.param(
            "success_json", "conan_task", "461534fe50686ce31d073dc24f005bd12e08c9fd", id="patchelf"
        ),
        pytest.param(
            "libnetfilter_queue_graph",
            "libnetfilter_queue_task",
            "46bf0ba807876c7591c702abfa2ba19d3133f1af",
            id="libnetfilter_queue",
        ),
        pytest.param("apr_graph", "apr_task", "7741115342fe6159bd16463d6d349e4c02e33237", id="apr"),
    ],
)
def test_result_parser_returns_enrich_data_with_package_id(
    request: pytest.FixtureRequest,
    graph_fixture: str,
    task_fixture: str,
    expected_package_id: str,
) -> None:
    """parse() для разных компонентов (patchelf, libnetfilter_queue, apr)
    возвращает ConanEnrichData с ожидаемым package_id."""
    graph = request.getfixturevalue(graph_fixture)
    task = request.getfixturevalue(task_fixture)
    result = Conan2ResultParser().parse(graph, task)

    assert result is not None
    assert result.package_id == expected_package_id


@pytest.mark.business_logic
def test_result_parser_patchelf_base_ref_no_hash(
    success_json: dict[str, Any],
    conan_task: ConanTask,
) -> None:
    """base_ref начинается с 'patchelf/' и не содержит символа '#' (хэша ревизии)."""
    result = Conan2ResultParser().parse(success_json, conan_task)

    assert result is not None
    assert result.base_ref.startswith("patchelf/")
    assert "#" not in result.base_ref


@pytest.mark.business_logic
def test_result_parser_patchelf_conan_settings_has_os_distro(
    success_json: dict[str, Any],
    conan_task: ConanTask,
) -> None:
    """conan_settings содержит os.distro='alpine' из реального профиля Alpine Linux."""
    result = Conan2ResultParser().parse(success_json, conan_task)

    assert result is not None
    assert result.conan_settings.get("os.distro") == "alpine"


@pytest.mark.business_logic
def test_result_parser_patchelf_empty_default_options(
    success_json: dict[str, Any],
    conan_task: ConanTask,
) -> None:
    """patchelf не имеет default_options в graph JSON — результат должен быть пустым списком."""
    result = Conan2ResultParser().parse(success_json, conan_task)

    assert result is not None
    assert result.default_options == []


@pytest.mark.business_logic
def test_result_parser_nlohmann_json_null_package_id(
    nlohmann_json_graph: dict[str, Any],
    nlohmann_task: ConanTask,
) -> None:
    """nlohmann_json возвращает SHA1 NULL_PACKAGE_ID, характерный для header-only библиотек.

    NULL_PACKAGE_ID — это SHA1 пустой строки; Conan использует его как package_id
    для header-only компонентов, у которых нет бинарного пакета для конкретного профиля.
    """
    result = Conan2ResultParser().parse(nlohmann_json_graph, nlohmann_task)

    assert result is not None
    assert result.package_id == NULL_PACKAGE_ID


@pytest.mark.business_logic
def test_result_parser_nlohmann_json_no_default_options(
    nlohmann_json_graph: dict[str, Any],
    nlohmann_task: ConanTask,
) -> None:
    """nlohmann_json имеет пустой словарь default_options в JSON — результат должен быть []."""
    result = Conan2ResultParser().parse(nlohmann_json_graph, nlohmann_task)

    assert result is not None
    assert result.default_options == []


@pytest.mark.business_logic
def test_result_parser_nlohmann_json_no_dependencies(
    nlohmann_json_graph: dict[str, Any],
    nlohmann_task: ConanTask,
) -> None:
    """nlohmann_json не имеет узлов зависимостей — список dependencies должен быть пустым."""
    result = Conan2ResultParser().parse(nlohmann_json_graph, nlohmann_task)

    assert result is not None
    assert result.dependencies == []


@pytest.mark.business_logic
def test_result_parser_sqlite3_has_tcl_dependency(
    sqlite3_deps_graph: dict[str, Any],
    sqlite3_task: ConanTask,
) -> None:
    """Граф sqlite3 содержит узел зависимости tcl — он появляется в result.dependencies."""
    result = Conan2ResultParser().parse(sqlite3_deps_graph, sqlite3_task)

    assert result is not None
    assert "tcl" in result.dependencies


@pytest.mark.business_logic
def test_result_parser_sqlite3_has_default_options(
    sqlite3_deps_graph: dict[str, Any],
    sqlite3_task: ConanTask,
) -> None:
    """sqlite3 имеет несколько default_options, включая 'shared' — список должен быть непустым."""
    result = Conan2ResultParser().parse(sqlite3_deps_graph, sqlite3_task)

    assert result is not None
    assert len(result.default_options) > 0
    names = [opt.name for opt in result.default_options]
    assert "shared" in names


@pytest.mark.business_logic
def test_result_parser_sqlite3_dependency_nodes_not_matched(
    sqlite3_deps_graph: dict[str, Any],
    sqlite3_task: ConanTask,
) -> None:
    """parse() находит целевой узел по имени компонента ('sqlite3'), поэтому package_id
    в результате соответствует узлу '1' (sqlite3), а не узлу '2' (tcl), несмотря на то,
    что оба присутствуют в графе."""
    result = Conan2ResultParser().parse(sqlite3_deps_graph, sqlite3_task)

    assert result is not None
    assert result.package_id == "8c7b3c7905519eea8fda5ff9dde7fbefec90da76"


@pytest.mark.business_logic
def test_result_parser_libnetfilter_queue_two_deps(
    libnetfilter_queue_graph: dict[str, Any],
    libnetfilter_queue_task: ConanTask,
) -> None:
    """Граф libnetfilter_queue содержит узлы libmnl и libnfnetlink — оба появляются в dependencies."""
    result = Conan2ResultParser().parse(libnetfilter_queue_graph, libnetfilter_queue_task)

    assert result is not None
    assert "libmnl" in result.dependencies
    assert "libnfnetlink" in result.dependencies


@pytest.mark.business_logic
def test_result_parser_returns_none_when_node_not_found(
    success_json: dict[str, Any],
    conan_task: ConanTask,
) -> None:
    """parse() возвращает None, когда ни один узел не совпадает с заданным comp_name."""
    object.__setattr__(conan_task, "comp_name", "nonexistent")
    result = Conan2ResultParser().parse(success_json, conan_task)

    assert result is None


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "graph_fixture, task_fixture, comp_name_override",
    [
        # binary='Missing' на целевом узле графа (poco)
        pytest.param("poco_missing_graph", "poco_task", None, id="poco"),
        # binary='Missing' на целевом узле графа (libyang)
        pytest.param("missing_json", "conan_task", "libyang", id="libyang"),
    ],
)
def test_result_parser_returns_none_on_missing_binary(
    request: pytest.FixtureRequest,
    graph_fixture: str,
    task_fixture: str,
    comp_name_override: str | None,
) -> None:
    """parse() возвращает None, когда целевой узел графа имеет binary='Missing'."""
    graph = request.getfixturevalue(graph_fixture)
    task = request.getfixturevalue(task_fixture)
    if comp_name_override is not None:
        object.__setattr__(task, "comp_name", comp_name_override)

    result = Conan2ResultParser().parse(graph, task)

    assert result is None


@pytest.mark.business_logic
def test_result_parser_malformed_target_ref_returns_empty_base_ref(
    conan_task: ConanTask,
) -> None:
    """parse() перехватывает ConanException при разборе кривого поля 'ref' целевого узла
    (RecipeReference.loads не распознаёт формат) и возвращает base_ref='', не падая."""
    minimal_json: dict[str, Any] = {
        "graph": {
            "nodes": {
                "0": {"ref": "conanfile", "name": None, "binary": None},
                "1": {
                    "ref": "name@only",  # заведомо некорректный формат ref
                    "name": "patchelf",
                    "binary": "Download",
                    "package_id": "abc123",
                    "rrev": "",
                    "info": {},
                },
            }
        }
    }
    result = Conan2ResultParser().parse(minimal_json, conan_task)

    assert result is not None
    assert result.base_ref == ""


@pytest.mark.business_logic
def test_result_parser_malformed_dependency_ref_is_skipped(
    conan_task: ConanTask,
) -> None:
    """_extract_dependencies перехватывает ConanException для кривого 'ref' узла-зависимости
    и пропускает эту зависимость, не прерывая сбор остальных."""
    minimal_json: dict[str, Any] = {
        "graph": {
            "nodes": {
                "0": {"ref": "conanfile", "name": None, "binary": None},
                "1": {
                    "ref": "patchelf/0.18.0@platform-2.0/tech",
                    "name": "patchelf",
                    "binary": "Download",
                    "package_id": "abc123",
                    "rrev": "r1",
                    "info": {},
                },
                "2": {
                    "ref": "name@only",  # кривой ref зависимости — должен быть пропущен
                    "name": "broken-dep",
                    "binary": "Download",
                },
                "3": {
                    "ref": "goodlib/1.0@platform-2.0/tech",
                    "name": "goodlib",
                    "binary": "Download",
                },
            }
        }
    }
    result = Conan2ResultParser().parse(minimal_json, conan_task)

    assert result is not None
    assert "goodlib" in result.dependencies
    assert "broken-dep" not in result.dependencies


@pytest.mark.business_logic
def test_result_parser_skips_root_node(conan_task: ConanTask) -> None:
    """Узел '0' с name=null никогда не сопоставляется, даже если он единственный."""
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
    result = Conan2ResultParser().parse(minimal_json, conan_task)

    assert result is None


@pytest.mark.business_logic
def test_result_parser_handles_null_default_options(conan_task: ConanTask) -> None:
    """Узел с default_options=null должен возвращать пустой список для default_options."""
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
    result = Conan2ResultParser().parse(minimal_json, conan_task)

    assert result is not None
    assert result.default_options == []


@pytest.mark.business_logic
def test_result_parser_patchelf_016_version_uses_same_channel(
    success_json: dict[str, Any],
) -> None:
    """ConanResultParser обрабатывает patchelf 0.16.1/tech так же, как 0.18.0/tech.

    Повторно использует graph_info_success.json (содержащий узел patchelf), но с задачей
    с версией '0.16.1'. Парсер сопоставляет по имени, а не по версии, поэтому
    тот же узел графа находится и успешно парсится.
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
    result = Conan2ResultParser().parse(success_json, task_016)
    assert result is not None
    assert result.base_ref.startswith("patchelf/")
    assert result.conan_settings.get("os.distro") == "alpine"


@pytest.mark.business_logic
def test_result_parser_sqlite3_fast_base_ref_format(
    sqlite3_deps_graph: dict[str, Any],
    sqlite3_task: ConanTask,
) -> None:
    """base_ref для sqlite3 fast имеет формат 'sqlite3/<version>@platform-2.0/fast' без хэша rrev."""
    result = Conan2ResultParser().parse(sqlite3_deps_graph, sqlite3_task)
    assert result is not None
    assert result.base_ref.startswith("sqlite3/")
    assert "@platform-2.0/fast" in result.base_ref
    assert "#" not in result.base_ref


@pytest.fixture
def apr_task() -> ConanTask:
    """Минимальный ConanTask для apr/1.7.6 (канал fast, без зависимостей)."""
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
    """Содержимое graph_info_apr.json (apr 1.7.6, канал fast, без зависимостей)."""
    return json.loads((resources_dir / "conan" / "graph_info_apr.json").read_text())


@pytest.mark.business_logic
def test_result_parser_apr_no_dependencies(
    apr_graph: dict[str, Any],
    apr_task: ConanTask,
) -> None:
    """apr не имеет узлов зависимостей — список dependencies должен быть пустым."""
    result = Conan2ResultParser().parse(apr_graph, apr_task)
    assert result is not None
    assert result.dependencies == []


@pytest.mark.business_logic
def test_result_parser_apr_fast_channel_in_base_ref(
    apr_graph: dict[str, Any],
    apr_task: ConanTask,
) -> None:
    """base_ref для apr должен содержать '@platform-2.0/fast' (канал fast, не slow или tech)."""
    result = Conan2ResultParser().parse(apr_graph, apr_task)
    assert result is not None
    assert "@platform-2.0/fast" in result.base_ref


@pytest.mark.business_logic
def test_result_parser_apr_has_default_options(
    apr_graph: dict[str, Any],
    apr_task: ConanTask,
) -> None:
    """Узел apr содержит default_options (shared, fPIC, …) — список должен быть непустым."""
    result = Conan2ResultParser().parse(apr_graph, apr_task)
    assert result is not None
    assert len(result.default_options) > 0
    names = [opt.name for opt in result.default_options]
    assert "shared" in names


@pytest.mark.business_logic
def test_result_parser_libnetfilter_queue_deps_are_plain_names(
    libnetfilter_queue_graph: dict[str, Any],
    libnetfilter_queue_task: ConanTask,
) -> None:
    """Записи в result.dependencies — это чистые имена компонентов (без версии или @)."""
    result = Conan2ResultParser().parse(libnetfilter_queue_graph, libnetfilter_queue_task)
    assert result is not None
    for dep in result.dependencies:
        assert "/" not in dep, f"dependency '{dep}' should be a bare name, not a reference"
        assert "@" not in dep, f"dependency '{dep}' contains a conan reference part"


@pytest.fixture
def stunnel_error_graph(resources_dir: Path) -> dict[str, Any]:
    """Содержимое graph_info_stunnel_error.json (version range не удалось разрешить)."""
    return json.loads((resources_dir / "conan" / "graph_info_stunnel_error.json").read_text())


@pytest.fixture
def stunnel_task() -> ConanTask:
    """Минимальный ConanTask для stunnel/5.77, у которого разрешение version range завершается ошибкой."""
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
    """parse() возвращает None без исключений, когда version range не разрешился и узла компонента нет в графе."""
    result = Conan2ResultParser().parse(stunnel_error_graph, stunnel_task)
    assert result is None


@pytest.fixture
def patch_files_graph(resources_dir: Path) -> dict[str, Any]:
    """Содержимое graph_info_patch_files.json (patchelf с несколькими патчами в conandata)."""
    return json.loads((resources_dir / "conan" / "graph_info_patch_files.json").read_text())


@pytest.mark.business_logic
def test_result_parser_extracts_patch_file_names(
    patch_files_graph: dict[str, Any], conan_task: ConanTask
) -> None:
    """_extract_patches собирает уникальные имена патч-файлов из всех ключей conandata.patches."""
    result = Conan2ResultParser().parse(patch_files_graph, conan_task)

    assert result is not None
    assert result.patches == ["0001-fix.patch", "0002-extra.patch"]


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "conandata",
    [
        # patches — не словарь (например список) -> возвращается пустой список патчей
        pytest.param({"patches": ["not-a-dict"]}, id="patches-not-a-dict"),
        # значение под ключом версии — не список (например строка) -> элемент пропускается
        pytest.param({"patches": {"0.18.0": "not-a-list"}}, id="patch-entry-not-a-list"),
    ],
)
def test_result_parser_extract_patches_guards_against_malformed_conandata(
    conan_task: ConanTask, conandata: dict[str, Any]
) -> None:
    """_extract_patches возвращает пустой список патчей при неожиданной форме
    conandata.patches (не dict/не list там, где Conan обычно кладёт словарь/списки),
    не поднимая AttributeError/TypeError на кривых данных из реального ответа."""
    graph_json: dict[str, Any] = {
        "graph": {
            "nodes": {
                "1": {
                    "name": "patchelf",
                    "binary": "Download",
                    "ref": "patchelf/0.18.0@platform-2.0/tech#abc123",
                    "rrev": "abc123",
                    "package_id": "deadbeef",
                    "info": {"settings": {"os": "Linux"}, "options": {}},
                    "conandata": conandata,
                },
            }
        }
    }
    result = Conan2ResultParser().parse(graph_json, conan_task)

    assert result is not None
    assert result.patches == []


@pytest.mark.business_logic
def test_result_parser_build_url_empty_when_artifactory_base_url_missing(
    success_json: dict[str, Any],
) -> None:
    """parse() возвращает пустой build_url, если artifactory_base_url задачи пуст."""
    release = Release(version="0.18.0", platform="2.0", channel="tech")
    pb = ProfileBuild(profile_name="crypto_alpine_gcc_x86_64.jinja")
    task = ConanTask(
        cmd=["conan", "graph", "info"],
        comp_name="patchelf",
        version="0.18.0",
        channel="tech",
        profile_name="crypto_alpine_gcc_x86_64.jinja",
        option_id="1",
        option_str="",
        target_platform="2.0",
        artifactory_base_url="",
        release=release,
        pb=pb,
    )
    result = Conan2ResultParser().parse(success_json, task)

    assert result is not None
    assert result.build_url == ""


@pytest.mark.business_logic
def test_result_parser_build_url_empty_when_rrev_missing(conan_task: ConanTask) -> None:
    """parse() возвращает пустой build_url, если у целевого узла нет rrev."""
    graph_json: dict[str, Any] = {
        "graph": {
            "nodes": {
                "1": {
                    "name": "patchelf",
                    "binary": "Download",
                    "ref": "patchelf/0.18.0@platform-2.0/tech",  # без "#rrev"
                    "rrev": "",
                    "package_id": "deadbeef",
                    "info": {"settings": {}, "options": {}},
                },
            }
        }
    }
    result = Conan2ResultParser().parse(graph_json, conan_task)

    assert result is not None
    assert result.build_url == ""


@pytest.mark.business_logic
def test_result_parser_build_date_empty_on_malformed_timestamp(conan_task: ConanTask) -> None:
    """parse() возвращает пустой build_date при нечисловом prev_timestamp вместо исключения."""
    graph_json: dict[str, Any] = {
        "graph": {
            "nodes": {
                "1": {
                    "name": "patchelf",
                    "binary": "Download",
                    "ref": "patchelf/0.18.0@platform-2.0/tech#abc123",
                    "rrev": "abc123",
                    "package_id": "deadbeef",
                    "info": {"settings": {}, "options": {}},
                    "prev_timestamp": "not-a-number",
                },
            }
        }
    }
    result = Conan2ResultParser().parse(graph_json, conan_task)

    assert result is not None
    assert result.build_date == ""
