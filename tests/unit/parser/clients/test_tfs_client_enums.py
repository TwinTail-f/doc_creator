"""Юнит-тесты для autodoc/parser/clients/tfs_client_enums.py.

Фиксирует строковые значения перечислений TFS API на уровне протокола.
Сбой теста означает, что рефакторинг изменил значение, передаваемое в HTTP-запросах,
что молча сломает результаты запросов к TFS.
"""

import pytest

from autodoc.parser.clients.tfs_client_enums import RecursionLevel, VersionType


@pytest.mark.contract
@pytest.mark.parametrize(
    "member, expected",
    [
        pytest.param(RecursionLevel.ONE_LEVEL, "OneLevel", id="one-level"),
        pytest.param(RecursionLevel.FULL, "Full", id="full"),
    ],
)
def test_recursion_level_value(member: RecursionLevel, expected: str) -> None:
    """RecursionLevel-член должен быть равен зафиксированной строке протокола TFS Items API."""
    assert member == expected


@pytest.mark.contract
@pytest.mark.parametrize(
    "member, expected",
    [
        pytest.param(VersionType.BRANCH, "branch", id="branch"),
        pytest.param(VersionType.TAG, "tag", id="tag"),
        pytest.param(VersionType.COMMIT, "commit", id="commit"),
    ],
)
def test_version_type_value(member: VersionType, expected: str) -> None:
    """VersionType-член должен быть равен зафиксированной строке versionDescriptor.versionType."""
    assert member == expected
