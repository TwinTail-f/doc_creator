"""
Enum-типы для TFS Items API.
"""

from enum import Enum


class RecursionLevel(str, Enum):
    """Допустимые уровни рекурсии для TFS Items API."""

    ONE_LEVEL = "OneLevel"
    FULL = "Full"


class VersionType(str, Enum):
    """Тип версии для versionDescriptor TFS Items API."""

    BRANCH = "branch"
    TAG = "tag"
    COMMIT = "commit"
