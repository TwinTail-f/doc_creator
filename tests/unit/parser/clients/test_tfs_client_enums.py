"""Юнит-тесты для autodoc/parser/clients/tfs_client_enums.py.

Pins the wire-format string values of TFS API enums.
A test failure here means a refactor changed a value sent in HTTP requests,
which would silently break TFS query results.
"""
import pytest

from autodoc.parser.clients.tfs_client_enums import RecursionLevel, VersionType


class TestRecursionLevel:
    """Wire-value assertions for RecursionLevel."""

    @pytest.mark.infrastructure
    def test_one_level_value(self) -> None:
        """RecursionLevel.ONE_LEVEL must equal 'OneLevel'."""
        assert RecursionLevel.ONE_LEVEL == "OneLevel"

    @pytest.mark.infrastructure
    def test_full_value(self) -> None:
        """RecursionLevel.FULL must equal 'Full'."""
        assert RecursionLevel.FULL == "Full"

    @pytest.mark.infrastructure
    def test_all_members_are_strings(self) -> None:
        """All RecursionLevel members must be str instances (str-enum contract)."""
        for member in RecursionLevel:
            assert isinstance(member, str)


class TestVersionType:
    """Wire-value assertions for VersionType."""

    @pytest.mark.infrastructure
    def test_branch_value(self) -> None:
        """VersionType.BRANCH must equal 'branch'."""
        assert VersionType.BRANCH == "branch"

    @pytest.mark.infrastructure
    def test_tag_value(self) -> None:
        """VersionType.TAG must equal 'tag'."""
        assert VersionType.TAG == "tag"

    @pytest.mark.infrastructure
    def test_commit_value(self) -> None:
        """VersionType.COMMIT must equal 'commit'."""
        assert VersionType.COMMIT == "commit"

    @pytest.mark.infrastructure
    def test_all_members_are_strings(self) -> None:
        """All VersionType members must be str instances."""
        for member in VersionType:
            assert isinstance(member, str)
