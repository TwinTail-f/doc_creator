"""
Юнит-тесты для autodoc/parser/conan/conan2_result_parser.py.

Охватывает Conan2ResultParser.parse() — успешный путь (patchelf, nlohmann_json,
sqlite3, libnetfilter_queue), бинарник Missing (poco), отсутствующий узел,
пропуск корневого узла и извлечение полей.
JSON-фикстуры загружаются через константу RESOURCES_DIR (tests.unit.parser.conftest).
"""

import dataclasses
import json
from typing import Any

import pytest

from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.release import Release
from autodoc.parser.conan.conan2_result_parser import Conan2ResultParser
from autodoc.parser.conan.models.conan_task import ConanTask
from tests.unit.parser.conftest import NULL_PACKAGE_ID, RESOURCES_DIR


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
def success_json() -> dict[str, Any]:
    """Содержимое graph_info_success.json (patchelf, канал tech)."""
    return json.loads((RESOURCES_DIR / "conan" / "graph_info_success.json").read_text())


@pytest.fixture
def missing_json() -> dict[str, Any]:
    """Содержимое graph_info_missing.json (libyang с binary=Missing)."""
    return json.loads((RESOURCES_DIR / "conan" / "graph_info_missing.json").read_text())


@pytest.fixture
def nlohmann_json_graph() -> dict[str, Any]:
    """Содержимое graph_info_nlohmann_json.json (header-only, NULL_PACKAGE_ID)."""
    return json.loads((RESOURCES_DIR / "conan" / "graph_info_nlohmann_json.json").read_text())


@pytest.fixture
def sqlite3_deps_graph() -> dict[str, Any]:
    """Содержимое graph_info_sqlite3_with_deps.json (sqlite3 с зависимостью tcl)."""
    return json.loads((RESOURCES_DIR / "conan" / "graph_info_sqlite3_with_deps.json").read_text())


@pytest.fixture
def libnetfilter_queue_graph() -> dict[str, Any]:
    """Содержимое graph_info_libnetfilter_queue.json (зависимости libmnl + libnfnetlink)."""
    return json.loads((RESOURCES_DIR / "conan" / "graph_info_libnetfilter_queue.json").read_text())


@pytest.fixture
def poco_missing_graph() -> dict[str, Any]:
    """Содержимое graph_info_poco_missing.json (poco с binary=Missing)."""
    return json.loads((RESOURCES_DIR / "conan" / "graph_info_poco_missing.json").read_text())


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
    """
    parse() для разных компонентов (patchelf, libnetfilter_queue, apr)
    возвращает ConanEnrichData с ожидаемым package_id."""
    graph = request.getfixturevalue(graph_fixture)
    task = request.getfixturevalue(task_fixture)
    result = Conan2ResultParser().parse(graph, task)

    assert result is not None
    assert result.package_id == expected_package_id


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
@pytest.mark.parametrize(
    "graph_fixture, task_fixture",
    [
        pytest.param("success_json", "conan_task", id="patchelf-missing-key"),
        pytest.param("nlohmann_json_graph", "nlohmann_task", id="nlohmann-json-empty-dict"),
    ],
)
def test_result_parser_no_default_options(
    request: pytest.FixtureRequest, graph_fixture: str, task_fixture: str
) -> None:
    """
    default_options возвращается пустым списком и когда ключ default_options
    отсутствует в JSON (patchelf), и когда он присутствует, но пуст (nlohmann_json)."""
    graph = request.getfixturevalue(graph_fixture)
    task = request.getfixturevalue(task_fixture)
    result = Conan2ResultParser().parse(graph, task)

    assert result is not None
    assert result.default_options == []


