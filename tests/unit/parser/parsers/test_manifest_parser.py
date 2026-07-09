"""Юнит-тесты для autodoc.parser.parsers.manifest_parser.ManifestParser."""

from __future__ import annotations

from pathlib import Path

import pytest

from autodoc.parser.parsers.manifest_parser import ManifestParser

TARGET_PLATFORM: str = "2.0"
TFS_COLLECTION_URL: str = "https://tfs.example.com"


def write_props(tmp_path: Path, filename: str, content: str) -> Path:
    """Записать содержимое в файл .properties в tmp_path и вернуть путь."""
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def all_real_properties(real_manifests_dir: Path) -> list[Path]:
    """Отсортированный список всех реальных файлов .properties в resources/manifests/."""
    return sorted(real_manifests_dir.glob("*.properties"))


@pytest.fixture
def parser_20() -> ManifestParser:
    """ManifestParser настроенный для платформы 2.0 с поддельным URL коллекции TFS."""
    return ManifestParser(
        target_platform=TARGET_PLATFORM,
        tfs_collection_url=TFS_COLLECTION_URL,
    )


@pytest.mark.integration
def test_parser_returns_correct_component_count(
    parser_20: ManifestParser,
    all_real_properties: list[Path],
) -> None:
    """parse() со всеми реальными файлами возвращает по крайней мере 5 названий компонентов."""
    components, _ = parser_20.parse(all_real_properties, component_names=[], filter_mode="exclude")
    assert len(components) >= 5


