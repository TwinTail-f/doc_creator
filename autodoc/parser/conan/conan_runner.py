"""
Запуск команд Conan CLI через subprocess.
"""
import json
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from autodoc.infrastructure.logger import logger
from autodoc.parser.conan.task_builder import ConanTask


@dataclass
class ConanRawResult:
    """
    Сырой результат выполнения одной команды ``conan graph info``.

    Содержит либо распарсенный JSON (при успехе), либо текст ошибки.
    """

    task: ConanTask
    success: bool
    data: Optional[Dict[str, Any]]  # разобранный JSON, если success=True
    error: str                       # текст ошибки, если success=False


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
    """

    _CONAN_NOT_FOUND_MSG = 'Утилита conan не найдена. Проверьте PATH.'
    _CLEAN_CACHE_CMD = ['conan', 'remove', '*', '-c']
    _CLEAN_CACHE_TIMEOUT = 60

    def __init__(self, timeout: int) -> None:
        """
        Args:
            timeout: Таймаут выполнения команды в секундах.
        """
        self._timeout = timeout

    def run(self, task: ConanTask) -> ConanRawResult:
        """
        Выполняет ``conan graph info`` и возвращает сырой результат.

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
                error=f'Таймаут выполнения команды ({self._timeout} с).',
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
            return ConanRawResult(task=task, success=True, data=parsed, error='')
        except json.JSONDecodeError as e:
            return ConanRawResult(
                task=task,
                success=False,
                data=None,
                error=f'JSON decode error: {e}. STDOUT: {result.stdout[:300]}',
            )

    def clean_cache(self) -> None:
        """
        Очищает локальный кэш пакетов Conan 2.

        Raises:
            RuntimeError: Если утилита ``conan`` не найдена в PATH.
        """
        logger.info('Conan2Runner: очищаем локальный кэш Conan 2…')
        try:
            result = subprocess.run(
                self._CLEAN_CACHE_CMD,
                capture_output=True,
                text=True,
                timeout=self._CLEAN_CACHE_TIMEOUT,
            )
            if result.returncode == 0:
                logger.info('Conan2Runner: кэш Conan 2 очищен.')
            else:
                logger.debug(
                    f'Conan2Runner: кэш пуст или некритичная ошибка: '
                    f'{result.stderr.strip()}'
                )
        except subprocess.TimeoutExpired:
            logger.warning('Conan2Runner: таймаут при очистке кэша.')
        except FileNotFoundError:
            raise RuntimeError(self._CONAN_NOT_FOUND_MSG)

    @staticmethod
    def _extract_error_message(stderr: str) -> str:
        """
        Извлекает релевантное сообщение из stderr Conan.

        Ищет первое вхождение ``ERROR:`` или ``Error:`` и возвращает
        текст начиная с найденной метки.

        Args:
            stderr: Полный stderr процесса.

        Returns:
            Укороченное сообщение об ошибке.
        """
        for prefix in ('ERROR:', 'Error:'):
            idx = stderr.find(prefix)
            if idx != -1:
                return stderr[idx:]
        return stderr.strip()
