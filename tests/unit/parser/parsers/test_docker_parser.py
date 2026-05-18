"""Юнит-тесты для autodoc.parser.parsers.docker_parser.DockerParser.

Охватывает: extract_from_yaml, extract_docker_image, add_aliases.
Все тесты работают с in-memory словарями — ввод/вывод не требуется.
"""

from __future__ import annotations
import pytest

from autodoc.parser.parsers.docker_parser import DockerParser, DockerLinksMap

# ---------------------------------------------------------------------------
# Константы уровня модуля
# ---------------------------------------------------------------------------

DOCKER_IMAGE: str = "harbor.example.com/debian11:components"
DOCKER_IMAGE_DICT: str = "harbor.example.com/image:tag"
PROFILE_LINUX: str = "linux-x86_64-gcc10_2"
PROFILE_WITH_PATH: str = "path/to/profile.jinja"
PROFILE_FLAT: str = "hw-linux-x86_64-gcc10_2"


# ===========================================================================
# extract_from_yaml: docker-значение в виде простой строки
# ===========================================================================


@pytest.mark.infrastructure
def test_extract_from_yaml_plain_string_docker() -> None:
    """extract_from_yaml сопоставляет ключ arch с URL docker-образа в виде простой строки."""
    content: dict = {
        "archs": {
            PROFILE_LINUX: {
                "profile_host": PROFILE_LINUX,
                "docker": DOCKER_IMAGE,
            }
        }
    }
    links: DockerLinksMap = {}
    DockerParser.extract_from_yaml(content, links)
    assert links[PROFILE_LINUX] == DOCKER_IMAGE


# ===========================================================================
# extract_from_yaml: docker как словарь с ключом 'image'
# ===========================================================================


@pytest.mark.infrastructure
def test_extract_from_yaml_docker_dict_image_key() -> None:
    """extract_from_yaml извлекает URL образа, когда docker-значение — словарь с ключом 'image'."""
    content: dict = {
        "archs": {
            PROFILE_LINUX: {
                "profile_host": PROFILE_LINUX,
                "docker": {"image": DOCKER_IMAGE_DICT},
            }
        }
    }
    links: DockerLinksMap = {}
    DockerParser.extract_from_yaml(content, links)
    assert links[PROFILE_LINUX] == DOCKER_IMAGE_DICT


# ===========================================================================
# extract_from_yaml: ключ 'common' пропускается
# ===========================================================================


@pytest.mark.infrastructure
def test_extract_from_yaml_skips_common_key() -> None:
    """extract_from_yaml игнорирует записи с зарезервированным ключом 'common'."""
    content: dict = {
        "archs": {
            "common": {"docker": DOCKER_IMAGE},
        }
    }
    links: DockerLinksMap = {}
    DockerParser.extract_from_yaml(content, links)
    assert links == {}


# ===========================================================================
# extract_from_yaml: запись без ключа 'docker' пропускается
# ===========================================================================


@pytest.mark.infrastructure
def test_extract_from_yaml_skips_entry_without_docker() -> None:
    """extract_from_yaml пропускает записи arch, не содержащие поле 'docker'."""
    content: dict = {
        "archs": {
            PROFILE_LINUX: {"profile_host": PROFILE_LINUX},
        }
    }
    links: DockerLinksMap = {}
    DockerParser.extract_from_yaml(content, links)
    assert links == {}


# ===========================================================================
# extract_from_yaml: profile_host как список добавляет псевдоним для каждой записи
# ===========================================================================


@pytest.mark.business_logic
def test_extract_from_yaml_profile_host_list_adds_all_aliases() -> None:
    """extract_from_yaml регистрирует docker-образ для каждого элемента списка profile_host."""
    content: dict = {
        "archs": {
            "multi-arch": {
                "profile_host": ["prof-a", "prof-b"],
                "docker": DOCKER_IMAGE,
            }
        }
    }
    links: DockerLinksMap = {}
    DockerParser.extract_from_yaml(content, links)
    assert "prof-a" in links
    assert "prof-b" in links


# ===========================================================================
# add_aliases: файл с расширением добавляет четыре различные записи
# ===========================================================================


@pytest.mark.business_logic
def test_add_aliases_with_extension_adds_four_entries() -> None:
    """add_aliases добавляет полный путь, имя файла, stem и parent/stem для вложённого .jinja-имени."""
    links: DockerLinksMap = {}
    DockerParser.add_aliases(PROFILE_WITH_PATH, "img:tag", links)
    assert links.get("path/to/profile.jinja") == "img:tag"
    assert links.get("profile.jinja") == "img:tag"
    assert links.get("profile") == "img:tag"
    assert links.get("path/to/profile") == "img:tag"


# ===========================================================================
# add_aliases: плоское имя без слешей
# ===========================================================================


@pytest.mark.business_logic
def test_add_aliases_flat_name_adds_entries() -> None:
    """add_aliases отображает плоское (невложенное) имя без добавления ключа parent/stem."""
    links: DockerLinksMap = {}
    DockerParser.add_aliases(PROFILE_FLAT, "img:tag", links)
    assert links[PROFILE_FLAT] == "img:tag"
    assert "." not in links


# ===========================================================================
# add_aliases: пустое имя ничего не делает
# ===========================================================================


@pytest.mark.infrastructure
def test_add_aliases_empty_name_does_nothing() -> None:
    """add_aliases оставляет словарь links без изменений, когда name — пустая строка."""
    links: DockerLinksMap = {}
    DockerParser.add_aliases("", "img:tag", links)
    assert links == {}


# ===========================================================================
# extract_docker_image: не строка и не словарь возвращает пустую строку
# ===========================================================================


@pytest.mark.infrastructure
def test_extract_docker_image_none_returns_empty_string() -> None:
    """extract_docker_image возвращает '', если значение поля docker равно None."""
    result = DockerParser.extract_docker_image({"docker": None})
    assert result == ""
