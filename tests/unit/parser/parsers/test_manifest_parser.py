"""Юнит-тесты для autodoc.parser.parsers.manifest_parser.ManifestParser."""

from pathlib import Path

import pytest

import autodoc.parser.parsers.manifest_parser as manifest_parser_module
from autodoc.parser.parsers.manifest_parser import ManifestParser

TARGET_PLATFORM: str = "2.0"

_MANIFEST_WITHOUT_NAME = "description= test\n"

_MANIFEST_PLATFORM_MISMATCH = (
    "name= libfoo\n"
    "versions.component= 1.0\n"
    "versions.platform= 1.0-tech\n"
    "profiles-1.0-1.0-tech= hw-linux-x86_64-gcc10_2\n"
)

_MANIFEST_NO_PROFILES_KEY = (
    "name= libfoo\n" "versions.component= 1.0\n" "versions.platform= 2.0-tech\n"
)


@pytest.fixture
def all_real_properties(real_manifests_dir: Path) -> list[Path]:
    """Отсортированный список всех реальных файлов .properties в resources/manifests/."""
    return sorted(real_manifests_dir.glob("*.properties"))


@pytest.fixture
def parser_20() -> ManifestParser:
    """ManifestParser настроенный для платформы 2.0 с поддельным URL коллекции TFS."""
    return ManifestParser(
        target_platform=TARGET_PLATFORM,
        tfs_collection_url="https://tfs.example.com",
    )


@pytest.mark.business_logic
def test_parser_returns_correct_component_count(
    parser_20: ManifestParser,
    all_real_properties: list[Path],
) -> None:
    """
    parse() со всеми реальными файлами возвращает по одному компоненту на каждый
    файл resources/manifests/ (у каждого есть релиз для платформы 2.0)."""
    components, _ = parser_20.parse(all_real_properties, component_names=[], filter_mode="exclude")
    assert len(components) == len(all_real_properties)
    assert {c.name for c in components} == {
        "apr",
        "libnetfilter_queue",
        "nlohmann_json",
        "nlohmann_json_fast_only",
        "openssl",
        "patchelf",
        "sqlite3",
    }


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "manifest_filename, expected_pairs",
    [
        # patchelf — 2 релиза в одном канале tech
        pytest.param(
            "patchelf.properties", {("0.16.1", "tech"), ("0.18.0", "tech")}, id="patchelf"
        ),
        # apr — 1 релиз, канал fast
        pytest.param("apr.properties", {("1.7.6", "fast")}, id="apr"),
        # sqlite3 — 2 релиза, разные каналы fast/slow
        pytest.param("sqlite3.properties", {("3.51.2", "fast"), ("3.34.1", "slow")}, id="sqlite3"),
        # libnetfilter_queue — 1 релиз для платформы 2.0, канал slow
        pytest.param("libnetfilter_queue.properties", {("1.0.5", "slow")}, id="libnetfilter_queue"),
        # nlohmann_json — 2 релиза, разные каналы slow/fast
        pytest.param(
            "nlohmann_json.properties", {("3.9.1", "slow"), ("3.12.0", "fast")}, id="nlohmann_json"
        ),
        # openssl — 1 релиз, канал tech
        pytest.param("openssl.properties", {("3.0.9", "tech")}, id="openssl"),
    ],
)
def test_parser_release_version_channel_pairs(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
    manifest_filename: str,
    expected_pairs: set[tuple[str, str]],
) -> None:
    """
    Для каждого реального манифеста parse() возвращает ожидаемый набор
    пар (version, channel) среди releases компонента."""
    components, _ = parser_20.parse(
        [real_manifests_dir / manifest_filename],
        component_names=[],
        filter_mode="exclude",
    )
    assert len(components) == 1
    pairs = {(r.version, r.channel) for r in components[0].releases}
    assert pairs == expected_pairs


