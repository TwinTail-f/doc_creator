"""Юнит-тесты для autodoc.parser.parsers.manifest_parser.ManifestParser.

Охватывает: parse, _parse_single_file, _build_releases.
Реальные .properties-файлы читаются из фикстуры resources_dir.
Пользовательское/граничное содержимое записывается в tmp_path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autodoc.parser.parsers.manifest_parser import ManifestParser

# ---------------------------------------------------------------------------
# Константы уровня модуля
# ---------------------------------------------------------------------------

TARGET_PLATFORM: str = "2.0"
CHANNEL_TECH: str = "tech"
NULL_PACKAGE_ID: str = "da39a3ee5e6b4b0d3255bfef95601890afd80709"

VALID_SINGLE_CONTENT: str = (
    "name= openssl\n"
    "description= TLS library\n"
    "versions.component= 3.0.0\n"
    "versions.platform= 2.0-tech\n"
    "profiles-3.0.0-2.0-tech= hw-linux-x86_64-gcc10_2, hw-linux-armv7-gcc10_2\n"
    "tfs_git_project= DEP_Components\n"
    "git_repo_name= contrib_openssl\n"
)

VALID_PATCHELF_CONTENT: str = (
    "name= patchelf\n"
    "description= ELF patcher\n"
    "versions.component= 1.0\n"
    "versions.platform= 2.0-tech\n"
    "profiles-1.0-2.0-tech= hw-linux-x86_64-gcc10_2\n"
    "tfs_git_project= DEP_Components\n"
    "git_repo_name= contrib_patchelf\n"
)


# ---------------------------------------------------------------------------
# Вспомогательная функция
# ---------------------------------------------------------------------------


def write_props(tmp_path: Path, filename: str, content: str) -> Path:
    """Записывает содержимое в .properties-файл в tmp_path и возвращает путь."""
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return p


# ===========================================================================
# Успешный путь: один компонент, один релиз
# ===========================================================================


def test_manifest_parser_parse_single_valid_file(tmp_path: Path) -> None:
    """ManifestParser возвращает один компонент с двумя profile_builds для корректного файла."""
    path = write_props(tmp_path, "openssl.properties", VALID_SINGLE_CONTENT)
    components, _ = ManifestParser(TARGET_PLATFORM).parse([path], excluded=[])
    assert len(components) == 1
    assert components[0].name == "openssl"
    assert len(components[0].releases[0].profile_builds) == 2


# ===========================================================================
# Файл без поля 'name' молча пропускается
# ===========================================================================


def test_manifest_parser_skips_file_without_name(tmp_path: Path) -> None:
    """ManifestParser молча пропускает .properties-файл, не содержащий ключ 'name'."""
    path = write_props(tmp_path, "noname.properties", "description= test\n")
    components, warnings = ManifestParser(TARGET_PLATFORM).parse([path], excluded=[])
    assert len(components) == 0
    assert len(warnings) == 0


# ===========================================================================
# Исключённый компонент не возвращается
# ===========================================================================


def test_manifest_parser_excluded_component_not_returned(tmp_path: Path) -> None:
    """ManifestParser пропускает компоненты, чьё имя присутствует в списке исключений."""
    path = write_props(tmp_path, "patchelf.properties", VALID_PATCHELF_CONTENT)
    components, _ = ManifestParser(TARGET_PLATFORM).parse([path], excluded=["patchelf"])
    assert len(components) == 0


# ===========================================================================
# Несоответствие версии платформы → релиз не создаётся
# ===========================================================================


def test_manifest_parser_platform_mismatch_no_release(tmp_path: Path) -> None:
    """ManifestParser не возвращает компоненты, если все версии платформы не совпадают с целевой."""
    content = (
        "name= libfoo\n"
        "versions.component= 1.0\n"
        "versions.platform= 1.0-tech\n"
        "profiles-1.0-1.0-tech= hw-linux-x86_64-gcc10_2\n"
    )
    path = write_props(tmp_path, "libfoo.properties", content)
    components, _ = ManifestParser(TARGET_PLATFORM).parse([path], excluded=[])
    assert len(components) == 0


# ===========================================================================
# Несуществующий файл генерирует предупреждение
# ===========================================================================


def test_manifest_parser_missing_file_produces_warning() -> None:
    """ManifestParser записывает предупреждение и не возвращает компоненты для несуществующего файла."""
    missing = Path("nonexistent.properties")
    components, warnings = ManifestParser(TARGET_PLATFORM).parse([missing], excluded=[])
    assert len(components) == 0
    assert len(warnings) == 1


# ===========================================================================
# Несколько версий компонента → несколько релизов
# ===========================================================================


def test_manifest_parser_multiple_component_versions_produce_multiple_releases(
    tmp_path: Path,
) -> None:
    """ManifestParser создаёт один релиз для каждой совпадающей пары компонент-версия / платформа."""
    content = (
        "name= patchelf\n"
        "versions.component= 0.16.1, 0.18.0\n"
        "versions.platform= 2.0-tech\n"
        "profiles-0.16.1-2.0-tech= hw-linux-x86_64-gcc10_2\n"
        "profiles-0.18.0-2.0-tech= hw-linux-x86_64-gcc10_2, hw-linux-armv7-gcc10_2\n"
    )
    path = write_props(tmp_path, "patchelf.properties", content)
    components, _ = ManifestParser(TARGET_PLATFORM).parse([path], excluded=[])
    assert len(components) == 1
    releases = components[0].releases
    assert len(releases) == 2
    release_018 = next(r for r in releases if r.version == "0.18.0")
    assert len(release_018.profile_builds) == 2


# ===========================================================================
# Канал извлекается из суффикса версии платформы
# ===========================================================================


def test_manifest_parser_channel_extracted_from_platform_suffix(
    tmp_path: Path,
) -> None:
    """ManifestParser устанавливает release.channel равным части после первого '-' в версии платформы."""
    content = (
        "name= libfoo\n"
        "versions.component= 1.0\n"
        "versions.platform= 2.0-fast\n"
        "profiles-1.0-2.0-fast= hw-linux-x86_64-gcc10_2\n"
    )
    path = write_props(tmp_path, "libfoo.properties", content)
    components, _ = ManifestParser(TARGET_PLATFORM).parse([path], excluded=[])
    assert components[0].releases[0].channel == "fast"


# ===========================================================================
# Версия платформы без суффикса → пустой канал
# ===========================================================================


def test_manifest_parser_platform_without_suffix_empty_channel(
    tmp_path: Path,
) -> None:
    """ManifestParser устанавливает release.channel в '', если версия платформы не имеет суффикса '-'."""
    content = (
        "name= libfoo\n"
        "versions.component= 1.0\n"
        "versions.platform= 2.0\n"
        "profiles-1.0-2.0= hw-linux-x86_64-gcc10_2\n"
    )
    path = write_props(tmp_path, "libfoo.properties", content)
    components, _ = ManifestParser(TARGET_PLATFORM).parse([path], excluded=[])
    assert components[0].releases[0].channel == ""


# ===========================================================================
# git_url строится из tfs_git_project и git_repo_name
# ===========================================================================


def test_manifest_parser_git_url_constructed_correctly(tmp_path: Path) -> None:
    """ManifestParser строит release.git_url в виде '<project>/_git/<repo>'."""
    content = (
        "name= openssl\n"
        "versions.component= 1.0\n"
        "versions.platform= 2.0-tech\n"
        "profiles-1.0-2.0-tech= hw-linux-x86_64-gcc10_2\n"
        "tfs_git_project= DEP_Components\n"
        "git_repo_name= contrib_openssl\n"
    )
    path = write_props(tmp_path, "openssl.properties", content)
    components, _ = ManifestParser(TARGET_PLATFORM).parse([path], excluded=[])
    assert components[0].releases[0].git_url == "DEP_Components/_git/contrib_openssl"


# ===========================================================================
# Отсутствующий ключ profiles для пары версий → нет релиза
# ===========================================================================


def test_manifest_parser_missing_profiles_key_skips_version_pair(
    tmp_path: Path,
) -> None:
    """ManifestParser пропускает пару версий, для которой нет совпадающего ключа profiles."""
    content = (
        "name= libfoo\n" "versions.component= 1.0\n" "versions.platform= 2.0-tech\n"
    )
    path = write_props(tmp_path, "libfoo.properties", content)
    components, _ = ManifestParser(TARGET_PLATFORM).parse([path], excluded=[])
    assert len(components) == 0


# ===========================================================================
# Несколько файлов разобрано → результаты накоплены
# ===========================================================================


def test_manifest_parser_multiple_files_accumulated(tmp_path: Path) -> None:
    """ManifestParser накапливает компоненты из нескольких корректных файлов."""
    path_a = write_props(tmp_path, "openssl.properties", VALID_SINGLE_CONTENT)
    path_b = write_props(tmp_path, "patchelf.properties", VALID_PATCHELF_CONTENT)
    components, _ = ManifestParser(TARGET_PLATFORM).parse([path_a, path_b], excluded=[])
    assert len(components) == 2


# ===========================================================================
# Реальный openssl.properties разбирается корректно (использует resources_dir)
# ===========================================================================


def test_manifest_parser_parses_real_openssl_file(resources_dir: Path) -> None:
    """ManifestParser корректно разбирает реальный файл ресурса openssl.properties."""
    props_file = resources_dir / "manifests" / "openssl.properties"
    components, warnings = ManifestParser(TARGET_PLATFORM).parse(
        [props_file], excluded=[]
    )
    names = [c.name for c in components]
    assert "openssl" in names