@pytest.mark.business_logic
def test_result_parser_nlohmann_json_null_package_id(
    nlohmann_json_graph: dict[str, Any],
    nlohmann_task: ConanTask,
) -> None:
    """
    nlohmann_json возвращает SHA1 NULL_PACKAGE_ID, характерный для header-only библиотек.

    NULL_PACKAGE_ID — это SHA1 пустой строки; Conan использует его как package_id
    для header-only компонентов, у которых нет бинарного пакета для конкретного профиля.
    """
    result = Conan2ResultParser().parse(nlohmann_json_graph, nlohmann_task)

    assert result is not None
    assert result.package_id == NULL_PACKAGE_ID


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "graph_fixture, task_fixture",
    [
        pytest.param("nlohmann_json_graph", "nlohmann_task", id="nlohmann_json"),
        pytest.param("apr_graph", "apr_task", id="apr"),
    ],
)
def test_result_parser_no_dependencies(
    request: pytest.FixtureRequest, graph_fixture: str, task_fixture: str
) -> None:
    """nlohmann_json и apr не имеют узлов зависимостей — dependencies должен быть пустым списком."""
    graph = request.getfixturevalue(graph_fixture)
    task = request.getfixturevalue(task_fixture)
    result = Conan2ResultParser().parse(graph, task)

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
@pytest.mark.parametrize(
    "graph_fixture, task_fixture",
    [
        pytest.param("sqlite3_deps_graph", "sqlite3_task", id="sqlite3"),
        pytest.param("apr_graph", "apr_task", id="apr"),
    ],
)
def test_result_parser_has_default_options(
    request: pytest.FixtureRequest, graph_fixture: str, task_fixture: str
) -> None:
    """sqlite3 и apr оба имеют default_options, включая 'shared' — список должен быть непустым."""
    graph = request.getfixturevalue(graph_fixture)
    task = request.getfixturevalue(task_fixture)
    result = Conan2ResultParser().parse(graph, task)

    assert result is not None
    assert len(result.default_options) > 0
    names = [opt.name for opt in result.default_options]
    assert "shared" in names


@pytest.mark.business_logic
def test_result_parser_sqlite3_dependency_nodes_not_matched(
    sqlite3_deps_graph: dict[str, Any],
    sqlite3_task: ConanTask,
) -> None:
    """
    parse() находит целевой узел по имени компонента ('sqlite3'), поэтому package_id
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
    conan_task = dataclasses.replace(conan_task, comp_name="nonexistent")
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
        task = dataclasses.replace(task, comp_name=comp_name_override)

    result = Conan2ResultParser().parse(graph, task)

    assert result is None


@pytest.mark.business_logic
def test_result_parser_malformed_target_ref_returns_empty_base_ref(
    conan_task: ConanTask,
) -> None:
    """
    parse() перехватывает ConanException при разборе кривого поля 'ref' целевого узла
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
def test_result_parser_missing_ref_returns_empty_base_ref(
    conan_task: ConanTask,
) -> None:
    """
    parse() возвращает base_ref='', если у узла нет поля 'ref' вовсе
    (ранний выход до RecipeReference.loads, отдельно от кейса с кривым ref)."""
    minimal_json: dict[str, Any] = {
        "graph": {
            "nodes": {
                "0": {"ref": "conanfile", "name": None, "binary": None},
                "1": {
                    "name": "patchelf",
                    "binary": "Download",
                    "package_id": "abc123",
                    "rrev": "existing-rrev",
                    "info": {},
                    # поле "ref" намеренно отсутствует
                },
            }
        }
    }
    result = Conan2ResultParser().parse(minimal_json, conan_task)

    assert result is not None
    assert result.base_ref == ""
    assert result.rrev == "existing-rrev"
    assert result.full_version == conan_task.version


@pytest.mark.business_logic
def test_result_parser_short_ref_without_user_uses_ref_revision(
    conan_task: ConanTask,
) -> None:
    """
    Короткий ref без @user/channel ('name/version#rrev'): rrev берётся из
    ref, если node['rrev'] пуст, а full_version НЕ переопределяется —
    переопределение версии срабатывает только когда у ref есть user."""
    minimal_json: dict[str, Any] = {
        "graph": {
            "nodes": {
                "0": {"ref": "conanfile", "name": None, "binary": None},
                "1": {
                    "name": "patchelf",
                    "binary": "Download",
                    "ref": "patchelf/9.9.9#deadbeef",  # без @user/channel
                    "rrev": "",
                    "package_id": "abc123",
                    "info": {},
                },
            }
        }
    }
    result = Conan2ResultParser().parse(minimal_json, conan_task)

    assert result is not None
    assert result.rrev == "deadbeef"
    assert result.full_version == conan_task.version  # не "9.9.9"


