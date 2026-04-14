"""
Запуск команд Conan CLI через subprocess.

Содержит интерфейс ``BaseConanRunner`` и реализацию ``Conan2Runner``.
Дата-класс результата вынесен в ``conan_result.py``.
"""

import json
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod

from autodoc.infrastructure.logger import logger
from autodoc.models.conan_result import ConanRawResult
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

    Обрабатывает таймауты и ненулевые коды возврата.
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

    @staticmethod
    def _real_conan_home() -> Path:
        """Возвращает путь к реальному CONAN_HOME (из env или ~/.conan2)."""
        return Path(os.environ.get("CONAN_HOME", Path.home() / ".conan2"))

    @staticmethod
    def _setup_isolated_conan_home(src_home: Path, dst_home: Path) -> None:
        """
        Копирует папку ``.conan2`` из реального CONAN_HOME в изолированный.

        Без этого Conan не находит ни пользовательские профили (-pr=...),
        ни дефолтный профиль, и завершается с ошибкой.
        """
        shutil.copytree(src_home, dst_home, dirs_exist_ok=True)

    def run(self, task: ConanTask) -> ConanRawResult:
        """
        Выполняет ``conan graph info`` и возвращает сырой результат.

        Проверяет наличие ``conan`` в PATH до запуска subprocess.
        Для каждого вызова создаётся изолированный временный ``CONAN_HOME``
        с скопированными профилями из реального окружения пользователя.
        Это устраняет race condition в кэше Conan 2.x при параллельных вызовах.

        При таймауте или отсутствии утилиты возвращает ``success=False``
        с описанием ошибки — не бросает исключений.

        Args:
            task: Задача с готовой CLI-командой.

        Returns:
            ``ConanRawResult`` с данными или описанием ошибки.
        """
        if not shutil.which("conan"):
            return ConanRawResult(
                task=task,
                success=False,
                data=None,
                error=self._CONAN_NOT_FOUND_MSG,
            )

        with tempfile.TemporaryDirectory(prefix="conan_home_") as tmp_home:
            self._setup_isolated_conan_home(self._real_conan_home(), Path(tmp_home))
            env = {**os.environ, "CONAN_HOME": tmp_home}
            try:
                result = subprocess.run(
                    task.cmd,
                    capture_output=True,
                    text=True,
                    timeout=self._timeout,
                    env=env,
                )
            except subprocess.TimeoutExpired:
                return ConanRawResult(
                    task=task,
                    success=False,
                    data=None,
                    error=f"Таймаут выполнения команды ({self._timeout} с).",
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
                    error=f"JSON decode error: {e}. STDOUT: {result.stdout[:300]}",
                )

    def clean_cache(self) -> None:
        """
        Очищает локальный кэш пакетов Conan 2.

        Raises:
            RuntimeError: Если утилита ``conan`` не найдена в PATH.
        """
        if not shutil.which("conan"):
            raise RuntimeError(self._CONAN_NOT_FOUND_MSG)

        logger.info("Очищаем локальный кэш Conan 2…")
        try:
            result = subprocess.run(
                self._CLEAN_CACHE_CMD,
                capture_output=True,
                text=True,
                timeout=self._CLEAN_CACHE_TIMEOUT,
            )
            if result.returncode == 0:
                logger.info("Кэш Conan 2 очищен.")
            else:
                logger.debug(
                    f"кэш пуст или некритичная ошибка: {result.stderr.strip()}"
                )
        except subprocess.TimeoutExpired:
            logger.warning("Таймаут при очистке кэша.")

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
