"""Unit tests for autodoc.parser.parsers.docker_parser.DockerParser.

Covers: extract_from_yaml, extract_docker_image, add_aliases.
All tests operate on in-memory dicts — no I/O required.
"""

from __future__ import annotations

from autodoc.parser.parsers.docker_parser import DockerParser, DockerLinksMap

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

DOCKER_IMAGE: str = "harbor.example.com/debian11:components"
DOCKER_IMAGE_DICT: str = "harbor.example.com/image:tag"
PROFILE_LINUX: str = "linux-x86_64-gcc10_2"
PROFILE_WITH_PATH: str = "path/to/profile.jinja"
PROFILE_FLAT: str = "hw-linux-x86_64-gcc10_2"


# ===========================================================================
# 4.1 — extract_from_yaml: plain string docker value
# ===========================================================================


def test_extract_from_yaml_plain_string_docker() -> None:
    """extract_from_yaml maps the arch key to a plain-string docker image URL."""
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
# 4.2 — extract_from_yaml: docker as dict with 'image' key
# ===========================================================================


def test_extract_from_yaml_docker_dict_image_key() -> None:
    """extract_from_yaml extracts the image URL when docker value is a dict with an 'image' key."""
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
# 4.3 — extract_from_yaml: 'common' key is skipped
# ===========================================================================


def test_extract_from_yaml_skips_common_key() -> None:
    """extract_from_yaml ignores entries with the reserved 'common' key."""
    content: dict = {
        "archs": {
            "common": {"docker": DOCKER_IMAGE},
        }
    }
    links: DockerLinksMap = {}
    DockerParser.extract_from_yaml(content, links)
    assert links == {}


# ===========================================================================
# 4.4 — extract_from_yaml: entry without 'docker' key is skipped
# ===========================================================================


def test_extract_from_yaml_skips_entry_without_docker() -> None:
    """extract_from_yaml skips arch entries that carry no 'docker' field."""
    content: dict = {
        "archs": {
            PROFILE_LINUX: {"profile_host": PROFILE_LINUX},
        }
    }
    links: DockerLinksMap = {}
    DockerParser.extract_from_yaml(content, links)
    assert links == {}


# ===========================================================================
# 4.5 — extract_from_yaml: profile_host as list adds alias for each entry
# ===========================================================================


def test_extract_from_yaml_profile_host_list_adds_all_aliases() -> None:
    """extract_from_yaml registers a docker image for every item in a list profile_host."""
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
# 4.6 — add_aliases: file with extension adds four distinct entries
# ===========================================================================


def test_add_aliases_with_extension_adds_four_entries() -> None:
    """add_aliases inserts full path, filename, stem, and parent/stem for a nested .jinja name."""
    links: DockerLinksMap = {}
    DockerParser.add_aliases(PROFILE_WITH_PATH, "img:tag", links)
    assert links.get("path/to/profile.jinja") == "img:tag"
    assert links.get("profile.jinja") == "img:tag"
    assert links.get("profile") == "img:tag"
    assert links.get("path/to/profile") == "img:tag"


# ===========================================================================
# 4.7 — add_aliases: flat name without slashes
# ===========================================================================


def test_add_aliases_flat_name_adds_entries() -> None:
    """add_aliases maps a flat (non-nested) name without adding a parent/stem key."""
    links: DockerLinksMap = {}
    DockerParser.add_aliases(PROFILE_FLAT, "img:tag", links)
    assert links[PROFILE_FLAT] == "img:tag"
    assert "." not in links


# ===========================================================================
# 4.8 — add_aliases: empty name does nothing
# ===========================================================================


def test_add_aliases_empty_name_does_nothing() -> None:
    """add_aliases leaves the links dict unchanged when name is an empty string."""
    links: DockerLinksMap = {}
    DockerParser.add_aliases("", "img:tag", links)
    assert links == {}


# ===========================================================================
# 4.9 — extract_docker_image: non-string, non-dict returns empty string
# ===========================================================================


def test_extract_docker_image_none_returns_empty_string() -> None:
    """extract_docker_image returns '' when the docker field value is None."""
    result = DockerParser.extract_docker_image({"docker": None})
    assert result == ""