@pytest.mark.business_logic
def test_result_parser_malformed_dependency_ref_is_skipped(
    conan_task: ConanTask,
) -> None:
    """
    _extract_dependencies перехватывает ConanException для кривого 'ref' узла-зависимости
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
                "4": {
                    # поле "ref" отсутствует вовсе — должен быть пропущен
                    "name": "no-ref-dep",
                    "binary": "Download",
                },
                "5": {
                    # name узла отличается от comp_name (иначе отсеялся бы
                    # раньше, до парсинга ref), но ref реально указывает на
                    # тот же компонент, что и цель — не должен попасть в deps
                    "ref": "patchelf/2.0@platform-2.0/tech",
                    "name": "patchelf-alias-node",
                    "binary": "Download",
                },
            }
        }
    }
    result = Conan2ResultParser().parse(minimal_json, conan_task)

    assert result is not None
    assert result.dependencies == ["goodlib"]
    assert "no-ref-dep" not in result.dependencies
    assert "patchelf-alias-node" not in result.dependencies


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
    """
    ConanResultParser обрабатывает patchelf 0.16.1/tech так же, как 0.18.0/tech.

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
def apr_graph() -> dict[str, Any]:
    """Содержимое graph_info_apr.json (apr 1.7.6, канал fast, без зависимостей)."""
    return json.loads((RESOURCES_DIR / "conan" / "graph_info_apr.json").read_text())


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "graph_fixture, task_fixture, expected_prefix, expected_channel_part",
    [
        pytest.param(
            "success_json", "conan_task", "patchelf/", "@platform-2.0/tech", id="patchelf-tech"
        ),
        pytest.param(
            "sqlite3_deps_graph",
            "sqlite3_task",
            "sqlite3/",
            "@platform-2.0/fast",
            id="sqlite3-fast",
        ),
        pytest.param("apr_graph", "apr_task", "apr/", "@platform-2.0/fast", id="apr-fast"),
    ],
)
def test_result_parser_base_ref_format(
    request: pytest.FixtureRequest,
    graph_fixture: str,
    task_fixture: str,
    expected_prefix: str,
    expected_channel_part: str,
) -> None:
    """
    base_ref начинается с '<comp_name>/', содержит канал вида '@platform-2.0/<channel>' и
    никогда не содержит символ '#' (хэш ревизии) — единый строгий набор ассертов для
    patchelf (tech), sqlite3 (fast) и apr (fast)."""
    graph = request.getfixturevalue(graph_fixture)
    task = request.getfixturevalue(task_fixture)
    result = Conan2ResultParser().parse(graph, task)

    assert result is not None
    assert result.base_ref.startswith(expected_prefix)
    assert expected_channel_part in result.base_ref
    assert "#" not in result.base_ref


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
def stunnel_error_graph() -> dict[str, Any]:
    """Содержимое graph_info_stunnel_error.json (version range не удалось разрешить)."""
    return json.loads((RESOURCES_DIR / "conan" / "graph_info_stunnel_error.json").read_text())


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
def patch_files_graph() -> dict[str, Any]:
    """Содержимое graph_info_patch_files.json (patchelf с несколькими патчами в conandata)."""
    return json.loads((RESOURCES_DIR / "conan" / "graph_info_patch_files.json").read_text())


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
    "conandata, expected_patches",
    [
        # patches — не словарь (например список) -> возвращается пустой список патчей
        pytest.param({"patches": ["not-a-dict"]}, [], id="patches-not-a-dict"),
        # значение под ключом версии — не список (например строка) -> элемент пропускается
        pytest.param({"patches": {"0.18.0": "not-a-list"}}, [], id="patch-entry-not-a-list"),
        # элемент списка — не словарь -> пропускается, валидные элементы остаются
        pytest.param(
            {"patches": {"0.18.0": ["not-a-dict", {"patch_file": "keep.patch"}]}},
            ["keep.patch"],
            id="list-item-not-a-dict",
        ),
        # отсутствующий или пустой patch_file -> пропускается, валидные элементы остаются
        pytest.param(
            {
                "patches": {
                    "0.18.0": [
                        {"other_field": "x"},
                        {"patch_file": ""},
                        {"patch_file": "real.patch"},
                    ]
                }
            },
            ["real.patch"],
            id="missing-or-empty-patch-file",
        ),
    ],
)
def test_result_parser_extract_patches_guards_against_malformed_conandata(
    conan_task: ConanTask, conandata: dict[str, Any], expected_patches: list[str]
) -> None:
    """
    _extract_patches возвращает только валидные patch_file при неожиданной форме
    conandata.patches: не-dict/не-list контейнеры, не-dict элементы списка,
    отсутствующий/пустой patch_file — без AttributeError/TypeError."""
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
    assert result.patches == expected_patches


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
def test_build_artifactory_url_without_package_id_suffix(
    conan_task: ConanTask,
) -> None:
    """
    _build_artifactory_url не добавляет суффикс '/package/<id>' без package_id.
    Метод вызывается напрямую: через parse() эта ветка недостижима, т.к. вызов
    там уже обёрнут условием 'if package_id'."""
    url = Conan2ResultParser()._build_artifactory_url(
        conan_task, full_version="0.18.0", rrev="abc123", package_id=""
    )

    assert url == "https://art.example.com/platform-2.0/patchelf/0.18.0/tech/abc123"
    assert "/package/" not in url


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
