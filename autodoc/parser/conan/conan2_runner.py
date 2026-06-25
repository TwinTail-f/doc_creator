"""
Реализация Conan2Runner — запуск команд Conan 2.x через subprocess.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from autodoc.common.logger import logger
from autodoc.parser.conan.models.conan_raw_result import ConanRawResult
from autodoc.parser.conan.base_conan_runner import BaseConanRunner
from autodoc.parser.conan.models.conan_task import ConanTask


class Conan2Runner(BaseConanRunner):
    """
    Выполняет команды Conan 2.x, изолируя каждый вызов в собственный временный ``CONAN_HOME``.

    Каждый вызов ``run()`` копирует ``conan_home_template`` в свою изолированную
    временную директорию — безопасен для использования из нескольких потоков.

    ``conan_home_template`` должен быть подготовлен заранее через
    ``ConanEnvironmentManager.setup()`` и передан при создании экземпляра.
    """

    _CONAN_NOT_FOUND_MSG: str = "Утилита conan не найдена. Проверьте PATH."
    _CLEAN_CACHE_CMD: list[str] = ["conan", "remove", "*", "-c"]
    _CLEAN_CACHE_TIMEOUT: int = 60
    _STDOUT_PREVIEW_LENGTH: int = 300

    def __init__(self, timeout: int, conan_home_template: Path) -> None:
        """
        Args:
            timeout: Таймаут выполнения одной команды ``conan graph info`` в секундах.
            conan_home_template: Путь к директории-шаблону с установленной конфигурацией
                Conan (профили, ``global.conf``, ``remotes.json``, ``settings.yml``).
                Создаётся и управляется ``ConanEnvironmentManager``.
        """
        self._timeout = timeout
        self._conan_home_template = conan_home_template

    def run(self, task: ConanTask) -> ConanRawResult:
        """
        Выполняет ``conan graph info`` и возвращает сырой результат.

        Проверяет наличие ``conan`` в PATH до запуска subprocess.
        Для каждого вызова создаётся изолированный временный ``CONAN_HOME``
        путём копирования директории-шаблона (``conan_home_template``).
        Это устраняет race condition в кэше Conan 2.x при параллельных вызовах.
        Временная директория удаляется автоматически после завершения вызова.

        При таймауте или отсутствии утилиты возвращает ``success=False``
        с описанием ошибки — не бросает исключений.

        Args:
            task: Задача с готовой CLI-командой.

        Returns:
            ``ConanRawResult`` с данными или описанием ошибки.
        """
        if not shutil.which("conan"):
            return ConanRawResult(
                success=False,
                data=None,
                error=self._CONAN_NOT_FOUND_MSG,
            )

        with tempfile.TemporaryDirectory(prefix="conan_run_") as tmp_run:
            tmp_run_path = Path(tmp_run)
            shutil.copytree(
                self._conan_home_template,
                tmp_run_path,
                dirs_exist_ok=True,
            )
            env = {**os.environ, "CONAN_HOME": tmp_run}

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
                    success=False,
                    data=None,
                    error=f"Таймаут выполнения команды ({self._timeout} с).",
                )

            if result.returncode != 0:
                return ConanRawResult(
                    success=False,
                    data=None,
                    error=self._extract_error_message(result.stderr),
                )

            try:
                parsed = json.loads(result.stdout)
                return ConanRawResult(success=True, data=parsed, error="")
            except json.JSONDecodeError as e:
                return ConanRawResult(
                    success=False,
                    data=None,
                    error=(
                        f"Ошибка декодирования JSON: {e}. "
                        f"STDOUT (первые {self._STDOUT_PREVIEW_LENGTH} символов): "
                        f"{result.stdout[:self._STDOUT_PREVIEW_LENGTH]}"
                    ),
                )

    def clean_cache(self) -> None:
        """
        Очищает локальный кэш пакетов Conan 2 в директории-шаблоне.

        Raises:
            RuntimeError: Если утилита ``conan`` не найдена в PATH.
        """
        if not shutil.which("conan"):
            raise RuntimeError(self._CONAN_NOT_FOUND_MSG)

        logger.info("Очищаем локальный кэш Conan 2…")
        env = {**os.environ, "CONAN_HOME": str(self._conan_home_template)}
        try:
            result = subprocess.run(
                self._CLEAN_CACHE_CMD,
                capture_output=True,
                text=True,
                timeout=self._CLEAN_CACHE_TIMEOUT,
                env=env,
            )
            if result.returncode == 0:
                logger.info("Кэш Conan 2 очищен.")
            else:
                logger.debug(
                    f"кэш пуст или некритичная ошибка: {result.stderr.strip()}"
                )
        except subprocess.TimeoutExpired:
            logger.warning("Таймаут при очистке кэша.")

    def _extract_error_message(self, stderr: str) -> str:
        """
        Извлекает релевантное сообщение из stderr Conan.

        Args:
            stderr: Полный stderr процесса.

        Returns:
            Сообщение об ошибке, начинающееся с маркера, или весь stderr.
        """
        # Conan обычно предваряет сообщение об ошибке длинной INFO-преамбулой;
        # обрезаем до первого вхождения "error:" для более чистого сообщения.
        idx = stderr.lower().find("error:")
        if idx != -1:
            return stderr[idx:]
        return stderr.strip()
