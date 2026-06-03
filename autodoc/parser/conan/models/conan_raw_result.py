"""
Сырые результаты выполнения команд Conan.

ConanRawResult     — сырой результат одного вызова conan graph info.
ConanCommandRecord — запись об одном выполненном вызове.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class ConanRawResult:
    """Сырой результат одного вызова ``conan graph info``."""

    success: bool
    data: dict[str, Any] | None
    error: str = ""


@dataclass
class ConanCommandRecord:
    """Запись об одном выполненном вызове ``conan graph info``."""

    command: str
    status: str  # "SUCCESS" | "FAILED"
    error: str = ""