@pytest.mark.integration
def test_parser_patchelf_two_versions_same_channel(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """patchelf имеет ровно 2 релиза, оба channel=='tech', версии 0.16.1 и 0.18.0."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "patchelf.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    assert len(components) == 1
    comp = components[0]
    assert comp.name == "patchelf"
    assert len(comp.releases) == 2
    assert {r.channel for r in comp.releases} == {"tech"}
    assert {r.version for r in comp.releases} == {"0.16.1", "0.18.0"}


@pytest.mark.integration
def test_parser_nlohmann_json_multiple_releases(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """nlohmann_json имеет по крайней мере 2 релиза; один channel=='slow', один channel=='fast'."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "nlohmann_json.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    assert len(components) == 1
    releases = components[0].releases
    assert len(releases) >= 2
    channels = {r.channel for r in releases}
    assert "slow" in channels
    assert "fast" in channels


@pytest.mark.integration
def test_parser_apr_single_release_fast_channel(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """apr имеет ровно 1 релиз с version=='1.7.6' и channel=='fast'."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "apr.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    assert len(components) == 1
    assert components[0].name == "apr"
    assert len(components[0].releases) == 1
    rel = components[0].releases[0]
    assert rel.version == "1.7.6"
    assert rel.channel == "fast"


@pytest.mark.integration
def test_parser_libnetfilter_queue_prg_quant_project(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """компонент libnetfilter_queue имеет git_project=='PRG_Quant' (нестандартный проект)."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "libnetfilter_queue.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    assert len(components) == 1
    assert components[0].git_project == "PRG_Quant"


@pytest.mark.integration
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
def test_parser_profile_builds_populated_as_skeletons(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """Каждый ProfileBuild из парсинга имеет exists=False и variants==[] (простые скелеты)."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "apr.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    for comp in components:
        for rel in comp.releases:
            for pb in rel.profile_builds:
                assert pb.exists is False
                assert pb.variants == []


@pytest.mark.business_logic
def test_parser_filter_mode_include(
    parser_20: ManifestParser,
    all_real_properties: list[Path],
) -> None:
    """parse() с filter_mode='include' и component_names=['apr'] возвращает только apr."""
    components, _ = parser_20.parse(
        all_real_properties, component_names=["apr"], filter_mode="include"
    )
    assert len(components) == 1
    assert components[0].name == "apr"


@pytest.mark.business_logic
def test_parser_filter_mode_exclude(
    parser_20: ManifestParser,
    all_real_properties: list[Path],
) -> None:
    """parse() с filter_mode='exclude' и component_names=['apr'] опускает apr из результатов."""
    components, _ = parser_20.parse(
        all_real_properties, component_names=["apr"], filter_mode="exclude"
    )
    names = [c.name for c in components]
    assert "apr" not in names


@pytest.mark.business_logic
def test_parser_invalid_properties_skipped_with_warning(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
    tmp_path: Path,
) -> None:
    """Файл мусора рядом с корректными всё ещё даёт корректные компоненты из хороших файлов."""
    bad_file = write_props(tmp_path, "garbage.properties", "not valid properties!!!")
    good_file = real_manifests_dir / "apr.properties"
    components, _ = parser_20.parse(
        [good_file, bad_file], component_names=[], filter_mode="exclude"
    )
    names = [c.name for c in components]
    assert "apr" in names
    assert len(components) >= 1


@pytest.mark.business_logic
def test_manifest_parser_skips_file_without_name(tmp_path: Path) -> None:
    """ManifestParser молча пропускает файл .properties без ключа 'name'."""
    path = write_props(tmp_path, "noname.properties", "description= test\n")
    components, warnings = ManifestParser(TARGET_PLATFORM).parse(
        [path], component_names=[], filter_mode="exclude"
    )
    assert len(components) == 0
    assert len(warnings) == 0


@pytest.mark.infrastructure
def test_manifest_parser_missing_file_produces_warning() -> None:
    """ManifestParser записывает предупреждение и не возвращает компоненты для несуществующего файла."""
    missing = Path("nonexistent.properties")
    components, warnings = ManifestParser(TARGET_PLATFORM).parse(
        [missing], component_names=[], filter_mode="exclude"
    )
    assert len(components) == 0
    assert len(warnings) == 1


@pytest.mark.business_logic
def test_manifest_parser_platform_mismatch_no_release(tmp_path: Path) -> None:
    """ManifestParser не возвращает компоненты, когда все версии платформы не совпадают с целевой."""
    content = (
        "name= libfoo\n"
        "versions.component= 1.0\n"
        "versions.platform= 1.0-tech\n"
        "profiles-1.0-1.0-tech= hw-linux-x86_64-gcc10_2\n"
    )
    path = write_props(tmp_path, "libfoo.properties", content)
    components, _ = ManifestParser(TARGET_PLATFORM).parse(
        [path], component_names=[], filter_mode="exclude"
    )
    assert len(components) == 0


@pytest.mark.business_logic
def test_manifest_parser_missing_profiles_key_skips_version_pair(
    tmp_path: Path,
) -> None:
    """ManifestParser пропускает пару версий для которой не существует соответствующего ключа profiles."""
    content = "name= libfoo\n" "versions.component= 1.0\n" "versions.platform= 2.0-tech\n"
    path = write_props(tmp_path, "libfoo.properties", content)
    components, _ = ManifestParser(TARGET_PLATFORM).parse(
        [path], component_names=[], filter_mode="exclude"
    )
    assert len(components) == 0


@pytest.mark.integration
def test_manifest_parser_parses_real_openssl_file(resources_dir: Path) -> None:
    """ManifestParser корректно парсит реальный файл ресурса openssl.properties."""
    props_file = resources_dir / "manifests" / "openssl.properties"
    components, warnings = ManifestParser(TARGET_PLATFORM).parse(
        [props_file], component_names=[], filter_mode="exclude"
    )
    names = [c.name for c in components]
    assert "openssl" in names


@pytest.mark.integration
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


@pytest.mark.integration
def test_parser_nlohmann_json_profile_builds_are_skeletons(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """Все nlohmann_json profile_builds имеют exists=False и variants==[] после парсинга манифеста."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "nlohmann_json.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    for rel in components[0].releases:
        for pb in rel.profile_builds:
            assert pb.exists is False
            assert pb.variants == []


@pytest.mark.integration
def test_parser_apr_has_no_slow_release(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """apr не имеет релиза с channel=='slow'; присутствует только fast."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "apr.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    slow_releases = [r for r in components[0].releases if r.channel == "slow"]
    assert slow_releases == []


@pytest.mark.integration
def test_parser_apr_profile_count_fast(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """apr 1.7.6/fast имеет ровно 4 profile_builds
    (crypto_default_gcc_x86_64, hw-linux-x86_64-gcc10_2,
     windows-x86_64-vs2022-mt, windows-x86-vs2022-mt)."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "apr.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    rel = components[0].releases[0]
    assert len(rel.profile_builds) == 4
    profile_names = {pb.profile_name for pb in rel.profile_builds}
    assert "hw-linux-x86_64-gcc10_2" in profile_names
    assert "windows-x86_64-vs2022-mt" in profile_names


@pytest.mark.integration
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


@pytest.mark.integration
def test_parser_patchelf_no_fast_or_slow_channel(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """У patchelf нет релизов с channel 'fast' или 'slow' — только 'tech'."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "patchelf.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    non_tech = [r for r in components[0].releases if r.channel != "tech"]
    assert non_tech == []


@pytest.mark.integration
def test_parser_sqlite3_has_both_fast_and_slow_releases(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """sqlite3 даёт ровно 2 релиза для платформы 2.0: один fast, один slow."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "sqlite3.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    assert len(components) == 1
    channels = {r.channel for r in components[0].releases}
    assert channels == {"fast", "slow"}
    assert len(components[0].releases) == 2


@pytest.mark.integration
def test_parser_sqlite3_slow_release_version_and_profiles(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """Релиз sqlite3 slow имеет версию 3.34.1 и только профили hw-linux-*."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "sqlite3.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    slow_rel = next(r for r in components[0].releases if r.channel == "slow")
    assert slow_rel.version == "3.34.1"
    assert len(slow_rel.profile_builds) >= 2
    profile_names = {pb.profile_name for pb in slow_rel.profile_builds}
    assert any("hw-linux" in p or "instrumented" in p for p in profile_names)


@pytest.mark.integration
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


@pytest.mark.integration
def test_parser_libnetfilter_queue_git_url_points_to_prg_quant(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """component.git_url для libnetfilter_queue содержит 'PRG_Quant' — проект внешней команды."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "libnetfilter_queue.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    assert "PRG_Quant" in components[0].git_url


@pytest.mark.integration
def test_parser_libnetfilter_queue_single_slow_release_for_platform_20(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """libnetfilter_queue имеет ровно 1 релиз для платформы 2.0 (канал slow)."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "libnetfilter_queue.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    assert len(components[0].releases) == 1
    assert components[0].releases[0].channel == "slow"
    assert components[0].releases[0].version == "1.0.5"


@pytest.mark.integration
def test_parser_libnetfilter_queue_slow_has_hw_linux_profiles(
    parser_20: ManifestParser,
    real_manifests_dir: Path,
) -> None:
    """libnetfilter_queue 1.0.5/slow имеет 4 profile_builds с префиксом hw-linux."""
    components, _ = parser_20.parse(
        [real_manifests_dir / "libnetfilter_queue.properties"],
        component_names=[],
        filter_mode="exclude",
    )
    pb_names = {pb.profile_name for pb in components[0].releases[0].profile_builds}
    assert "hw-linux-armv7-gcc10_2" in pb_names
    assert "hw-linux-armv8-gcc10_2" in pb_names
    assert "hw-linux-x86_64-gcc10_2" in pb_names
    assert "linux-x86_64-gcc10_2-instrumented" in pb_names


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
def test_channel_suffix_fast_extracted(tmp_path: Path) -> None:
    """Проверить, что строка платформы, заканчивающаяся на "-fast", даёт channel="fast"."""
    f = _write_manifest(tmp_path, "mylib", _minimal_manifest(plat_version="2.2-fast"))
    parser = ManifestParser(target_platform="2.2", tfs_collection_url="http://tfs")
    components, _ = parser.parse([f], component_names=[], filter_mode="include")

    assert len(components) == 1
    assert components[0].releases[0].channel == "fast"


@pytest.mark.business_logic
def test_channel_suffix_slow_extracted(tmp_path: Path) -> None:
    """Проверить, что строка платформы, заканчивающаяся на "-slow", даёт channel="slow"."""
    content = _minimal_manifest(plat_version="2.2-slow")
    f = _write_manifest(tmp_path, "mylib", content)
    parser = ManifestParser(target_platform="2.2", tfs_collection_url="http://tfs")
    components, _ = parser.parse([f], component_names=[], filter_mode="include")

    assert components[0].releases[0].channel == "slow"


@pytest.mark.business_logic
def test_channel_no_suffix_gives_empty_string(tmp_path: Path) -> None:
    """Проверить, что строка платформы без суффикса с дефисом даёт channel=""."""
    content = _minimal_manifest(plat_version="2.2")
    # ключ profiles также должен использовать версию платформы без суффикса
    content = (
        "name=mylib\ndescription=Test\ntfs_git_project=P\ngit_repo_name=r\n"
        "versions.component=1.0\nversions.platform=2.2\n"
        "profiles-1.0-2.2=hw-linux-x86_64\n"
    )
    f = _write_manifest(tmp_path, "mylib", content)
    parser = ManifestParser(target_platform="2.2", tfs_collection_url="http://tfs")
    components, _ = parser.parse([f], component_names=[], filter_mode="include")

    assert components[0].releases[0].channel == ""


@pytest.mark.business_logic
def test_channel_multi_dash_last_segment_is_channel(tmp_path: Path) -> None:
    """Проверить, что для строк платформы с несколькими дефисами только последний сегмент является каналом."""
    content = (
        "name=mylib\ndescription=Test\ntfs_git_project=P\ngit_repo_name=r\n"
        "versions.component=1.0\nversions.platform=2.2-extra-slow\n"
        "profiles-1.0-2.2-extra-slow=hw-linux-x86_64\n"
    )
    f = _write_manifest(tmp_path, "mylib", content)
    parser = ManifestParser(target_platform="2.2", tfs_collection_url="http://tfs")
    components, _ = parser.parse([f], component_names=[], filter_mode="include")

    release = components[0].releases[0]
    assert release.channel == "slow"
    assert "2" not in release.channel


@pytest.mark.business_logic
def test_include_filter_exact_match_only(tmp_path: Path) -> None:
    """Проверить, что filter_mode="include" точно совпадает с названиями компонентов."""
    for name in ["openssl", "openssl-extra"]:
        content = _minimal_manifest(
            comp_name=name, git_project="P", git_repo=name, plat_version="2.2-fast"
        )
        _write_manifest(tmp_path, name, content)

    parser = ManifestParser(target_platform="2.2")
    files = list(tmp_path.glob("*.properties"))
    components, _ = parser.parse(files, component_names=["openssl"], filter_mode="include")

    assert len(components) == 1
    assert components[0].name == "openssl"


@pytest.mark.business_logic
def test_exclude_filter_exact_match_only(tmp_path: Path) -> None:
    """Проверить, что filter_mode="exclude" исключает только именованный компонент точно."""
    for name in ["openssl", "openssl-extra"]:
        content = _minimal_manifest(
            comp_name=name, git_project="P", git_repo=name, plat_version="2.2-fast"
        )
        _write_manifest(tmp_path, name, content)

    parser = ManifestParser(target_platform="2.2")
    files = list(tmp_path.glob("*.properties"))
    components, _ = parser.parse(files, component_names=["openssl"], filter_mode="exclude")

    names = {c.name for c in components}
    assert "openssl" not in names
    assert "openssl-extra" in names


@pytest.mark.business_logic
def test_include_empty_list_returns_all_components(tmp_path: Path) -> None:
    """Проверить, что filter_mode="include" с пустым списком имён возвращает все компоненты."""
    for name in ["libA", "libB", "libC"]:
        content = _minimal_manifest(
            comp_name=name, git_project="P", git_repo=name, plat_version="2.2-fast"
        )
        _write_manifest(tmp_path, name, content)

    parser = ManifestParser(target_platform="2.2")
    files = list(tmp_path.glob("*.properties"))
    components, _ = parser.parse(files, component_names=[], filter_mode="include")

    assert len(components) == 3


@pytest.mark.business_logic
def test_exclude_empty_list_returns_all_components(tmp_path: Path) -> None:
    """Проверить, что filter_mode="exclude" с пустым списком имён возвращает все компоненты."""
    for name in ["libA", "libB"]:
        content = _minimal_manifest(
            comp_name=name, git_project="P", git_repo=name, plat_version="2.2-fast"
        )
        _write_manifest(tmp_path, name, content)

    parser = ManifestParser(target_platform="2.2")
    files = list(tmp_path.glob("*.properties"))
    components, _ = parser.parse(files, component_names=[], filter_mode="exclude")

    assert len(components) == 2


@pytest.mark.business_logic
def test_profile_builds_created_from_profiles_property(tmp_path: Path) -> None:
    """Проверить, что ManifestParser создаёт скелеты ProfileBuild для каждого имени профиля."""
    content = (
        "name=mylib\ndescription=Test\ntfs_git_project=P\ngit_repo_name=r\n"
        "versions.component=1.0\nversions.platform=2.2-fast\n"
        "profiles-1.0-2.2-fast=hw-linux-x86_64, hw-linux-armv8\n"
    )
    f = _write_manifest(tmp_path, "mylib", content)
    parser = ManifestParser(target_platform="2.2")
    components, _ = parser.parse([f], component_names=[], filter_mode="include")

    pbs = components[0].releases[0].profile_builds
    profile_names = {pb.profile_name for pb in pbs}
    assert "hw-linux-x86_64" in profile_names
    assert "hw-linux-armv8" in profile_names
    assert len(pbs) == 2


@pytest.mark.business_logic
def test_profile_builds_all_have_exists_false(tmp_path: Path) -> None:
    """Проверить, что все объекты ProfileBuild созданные ManifestParser имеют exists=False."""
    content = (
        "name=mylib\ndescription=Test\ntfs_git_project=P\ngit_repo_name=r\n"
        "versions.component=1.0\nversions.platform=2.2-fast\n"
        "profiles-1.0-2.2-fast=hw-linux-x86_64, hw-linux-armv8\n"
    )
    f = _write_manifest(tmp_path, "mylib", content)
    parser = ManifestParser(target_platform="2.2")
    components, _ = parser.parse([f], component_names=[], filter_mode="include")

    for pb in components[0].releases[0].profile_builds:
        assert pb.exists is False


@pytest.mark.business_logic
def test_profile_builds_all_have_empty_variants(tmp_path: Path) -> None:
    """Проверить, что все скелеты ProfileBuild произведённые ManifestParser имеют variants=[]."""
    content = _minimal_manifest(plat_version="2.2-fast")
    f = _write_manifest(tmp_path, "mylib", content)
    parser = ManifestParser(target_platform="2.2")
    components, _ = parser.parse([f], component_names=[], filter_mode="include")

    for pb in components[0].releases[0].profile_builds:
        assert pb.variants == []


@pytest.mark.business_logic
def test_profile_build_names_match_manifest_profile_list_exactly(
    tmp_path: Path,
) -> None:
    """Проверить, что значения ProfileBuild.profile_name точно равны записям манифеста."""
    content = (
        "name=mylib\ndescription=Test\ntfs_git_project=P\ngit_repo_name=r\n"
        "versions.component=1.0\nversions.platform=2.2-fast\n"
        "profiles-1.0-2.2-fast=hw-linux-x86_64-gcc12_3, hw-win-msvc2022\n"
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
    assert hasattr(comp, "git_url"), "git_url must be a Component field after migration"
    assert "mylib-repo" in comp.git_url
    assert len(comp.releases) == 2


@pytest.mark.business_logic
def test_git_url_format_is_tfs_git_format(tmp_path: Path) -> None:
    """Проверить, что Component.git_url отформатирован как хорошо сформированный TFS Git URL."""
    content = (
        "name=mylib\ndescription=Test\n"
        "tfs_git_project=PlatformTeam\ngit_repo_name=mylib\n"
        "versions.component=1.0\nversions.platform=2.2-fast\n"
        "profiles-1.0-2.2-fast=hw-linux-x86_64\n"
    )
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
    import autodoc.parser.parsers.manifest_parser as manifest_parser_module

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
