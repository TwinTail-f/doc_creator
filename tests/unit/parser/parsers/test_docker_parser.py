"""Юнит-тесты для autodoc.parser.parsers.docker_parser.DockerParser.

Охватывает: extract_from_yaml, extract_docker_image, add_aliases.
"""

import pytest

from autodoc.parser.parsers.docker_parser import DockerParser, DockerLinksMap

DOCKER_IMAGE: str = "harbor.example.com/debian11:components"
PROFILE_LINUX: str = "linux-x86_64-gcc10_2"


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "docker_value, expected_image",
    [
        # docker задан простой строкой
        pytest.param(DOCKER_IMAGE, DOCKER_IMAGE, id="plain-string"),
        # docker задан словарём с ключом 'image'
        pytest.param(
            {"image": "harbor.example.com/image:tag"},
            "harbor.example.com/image:tag",
            id="dict-image-key",
        ),
    ],
)
def test_extract_from_yaml_docker_value_formats(docker_value: object, expected_image: str) -> None:
    """extract_from_yaml сопоставляет ключ arch с URL docker-образа независимо
    от того, задан ли docker простой строкой или словарём с ключом 'image'."""
    content: dict = {
        "archs": {
            PROFILE_LINUX: {
                "profile_host": PROFILE_LINUX,
                "docker": docker_value,
            }
        }
    }
    links: DockerLinksMap = DockerParser.extract_from_yaml(content)
    assert links[PROFILE_LINUX] == expected_image


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "content",
    [
        # ключ 'common' зарезервирован и всегда пропускается
        pytest.param(
            {"archs": {"common": {"docker": DOCKER_IMAGE}}},
            id="reserved-common-key",
        ),
        # запись arch не содержит поле 'docker'
        pytest.param(
            {"archs": {PROFILE_LINUX: {"profile_host": PROFILE_LINUX}}},
            id="entry-without-docker-field",
        ),
        # значение arch не является словарём (ни строка, ни список)
        pytest.param(
            {
                "archs": {
                    PROFILE_LINUX: "not-a-dict",
                    "also-bad": ["still", "not", "a", "dict"],
                }
            },
            id="non-dict-arch-value",
        ),
        # в content вовсе отсутствует ключ 'archs'
        pytest.param({}, id="missing-archs-key"),
    ],
)
def test_extract_from_yaml_returns_empty_for_unusable_entries(content: dict) -> None:
    """extract_from_yaml возвращает пустой маппинг, если ни одна запись 'archs' не
    даёт docker-образ: зарезервированный ключ 'common', отсутствие поля 'docker',
    не-словарное значение arch или отсутствие самого ключа 'archs'."""
    links: DockerLinksMap = DockerParser.extract_from_yaml(content)
    assert links == {}


@pytest.mark.business_logic
def test_extract_from_yaml_missing_profile_host_only_adds_key_alias() -> None:
    """extract_from_yaml добавляет только псевдонимы по ключу arch, если поле profile_host отсутствует."""
    content: dict = {
        "archs": {
            PROFILE_LINUX: {"docker": DOCKER_IMAGE},
        }
    }
    links: DockerLinksMap = DockerParser.extract_from_yaml(content)
    assert links[PROFILE_LINUX] == DOCKER_IMAGE
    assert len(links) == 1


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
    links: DockerLinksMap = DockerParser.extract_from_yaml(content)
    assert links == {"multi-arch": DOCKER_IMAGE, "prof-a": DOCKER_IMAGE, "prof-b": DOCKER_IMAGE}


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "name, expected_keys",
    [
        # вложенное имя с расширением -> полный путь, имя файла, stem и parent/stem
        pytest.param(
            "path/to/profile.jinja",
            {"path/to/profile.jinja", "profile.jinja", "profile", "path/to/profile"},
            id="nested-path-with-extension",
        ),
        # плоское (невложенное) имя -> регистрируется только само имя, без parent/stem
        pytest.param(
            "hw-linux-x86_64-gcc10_2",
            {"hw-linux-x86_64-gcc10_2"},
            id="flat-name-no-parent",
        ),
    ],
)
def test_add_aliases_registers_expected_keys(name: str, expected_keys: set[str]) -> None:
    """add_aliases регистрирует полный путь, имя файла, stem и (при наличии
    родительской директории) parent/stem — все под одним и тем же docker-образом."""
    links: DockerLinksMap = {}
    DockerParser.add_aliases(name, "img:tag", links)
    assert set(links.keys()) == expected_keys
    assert all(value == "img:tag" for value in links.values())


@pytest.mark.business_logic
def test_add_aliases_empty_name_does_nothing() -> None:
    """add_aliases оставляет словарь links без изменений, когда name — пустая строка."""
    links: DockerLinksMap = {}
    DockerParser.add_aliases("", "img:tag", links)
    assert links == {}


@pytest.mark.business_logic
def test_extract_docker_image_none_returns_empty_string() -> None:
    """extract_docker_image возвращает '', если значение поля docker равно None."""
    result = DockerParser.extract_docker_image({"docker": None})
    assert result == ""
