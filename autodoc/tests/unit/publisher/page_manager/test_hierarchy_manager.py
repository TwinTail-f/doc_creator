"""Unit tests for PageHierarchyManager.

Covers:
- ensure_hierarchy_exists makes exactly two publish_page calls.
- First call uses root_parent_id and component_name as the title.
- Second call uses the ID returned by the first call as the parent.
- Second call title is "<comp_name> <release_version>".
- Return value is the ID from the second call.
- Both calls receive the correct space key.
"""

from __future__ import annotations

import pytest

from autodoc.publisher.page_manager.hierarchy_manager import PageHierarchyManager
from autodoc.tests.unit.publisher.conftest import FakeConfluenceClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SPACE: str = "TEST"
ROOT_PAGE_ID: str = "root-001"
COMP_NAME: str = "openssl"
RELEASE_VERSION: str = "1.0.0"
COMP_PAGE_ID: str = "comp-page-001"
VERSION_PAGE_ID: str = "ver-page-001"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COMP_RESPONSE: dict = {
    "id": COMP_PAGE_ID,
    "version": 1,
    "status": "created",
    "title": COMP_NAME,
}
_VERSION_RESPONSE: dict = {
    "id": VERSION_PAGE_ID,
    "version": 1,
    "status": "created",
    "title": f"{COMP_NAME} {RELEASE_VERSION}",
}


def _make_manager(client: FakeConfluenceClient) -> PageHierarchyManager:
    """Constructs a PageHierarchyManager with a pre-configured FakeConfluenceClient."""
    client.publish_responses = [_COMP_RESPONSE, _VERSION_RESPONSE]
    return PageHierarchyManager(client)


def _publish_calls(client: FakeConfluenceClient) -> list[dict]:
    """Filters recorded client calls to only publish_page entries."""
    return [c for c in client.calls if c["method"] == "publish_page"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_ensure_hierarchy_calls_publish_page_twice(
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """ensure_hierarchy_exists makes exactly two publish_page calls."""
    manager = _make_manager(publisher_confluence_client)

    manager.ensure_hierarchy_exists(SPACE, ROOT_PAGE_ID, COMP_NAME, RELEASE_VERSION)

    assert len(_publish_calls(publisher_confluence_client)) == 2


def test_ensure_hierarchy_first_call_uses_root_as_parent(
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """First publish_page call must use ROOT_PAGE_ID as parent and COMP_NAME as title."""
    manager = _make_manager(publisher_confluence_client)

    manager.ensure_hierarchy_exists(SPACE, ROOT_PAGE_ID, COMP_NAME, RELEASE_VERSION)

    first_call = _publish_calls(publisher_confluence_client)[0]
    assert first_call["parent_id"] == ROOT_PAGE_ID
    assert first_call["title"] == COMP_NAME


def test_ensure_hierarchy_second_call_uses_comp_id_as_parent(
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """Second publish_page call must use the ID returned by the first call as parent_id."""
    manager = _make_manager(publisher_confluence_client)

    manager.ensure_hierarchy_exists(SPACE, ROOT_PAGE_ID, COMP_NAME, RELEASE_VERSION)

    second_call = _publish_calls(publisher_confluence_client)[1]
    assert second_call["parent_id"] == COMP_PAGE_ID


def test_ensure_hierarchy_second_call_title_is_comp_version(
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """Second publish_page call title must be '<comp_name> <release_version>'."""
    manager = _make_manager(publisher_confluence_client)

    manager.ensure_hierarchy_exists(SPACE, ROOT_PAGE_ID, COMP_NAME, RELEASE_VERSION)

    second_call = _publish_calls(publisher_confluence_client)[1]
    assert second_call["title"] == f"{COMP_NAME} {RELEASE_VERSION}"


def test_ensure_hierarchy_returns_version_page_id(
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """Return value must be the ID from the second publish_page response."""
    manager = _make_manager(publisher_confluence_client)

    result = manager.ensure_hierarchy_exists(
        SPACE, ROOT_PAGE_ID, COMP_NAME, RELEASE_VERSION
    )

    assert result == VERSION_PAGE_ID


def test_ensure_hierarchy_passes_space_to_both_calls(
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """Both publish_page calls must receive the same space key."""
    manager = _make_manager(publisher_confluence_client)

    manager.ensure_hierarchy_exists(SPACE, ROOT_PAGE_ID, COMP_NAME, RELEASE_VERSION)

    calls = _publish_calls(publisher_confluence_client)
    assert calls[0]["space"] == SPACE
    assert calls[1]["space"] == SPACE
