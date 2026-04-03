"""
Запуск команд Conan CLI через subprocess.

Содержит интерфейс ``BaseConanRunner`` и реализацию ``Conan2Runner``.
Дата-класс результата вынесен в ``conan_result.py``.
"""
import json
import subprocess
from abc import ABC, abstractmethod

from autodoc.infrastructure.logger import logger
from autodoc.parser.conan.conan_result import ConanRawResult
from autodoc.parser.conan.task_builder import ConanTask


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


class Conan2Runner(BaseConanRunner):
    """
    Запускает команды Conan 2.x через ``subprocess``.

    Обрабатывает таймауты, ненулевые коды возврата и ошибки JSON-декодирования.
    Каждый вызов ``run()`` независим — безопасен для использования из нескольких потоков.
    """

    _CONAN_NOT_FOUND_MSG: str = "Утилита conan не найдена. Проверьте PATH."
    _CLEAN_CACHE_CMD: list[str] = ["conan", "remove", "*", "-c"]
    _CLEAN_CACHE_TIMEOUT: int = 60

    def __init__(self, timeout: int) -> None:
        """
        Args:
            timeout: Таймаут выполнения одной команды ``conan graph info`` в секундах.
        """
        self._timeout = timeout

    def run(self, task: ConanTask) -> ConanRawResult:
        """
        Выполняет ``conan graph info`` и возвращает сырой результат.

        При таймауте или отсутствии утилиты возвращает ``success=False``
        с описанием ошибки — не бросает исключений.

        Args:
            task: Задача с готовой CLI-командой.

        Returns:
            ``ConanRawResult`` с данными или описанием ошибки.
        """
        try:
            result = subprocess.run(
                task.cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
        except subprocess.TimeoutExpired:
            return ConanRawResult(
                task=task,
                success=False,
                data=None,
                error="Таймаут выполнения команды (%d с)." % self._timeout,
            )
        except FileNotFoundError:
            return ConanRawResult(
                task=task,
                success=False,
                data=None,
                error=self._CONAN_NOT_FOUND_MSG,
            )

        if result.returncode != 0:
            return ConanRawResult(
                task=task,
                success=False,
                data=None,
                error=self._extract_error_message(result.stderr),
            )

        try:
            parsed = json.loads(result.stdout)
            return ConanRawResult(task=task, success=True, data=parsed, error="")
        except json.JSONDecodeError as e:
            return ConanRawResult(
                task=task,
                success=False,
                data=None,
                error="JSON decode error: %s. STDOUT: %s" % (e, result.stdout[:300]),
            )

    def clean_cache(self) -> None:
        """
        Очищает локальный кэш пакетов Conan 2.

        Raises:
            RuntimeError: Если утилита ``conan`` не найдена в PATH.
        """
        logger.info("Conan2Runner: очищаем локальный кэш Conan 2…")
        try:
            result = subprocess.run(
                self._CLEAN_CACHE_CMD,
                capture_output=True,
                text=True,
                timeout=self._CLEAN_CACHE_TIMEOUT,
            )
            if result.returncode == 0:
                logger.info("Conan2Runner: кэш Conan 2 очищен.")
            else:
                logger.debug(
                    "Conan2Runner: кэш пуст или некритичная ошибка: %s", result.stderr.strip()
                )
        except subprocess.TimeoutExpired:
            logger.warning("Conan2Runner: таймаут при очистке кэша.")
        except FileNotFoundError:
            raise RuntimeError(self._CONAN_NOT_FOUND_MSG)

    @staticmethod
    def _extract_error_message(stderr: str) -> str:
        """
        Извлекает релевантное сообщение из stderr Conan.

        Ищет первое вхождение ``ERROR:`` или ``Error:`` и возвращает
        текст начиная с найденной метки. Если маркеры не найдены —
        возвращает весь stderr без пробелов по краям.

        Args:
            stderr: Полный stderr процесса.

        Returns:
            Укороченное сообщение об ошибке.
        """
        for prefix in ("ERROR:", "Error:"):
            idx = stderr.find(prefix)
            if idx != -1:
                return stderr[idx:]
        return stderr.strip()
