"""
Абстрактный интерфейс запуска команд Conan CLI.
"""

from abc import ABC, abstractmethod

from autodoc.models.conan_raw_result import ConanRawResult
from autodoc.parser.conan.conan_task import ConanTask


class BaseConanRunner(ABC):
    """Интерфейс запуска команд Conan CLI."""

    @abstractmethod
    def run(self, task: ConanTask) -> ConanRawResult:
        """
        Выполняет одну команду Conan и возвращает сырой результат.

        Args:
            task: Задача с готовой CLI-командой и метаданными.

        Returns:
            ``ConanRawResult`` с результатом выполнения.
        """

    @abstractmethod
    def clean_cache(self) -> None:
        """Очищает локальный кэш Conan."""
