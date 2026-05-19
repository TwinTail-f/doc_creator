"""Юнит-тесты для autodoc/parser/clients/tfs_client_enums.py.

Фиксирует строковые значения перечислений TFS API на уровне протокола.
Сбой теста означает, что рефакторинг изменил значение, передаваемое в HTTP-запросах,
что молча сломает результаты запросов к TFS.
"""
import pytest

from autodoc.parser.clients.tfs_client_enums import RecursionLevel, VersionType


class TestRecursionLevel:
    """Проверки строковых значений протокола для RecursionLevel."""

    @pytest.mark.infrastructure
    def test_one_level_value(self) -> None:
        """RecursionLevel.ONE_LEVEL должен быть равен 'OneLevel'."""
        assert RecursionLevel.ONE_LEVEL == "OneLevel"

    @pytest.mark.infrastructure
    def test_full_value(self) -> None:
        """RecursionLevel.FULL должен быть равен 'Full'."""
        assert RecursionLevel.FULL == "Full"

    @pytest.mark.infrastructure
    def test_all_members_are_strings(self) -> None:
        """Все элементы RecursionLevel должны быть экземплярами str (контракт str-enum)."""
        for member in RecursionLevel:
            assert isinstance(member, str)


class TestVersionType:
    """Проверки строковых значений протокола для VersionType."""

    @pytest.mark.infrastructure
    def test_branch_value(self) -> None:
        """VersionType.BRANCH должен быть равен 'branch'."""
        assert VersionType.BRANCH == "branch"

    @pytest.mark.infrastructure
    def test_tag_value(self) -> None:
        """VersionType.TAG должен быть равен 'tag'."""
        assert VersionType.TAG == "tag"

    @pytest.mark.infrastructure
    def test_commit_value(self) -> None:
        """VersionType.COMMIT должен быть равен 'commit'."""
        assert VersionType.COMMIT == "commit"

    @pytest.mark.infrastructure
    def test_all_members_are_strings(self) -> None:
        """Все элементы VersionType должны быть экземплярами str."""
        for member in VersionType:
            assert isinstance(member, str)
