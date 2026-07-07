"""Unit tests for PageHierarchyManager.

Covers:
- ensure_hierarchy_exists makes exactly two create_page calls (when pages don't yet exist).
- First call uses root_parent_id and component_name as the title.
- Second call uses the ID returned by the first call as the parent.
- Second call title is "<comp_name> <release_version>".
- Return value is the ID from the second call.
- Both calls receive the correct space key.
"""

from __future__ import annotations

import pytest

from autodoc.publisher.clients.models.page_result import PageResult
from autodoc.publisher.page_manager.hierarchy_manager import PageHierarchyManager
from tests.unit.publisher.conftest import FakeConfluenceClient

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

_COMP_RESPONSE = PageResult(id=COMP_PAGE_ID, version=1, status="created", message="")
_VERSION_RESPONSE = PageResult(id=VERSION_PAGE_ID, version=1, status="created", message="")


def _make_manager(client: FakeConfluenceClient) -> PageHierarchyManager:
    """Constructs a PageHierarchyManager with a pre-configured FakeConfluenceClient.

    Neither page exists yet (resolve_existing_page_id returns None by default,
    since no pages are pre-registered), so ensure_hierarchy_exists() must call
    create_page() for both the component and the version page.
    """
    client.create_responses = [_COMP_RESPONSE, _VERSION_RESPONSE]
    return PageHierarchyManager(client)