@pytest.mark.business_logic
def test_parser_sqlite3_many_profiles(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """релиз sqlite3 3.51.2/fast имеет по крайней мере 10 profile_builds."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "sqlite3.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    assert len(components) == 1
    fast_release = next(
        (r for r in components[0].releases if r.version == "3.51.2" and r.channel == "fast"),
        None,
    )
    assert fast_release is not None
    assert len(fast_release.profile_builds) >= 10


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "manifest_filename",
    [
        # компонент с плоским списком версий/каналов
        pytest.param("apr.properties", id="apr"),
        # компонент с несколькими релизами и каналами (slow/fast)
        pytest.param("nlohmann_json.properties", id="nlohmann_json"),
    ],
)
def test_parser_profile_builds_populated_as_skeletons(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
    manifest_filename: str,
) -> None:
    """Каждый ProfileBuild из парсинга имеет exists=False и variants==[] (простые скелеты)."""
    components, _ = parser_20.parse(
        [real_manifests_dir / manifest_filename],
        component_names=[],
        filter_mode="exclude",
    )
    for comp in components:
        for rel in comp.releases:
            for pb in rel.profile_builds:
                assert pb.exists is False
                assert pb.variants == []


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "filter_mode, expected_names",
    [
        # include с component_names=['apr'] -> в результате остаётся только apr
        pytest.param("include", {"apr"}, id="include-only-apr"),
        # exclude с component_names=['apr'] -> apr опускается, остаются остальные 6 компонентов
        pytest.param(
            "exclude",
            {
                "libnetfilter_queue",
                "nlohmann_json",
                "nlohmann_json_fast_only",
                "openssl",
                "patchelf",
                "sqlite3",
            },
            id="exclude-all-but-apr",
        ),
    ],
)
def test_parser_filter_mode_include_exclude(
    parser_20: ManifestParser,
    all_real_properties: list[Path],
    filter_mode: str,
    expected_names: set[str],
) -> None:
    """
    parse() с component_names=['apr'] возвращает только apr при filter_mode='include'
    и все компоненты, кроме apr, при filter_mode='exclude'."""
    components, _ = parser_20.parse(
        all_real_properties, component_names=["apr"], filter_mode=filter_mode
    )
    assert {c.name for c in components} == expected_names


@pytest.mark.business_logic
def test_parser_file_without_recognizable_properties_is_silently_skipped(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
    tmp_path: Path,
) -> None:
    """
    Файл без пары ключ-значение (нет поля 'name') не создаёт компонент и не
    добавляет предупреждение; корректные файлы рядом обрабатываются как обычно."""
    bad_file = _write_manifest(tmp_path, "garbage", "not valid properties!!!")
    good_file = real_manifests_dir / "apr.properties"
    components, warnings = parser_20.parse(
        [good_file, bad_file], component_names=[], filter_mode="exclude"
    )
    names = [c.name for c in components]
    assert "apr" in names
    assert len(components) == 1
    assert warnings == []


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "content, expected_warnings_count",
    [
        # без поля name файл целиком пропускается, молча
        pytest.param(_MANIFEST_WITHOUT_NAME, 0, id="missing-name"),
        # файл манифеста не найден на диске
        pytest.param(None, 1, id="missing-file"),
        # platform в манифесте не совпадает с platform парсера -> релиз не создаётся
        pytest.param(_MANIFEST_PLATFORM_MISMATCH, 0, id="platform-mismatch"),
        # ключ profiles отсутствует -> пара версия/канал пропускается
        pytest.param(_MANIFEST_NO_PROFILES_KEY, 0, id="missing-profiles-key"),
    ],
)
def test_manifest_parser_invalid_input_yields_no_components(
    tmp_path: Path,
    content: str | None,
    expected_warnings_count: int,
) -> None:
    """
    При некорректном, неполном или отсутствующем манифесте parse() не
    создаёт компонент; причина неполноты варьируется по кейсам."""
    if content is None:
        path = tmp_path / "nonexistent.properties"
    else:
        path = _write_manifest(tmp_path, "libfoo", content)
    components, warnings = ManifestParser(TARGET_PLATFORM).parse(
        [path], component_names=[], filter_mode="exclude"
    )
    assert len(components) == 0
    assert len(warnings) == expected_warnings_count


@pytest.mark.business_logic
def test_parser_nlohmann_json_fast_release_has_one_profile(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """релиз nlohmann_json 3.12.0/fast имеет ровно 1 profile_build (mobile-windows-x86_64)."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "nlohmann_json.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    fast_release = next(
        (r for r in components[0].releases if r.version == "3.12.0" and r.channel == "fast"),
        None,
    )
    assert fast_release is not None
    assert len(fast_release.profile_builds) == 1
    assert fast_release.profile_builds[0].profile_name == "mobile-windows-x86_64.jinja"


@pytest.mark.business_logic
def test_parser_apr_profile_count_fast(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """
    apr 1.7.6/fast имеет ровно 4 profile_builds
    (crypto_default_gcc_x86_64, hw-linux-x86_64-gcc10_2,
     windows-x86_64-vs2022-mt, windows-x86-vs2022-mt)."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "apr.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    rel = components[0].releases[0]
    profile_names = {pb.profile_name for pb in rel.profile_builds}
    assert profile_names == {
        "crypto_default_gcc_x86_64.jinja",
        "hw-linux-x86_64-gcc10_2",
        "windows-x86_64-vs2022-mt",
        "windows-x86-vs2022-mt",
    }


@pytest.mark.business_logic
def test_parser_patchelf_both_versions_have_same_profiles(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """Оба релиза patchelf имеют одинаковый набор имён профилей (по 6 профилей)."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "patchelf.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    releases = components[0].releases
    profile_sets = [frozenset(pb.profile_name for pb in rel.profile_builds) for rel in releases]
    assert profile_sets[0] == profile_sets[1]
    assert len(profile_sets[0]) == 6


@pytest.mark.business_logic
def test_parser_sqlite3_slow_release_version_and_profiles(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """Релиз sqlite3 slow имеет версию 3.34.1 и ровно 4 profile_builds."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "sqlite3.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    slow_rel = next(r for r in components[0].releases if r.channel == "slow")
    assert slow_rel.version == "3.34.1"
    profile_names = {pb.profile_name for pb in slow_rel.profile_builds}
    assert profile_names == {
        "hw-linux-armv7-gcc10_2",
        "hw-linux-armv8-gcc10_2",
        "hw-linux-x86_64-gcc10_2",
        "linux-x86_64-gcc10_2-instrumented",
    }


@pytest.mark.business_logic
def test_parser_sqlite3_fast_and_slow_different_versions(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """Релизы sqlite3 fast и slow имеют разные версии компонента."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "sqlite3.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    versions = {r.version for r in components[0].releases}
    assert len(versions) == 2


@pytest.mark.business_logic
def test_parser_libnetfilter_queue_git_project_and_url_point_to_prg_quant(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """
    компонент libnetfilter_queue имеет git_project=='PRG_Quant' (нестандартный
    проект) и содержит 'PRG_Quant' в сформированном git_url."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "libnetfilter_queue.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    assert len(components) == 1
    assert components[0].git_project == "PRG_Quant"
    assert "PRG_Quant" in components[0].git_url


@pytest.mark.business_logic
def test_parser_libnetfilter_queue_slow_has_expected_profiles(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """libnetfilter_queue 1.0.5/slow имеет ровно 4 profile_builds."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "libnetfilter_queue.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    pb_names = {pb.profile_name for pb in components[0].releases[0].profile_builds}
    assert pb_names == {
        "hw-linux-armv7-gcc10_2",
        "hw-linux-armv8-gcc10_2",
        "hw-linux-x86_64-gcc10_2",
        "linux-x86_64-gcc10_2-instrumented",
    }


def _write_manifest(tmp_path: Path, name: str, content: str) -> Path:
    """
    Записывает .properties-файл во временную директорию и возвращает путь к нему.

    Args:
        tmp_path: Временная директория из фикстуры pytest ``tmp_path``.
        name: Базовое имя файла (без расширения).
        content: Текстовое содержимое файла.

    Returns:
        Абсолютный путь к записанному файлу.
    """
    p = tmp_path / f"{name}.properties"
    p.write_text(content, encoding="utf-8")
    return p


def _minimal_manifest(
    comp_name: str = "mylib",
    comp_version: str = "1.0",
    plat_version: str = "2.2-fast",
    profiles: str = "hw-linux-x86_64",
    git_project: str = "MyProject",
    git_repo: str = "mylib",
) -> str:
    """
    Возвращает минимальную синтаксически корректную строку .properties.

    Использует реальные имена полей, понимаемые ManifestParser:
    ``versions.component``, ``versions.platform``, ``profiles-{cv}-{pv}``,
    ``tfs_git_project``, ``git_repo_name``.

    Args:
        comp_name: Имя компонента (поле ``name``).
        comp_version: Строка версии компонента.
        plat_version: Строка версии платформы, например ``"2.2-fast"`` или ``"2.2"``.
        profiles: Имена профилей для релиза, перечисленные через запятую.
        git_project: Имя проекта TFS.
        git_repo: Имя git-репозитория.

    Returns:
        Многострочная строка, пригодная для записи в файл .properties.
    """
    return (
        f"name={comp_name}\n"
        f"description=Test component\n"
        f"tfs_git_project={git_project}\n"
        f"git_repo_name={git_repo}\n"
        f"versions.component={comp_version}\n"
        f"versions.platform={plat_version}\n"
        f"profiles-{comp_version}-{plat_version}={profiles}\n"
    )


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "plat_version, profiles_key_suffix, expected_channel",
    [
        # суффикс "-fast" -> channel="fast"
        pytest.param("2.2-fast", "2.2-fast", "fast", id="suffix-fast"),
        # суффикс "-slow" -> channel="slow"
        pytest.param("2.2-slow", "2.2-slow", "slow", id="suffix-slow"),
        # версия платформы без дефиса -> channel=""
        pytest.param("2.2", "2.2", "", id="no-suffix-empty-channel"),
        # несколько дефисов -> каналом является только последний сегмент
        pytest.param("2.2-extra-slow", "2.2-extra-slow", "slow", id="multi-dash-last-segment"),
    ],
)
def test_channel_extracted_from_platform_version_suffix(
    tmp_path: Path, plat_version: str, profiles_key_suffix: str, expected_channel: str
) -> None:
    """Канал релиза — это последний дефис-разделённый сегмент строки версии платформы, либо '' при его отсутствии."""
    content = (
        "name=mylib\ndescription=Test\ntfs_git_project=P\ngit_repo_name=r\n"
        f"versions.component=1.0\nversions.platform={plat_version}\n"
        f"profiles-1.0-{profiles_key_suffix}=hw-linux-x86_64\n"
    )
    f = _write_manifest(tmp_path, "mylib", content)
    parser = ManifestParser(target_platform="2.2", tfs_collection_url="http://tfs")
    components, _ = parser.parse([f], component_names=[], filter_mode="include")

    assert len(components) == 1
    assert components[0].releases[0].channel == expected_channel


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "filter_mode, expected_names",
    [
        # include с точным именем -> остаётся только 'openssl', 'openssl-extra' не совпадает
        pytest.param("include", {"openssl"}, id="include-exact-match"),
        # exclude с точным именем -> исключается только 'openssl', 'openssl-extra' остаётся
        pytest.param("exclude", {"openssl-extra"}, id="exclude-exact-match"),
    ],
)
def test_filter_mode_exact_match_only(
    tmp_path: Path, filter_mode: str, expected_names: set[str]
) -> None:
    """filter_mode с component_names=['openssl'] точно совпадает по имени, не задевая 'openssl-extra'."""
    for name in ["openssl", "openssl-extra"]:
        content = _minimal_manifest(
            comp_name=name, git_project="P", git_repo=name, plat_version="2.2-fast"
        )
        _write_manifest(tmp_path, name, content)

    parser = ManifestParser(target_platform="2.2")
    files = list(tmp_path.glob("*.properties"))
    components, _ = parser.parse(files, component_names=["openssl"], filter_mode=filter_mode)

    assert {c.name for c in components} == expected_names


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "filter_mode, component_names",
    [
        # include с пустым списком имён -> фильтр не активен, возвращаются все компоненты
        pytest.param("include", ["libA", "libB", "libC"], id="include-empty-list"),
        # exclude с пустым списком имён -> исключать нечего, возвращаются все компоненты
        pytest.param("exclude", ["libA", "libB"], id="exclude-empty-list"),
    ],
)
def test_filter_mode_empty_list_returns_all_components(
    tmp_path: Path, filter_mode: str, component_names: list[str]
) -> None:
    """filter_mode с пустым списком component_names возвращает все компоненты независимо от режима."""
    for name in component_names:
        content = _minimal_manifest(
            comp_name=name, git_project="P", git_repo=name, plat_version="2.2-fast"
        )
        _write_manifest(tmp_path, name, content)

    parser = ManifestParser(target_platform="2.2")
    files = list(tmp_path.glob("*.properties"))
    components, _ = parser.parse(files, component_names=[], filter_mode=filter_mode)

    assert len(components) == len(component_names)


@pytest.mark.business_logic
def test_profile_build_names_match_manifest_profile_list_exactly(
    tmp_path: Path,
) -> None:
    """Проверить, что значения ProfileBuild.profile_name точно равны записям манифеста."""
    content = _minimal_manifest(
        git_project="P", git_repo="r", profiles="hw-linux-x86_64-gcc12_3, hw-win-msvc2022"
    )
    f = _write_manifest(tmp_path, "mylib", content)
    parser = ManifestParser(target_platform="2.2")
    components, _ = parser.parse([f], component_names=[], filter_mode="include")

    names = {pb.profile_name for pb in components[0].releases[0].profile_builds}
    assert names == {"hw-linux-x86_64-gcc12_3", "hw-win-msvc2022"}


@pytest.mark.business_logic
def test_git_url_set_on_component_not_release(tmp_path: Path) -> None:
    """Проверить, что git_url является полем уровня Component, а не Release."""
    content = (
        "name=mylib\ndescription=Test\n"
        "tfs_git_project=MyProject\ngit_repo_name=mylib-repo\n"
        "versions.component=1.0, 2.0\nversions.platform=2.2-fast\n"
        "profiles-1.0-2.2-fast=hw-linux-x86_64\n"
        "profiles-2.0-2.2-fast=hw-linux-x86_64\n"
    )
    f = _write_manifest(tmp_path, "mylib", content)
    parser = ManifestParser(target_platform="2.2", tfs_collection_url="http://tfs/col")
    components, _ = parser.parse([f], component_names=[], filter_mode="include")

    comp = components[0]
    assert hasattr(comp, "git_url"), "git_url должен быть полем Component"
    assert "mylib-repo" in comp.git_url
    assert len(comp.releases) == 2


@pytest.mark.business_logic
def test_git_url_format_is_tfs_git_format(tmp_path: Path) -> None:
    """Проверить, что Component.git_url отформатирован как хорошо сформированный TFS Git URL."""
    content = _minimal_manifest(git_project="PlatformTeam", git_repo="mylib")
    f = _write_manifest(tmp_path, "mylib", content)
    parser = ManifestParser(
        target_platform="2.2",
        tfs_collection_url="http://tfs.example.com/DefaultCollection",
    )
    components, _ = parser.parse([f], component_names=[], filter_mode="include")

    expected_url = "http://tfs.example.com/DefaultCollection/PlatformTeam/_git/mylib"
    assert components[0].git_url == expected_url


@pytest.mark.business_logic
def test_only_target_platform_releases_included(tmp_path: Path) -> None:
    """Проверить, что ManifestParser возвращает только релизы, соответствующие целевой платформе."""
    content = (
        "name=mylib\ndescription=Test\ntfs_git_project=P\ngit_repo_name=r\n"
        "versions.component=1.0, 2.0, 3.0\n"
        "versions.platform=2.1-fast, 2.2-fast, 2.3-fast\n"
        "profiles-1.0-2.1-fast=hw-linux-x86_64\n"
        "profiles-2.0-2.2-fast=hw-linux-x86_64\n"
        "profiles-3.0-2.3-fast=hw-linux-x86_64\n"
    )
    f = _write_manifest(tmp_path, "mylib", content)
    parser = ManifestParser(target_platform="2.2")
    components, _ = parser.parse([f], component_names=[], filter_mode="include")

    assert len(components[0].releases) == 1
    assert components[0].releases[0].version == "2.0"


@pytest.mark.business_logic
def test_manifest_parser_partial_profile_version_matrix(tmp_path: Path) -> None:
    """Разбирается только та комбинация версий компонента/платформы, для которой есть ключ profiles."""
    content = (
        "name=mylib\ndescription=Test\ntfs_git_project=P\ngit_repo_name=r\n"
        "versions.component=1.0, 2.0\n"
        "versions.platform=2.2-fast, 2.2-slow\n"
        "profiles-1.0-2.2-fast=hw-linux-x86_64\n"
        "profiles-2.0-2.2-slow=hw-linux-x86_64\n"
    )
    f = _write_manifest(tmp_path, "mylib", content)
    parser = ManifestParser(target_platform="2.2")
    components, _ = parser.parse([f], component_names=[], filter_mode="include")

    releases = components[0].releases
    assert len(releases) == 2
    pairs = {(r.version, r.channel) for r in releases}
    assert pairs == {("1.0", "fast"), ("2.0", "slow")}


@pytest.mark.infrastructure
def test_manifest_parser_read_properties_oserror_after_is_file_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ManifestParser перехватывает OSError из read_properties и возвращает предупреждение вместо падения."""
    f = _write_manifest(tmp_path, "mylib", _minimal_manifest())

    def _raise_oserror(_path):
        raise OSError("permission denied")

    monkeypatch.setattr(manifest_parser_module, "read_properties", _raise_oserror)

    parser = ManifestParser(target_platform="2.2")
    components, warnings = parser.parse([f], component_names=[], filter_mode="include")

    assert components == []
    assert len(warnings) == 1


@pytest.mark.business_logic
def test_manifest_parser_include_nonmatching_list_returns_empty(tmp_path: Path) -> None:
    """filter_mode='include' с непустым списком, не совпадающим ни с одним именем, не возвращает компонентов."""
    f = _write_manifest(tmp_path, "mylib", _minimal_manifest(comp_name="mylib"))
    parser = ManifestParser(target_platform="2.2")
    components, _ = parser.parse(
        [f], component_names=["completely-different-name"], filter_mode="include"
    )
    assert components == []


@pytest.mark.business_logic
def test_manifest_parser_skips_none_results_from_executor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    parse() пропускает файлы, для которых ParallelExecutor вернул None (задача
    завершилась ожидаемой ошибкой, например ComponentParsingError), не прерывая
    обработку остальных файлов и не падая на None."""
    f1 = _write_manifest(tmp_path, "broken", _minimal_manifest(comp_name="broken"))
    f2 = _write_manifest(tmp_path, "mylib", _minimal_manifest(comp_name="mylib"))
    parser = ManifestParser(target_platform="2.2")

    # Первый файл эмулирует задачу, завершившуюся ожидаемой ошибкой в ParallelExecutor
    # (результат для неё — None), второй файл разбирается нормально.
    monkeypatch.setattr(
        parser._executor,
        "execute",
        lambda fn, _, task_label="": [None, fn(f2)],
    )

    components, _ = parser.parse([f1, f2], component_names=[], filter_mode="include")

    assert len(components) == 1
    assert components[0].name == "mylib"


@pytest.mark.business_logic
def test_filter_mode_unknown_value_disables_filtering(tmp_path: Path) -> None:
    """
    Неизвестное значение filter_mode (не 'exclude' и не 'include') не
    фильтрует компоненты и не вызывает ошибку — обрабатываются все файлы,
    как если бы фильтрация была отключена."""
    content = _minimal_manifest(comp_name="mylib", git_project="P", git_repo="mylib")
    f = _write_manifest(tmp_path, "mylib", content)
    parser = ManifestParser(target_platform="2.2")

    components, _ = parser.parse([f], component_names=["mylib"], filter_mode="unknown")

    assert len(components) == 1
    assert components[0].name == "mylib"


@pytest.mark.business_logic
def test_git_url_empty_when_no_collection_url_and_no_git_repo(tmp_path: Path) -> None:
    """
    Component.git_url остаётся пустой строкой, если не задан ни
    tfs_collection_url у парсера, ни git_repo_name в манифесте — собрать
    ссылку не из чего, и парсер не должен подставлять частичный/некорректный URL."""
    content = _minimal_manifest(comp_name="mylib", git_project="P", git_repo="")
    f = _write_manifest(tmp_path, "mylib", content)
    parser = ManifestParser(target_platform="2.2")  # tfs_collection_url по умолчанию ""

    components, _ = parser.parse([f], component_names=[], filter_mode="include")

    assert components[0].git_url == ""