def _create_calls(client: FakeConfluenceClient) -> list[dict]:
    """Filters recorded client calls to only create_page entries."""
    return [c for c in client.calls if c["method"] == "create_page"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_ensure_hierarchy_calls_publish_page_twice(
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """ensure_hierarchy_exists makes exactly two create_page calls when neither page exists yet."""
    manager = _make_manager(publisher_confluence_client)

    manager.ensure_hierarchy_exists(SPACE, ROOT_PAGE_ID, COMP_NAME, RELEASE_VERSION)

    assert len(_create_calls(publisher_confluence_client)) == 2


@pytest.mark.business_logic
def test_ensure_hierarchy_first_call_uses_root_as_parent(
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """First create_page call must use ROOT_PAGE_ID as parent and COMP_NAME as title."""
    manager = _make_manager(publisher_confluence_client)

    manager.ensure_hierarchy_exists(SPACE, ROOT_PAGE_ID, COMP_NAME, RELEASE_VERSION)

    first_call = _create_calls(publisher_confluence_client)[0]
    assert first_call["parent_id"] == ROOT_PAGE_ID
    assert first_call["title"] == COMP_NAME


@pytest.mark.business_logic
def test_ensure_hierarchy_second_call_uses_comp_id_as_parent(
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """Second create_page call must use the ID returned by the first call as parent_id."""
    manager = _make_manager(publisher_confluence_client)

    manager.ensure_hierarchy_exists(SPACE, ROOT_PAGE_ID, COMP_NAME, RELEASE_VERSION)

    second_call = _create_calls(publisher_confluence_client)[1]
    assert second_call["parent_id"] == COMP_PAGE_ID


@pytest.mark.business_logic
def test_ensure_hierarchy_second_call_title_is_comp_version(
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """Second create_page call title must be '<comp_name> <release_version>'."""
    manager = _make_manager(publisher_confluence_client)

    manager.ensure_hierarchy_exists(SPACE, ROOT_PAGE_ID, COMP_NAME, RELEASE_VERSION)

    second_call = _create_calls(publisher_confluence_client)[1]
    assert second_call["title"] == f"{COMP_NAME} {RELEASE_VERSION}"


@pytest.mark.business_logic
def test_ensure_hierarchy_returns_version_page_id(
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """Return value must be the ID from the second create_page response."""
    manager = _make_manager(publisher_confluence_client)

    result = manager.ensure_hierarchy_exists(SPACE, ROOT_PAGE_ID, COMP_NAME, RELEASE_VERSION)

    assert result == VERSION_PAGE_ID


@pytest.mark.business_logic
def test_ensure_hierarchy_passes_space_to_both_calls(
    publisher_confluence_client: FakeConfluenceClient,
) -> None:
    """Both create_page calls must receive the same space key."""
    manager = _make_manager(publisher_confluence_client)

    manager.ensure_hierarchy_exists(SPACE, ROOT_PAGE_ID, COMP_NAME, RELEASE_VERSION)

    calls = _create_calls(publisher_confluence_client)
    assert calls[0]["space"] == SPACE
    assert calls[1]["space"] == SPACE


# ---------------------------------------------------------------------------
# Part-3 BL additions: BL-PHM-01…05  (using inline stub clients)
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_component_page_created_under_root_parent() -> None:
    """
    BL-PHM-01
    Business Rule: component page is created with parent_id = root_parent_id.

    Preconditions:
        - A RecordingClient is wired that records all publish_page calls.

    Steps:
        1. Call manager.ensure_hierarchy_exists(space, root_parent_id, comp, version).

    Expected Result:
        At least one publish_page call is recorded, and the first call
        uses root_parent_id as its parent_id argument.
    """
    recorded: list[dict] = []

    class _Client:
        _counter = [1000]

        def resolve_existing_page_id(self, space, parent_id, title):
            return None

        def create_page(self, space, parent_id, title, body_html):
            _id = str(self._counter[0])
            self._counter[0] += 1
            recorded.append({"space": space, "parent_id": parent_id, "title": title})
            return PageResult(id=_id, version=1, status="created", message="")

        def find_page(self, title, space=None, expand=None):
            return None

        def get_page(self, page_id, expand=None):
            return None

        def get_page_body(self, space, title):
            return " "

    manager = PageHierarchyManager(_Client())
    manager.ensure_hierarchy_exists(
        space="DEV",
        root_parent_id="ROOT_PAGE",
        component_name="mylib",
        release_version="1.0.0",
    )

    assert len(recorded) >= 1, "At least one publish_page call must exist (component page)"
    first_call = recorded[0]
    assert first_call["parent_id"] == "ROOT_PAGE", (
        f"First publish_page call must use root_parent_id='ROOT_PAGE', "
        f"got parent_id='{first_call['parent_id']}'"
    )


@pytest.mark.business_logic
def test_version_page_created_under_component_page() -> None:
    """
    BL-PHM-02
    Business Rule: release/version page is created with parent_id = id(component page).

    Preconditions:
        - The first publish_page call (component page) returns a known component_page_id.

    Steps:
        1. Create an inline client whose first publish_page returns component_page_id.
        2. Call ensure_hierarchy_exists(space, ROOT, comp, version).

    Expected Result:
        The second publish_page call (release page) has parent_id == component_page_id,
        forming the hierarchy: root → mylib → mylib 1.0.0.
    """
    call_log: list[dict] = []
    component_page_id = "COMP_PAGE_ID"
    call_seq = [0]

    class _Client:
        def resolve_existing_page_id(self, space, parent_id, title):
            return None

        def create_page(self, space, parent_id, title, body_html):
            call_seq[0] += 1
            call_log.append({"title": title, "parent_id": parent_id})
            if call_seq[0] == 1:
                return PageResult(id=component_page_id, version=1, status="created", message="")
            return PageResult(id="VERSION_PAGE_ID", version=1, status="created", message="")

        def find_page(self, title, space=None, expand=None):
            return None

        def get_page(self, page_id, expand=None):
            return None

        def get_page_body(self, space, title):
            return " "

    manager = PageHierarchyManager(_Client())
    manager.ensure_hierarchy_exists(
        space="DEV",
        root_parent_id="ROOT",
        component_name="mylib",
        release_version="1.0.0",
    )

    version_calls = [c for c in call_log if "1.0.0" in c.get("title", "")]
    assert len(version_calls) >= 1, "A release page must be created"
    version_call = version_calls[0]
    assert version_call["parent_id"] == component_page_id, (
        f"Release page must be a child of the component page '{component_page_id}', "
        f"got parent_id='{version_call['parent_id']}'"
    )


@pytest.mark.business_logic
def test_returns_version_page_id_not_component_page_id() -> None:
    """
    BL-PHM-03
    Business Rule: ensure_hierarchy_exists returns the ID of the RELEASE page,
    not the component page.

    Preconditions:
        - First publish_page returns component_page_id.
        - Second publish_page returns version_page_id.

    Steps:
        1. Call ensure_hierarchy_exists and capture the return value.

    Expected Result:
        The returned ID equals version_page_id (the second-level page),
        because the passport is created as a child of the release page.
    """
    component_page_id = "COMP_PAGE_42"
    version_page_id = "VERSION_PAGE_99"
    call_seq = [0]

    class _Client:
        def resolve_existing_page_id(self, space, parent_id, title):
            return None

        def create_page(self, space, parent_id, title, body_html):
            call_seq[0] += 1
            if call_seq[0] == 1:
                return PageResult(id=component_page_id, version=1, status="created", message="")
            return PageResult(id=version_page_id, version=1, status="created", message="")

        def find_page(self, title, space=None, expand=None):
            return None

        def get_page(self, page_id, expand=None):
            return None

        def get_page_body(self, space, title):
            return " "

    manager = PageHierarchyManager(_Client())
    returned_id = manager.ensure_hierarchy_exists(
        space="DEV",
        root_parent_id="ROOT",
        component_name="mylib",
        release_version="1.0.0",
    )

    assert returned_id == version_page_id, (
        f"Must return the release page ID '{version_page_id}', " f"got '{returned_id}'"
    )


@pytest.mark.business_logic
def test_hierarchy_calls_are_idempotent() -> None:
    """
    BL-PHM-04
    Business Rule: if pages already exist (publish_page returns the existing ID),
    the result remains the same on repeated calls.

    Preconditions:
        - Confluence client always returns the same fixed page ID (pages already exist).

    Steps:
        1. Call ensure_hierarchy_exists twice with the same arguments.

    Expected Result:
        Both calls return the same version_page_id (idempotency).
    """
    fixed_version_page_id = "EXISTING_VERSION_PAGE"

    class _Client:
        def resolve_existing_page_id(self, space, parent_id, title):
            return None

        def create_page(self, space, parent_id, title, body_html):
            return PageResult(id=fixed_version_page_id, version=2, status="created", message="")

        def find_page(self, title, space=None, expand=None):
            return None

        def get_page(self, page_id, expand=None):
            return None

        def get_page_body(self, space, title):
            return " "

    manager = PageHierarchyManager(_Client())

    id_first = manager.ensure_hierarchy_exists(
        space="DEV",
        root_parent_id="ROOT",
        component_name="mylib",
        release_version="1.0.0",
    )
    id_second = manager.ensure_hierarchy_exists(
        space="DEV",
        root_parent_id="ROOT",
        component_name="mylib",
        release_version="1.0.0",
    )

    assert id_first == id_second, "Repeated calls must return the same page_id (idempotency)"


@pytest.mark.business_logic
def test_version_page_title_format() -> None:
    """
    BL-PHM-05
    Business Rule: release page title format is '{comp_name} {release_version}'.

    Preconditions:
        - A title-capturing client records all page titles passed to publish_page.

    Steps:
        1. Call ensure_hierarchy_exists with component_name='openssl', release_version='3.0.1'.

    Expected Result:
        Among the recorded titles, at least one contains both 'openssl' and '3.0.1',
        confirming the '{comp_name} {release_version}' format is used for the release page.
    """
    created_titles: list[str] = []
    seq = [0]

    class _Client:
        def resolve_existing_page_id(self, space, parent_id, title):
            return None

        def create_page(self, space, parent_id, title, body_html):
            seq[0] += 1
            created_titles.append(title)
            return PageResult(id=f"page-id-{seq[0]}", version=1, status="created", message="")

        def find_page(self, title, space=None, expand=None):
            return None

        def get_page(self, page_id, expand=None):
            return None

        def get_page_body(self, space, title):
            return " "

    manager = PageHierarchyManager(_Client())
    manager.ensure_hierarchy_exists(
        space="DEV",
        root_parent_id="ROOT",
        component_name="openssl",
        release_version="3.0.1",
    )

    assert any(
        "openssl" in t and "3.0.1" in t for t in created_titles
    ), f"Release title must contain 'openssl' and '3.0.1', recorded titles: {created_titles}"
