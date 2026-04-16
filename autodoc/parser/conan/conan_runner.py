"""
Запуск команд Conan CLI через subprocess.

Содержит интерфейс ``BaseConanRunner`` и реализацию ``Conan2Runner``.
Дата-класс результата вынесен в ``conan_result.py``.
"""

import json
import os
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

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


class ConanEnvironmentManager:
    """
    Управляет жизненным циклом изолированного окружения Conan.

    Создаёт одну разделяемую директорию-шаблон (``_setup_dir``), в которую
    единожды устанавливается конфигурация через ``conan config install``.
    Каждый вызов ``Conan2Runner.run()`` копирует шаблон в свою временную
    директорию — это исключает race condition при параллельных вызовах.

    После завершения работы ``cleanup()`` удаляет директорию-шаблон.
    Временные директории отдельных вызовов удаляются самими вызовами через
    ``tempfile.TemporaryDirectory``.

    Типичное использование::

        manager = ConanEnvironmentManager(config_url="https://...")
        try:
            setup_dir = manager.setup()
            runner = Conan2Runner(timeout=120, conan_home_template=setup_dir)
            # ... запуск задач ...
        finally:
            manager.cleanup()
    """

    _CONFIG_INSTALL_TIMEOUT: int = 120

    def __init__(self, config_url: str) -> None:
        """
        Args:
            config_url: URL zip-архива конфигурации Conan в Artifactory.
                Например:
                ``https://artifactory.company.ru/artifactory/components-conan2/
                platform_config2/1.0.1.2/conan_config.zip``
        """
        self._config_url = config_url
        self._setup_dir: Path | None = None

    def setup(self) -> Path:
        """
        Создаёт временную директорию и устанавливает в неё конфигурацию Conan.

        Выполняет ``conan config install <config_url>`` с ``CONAN_HOME``
        указывающим на свежую временную директорию. По итогу там появляются:
        папка ``profiles/``, файлы ``global.conf``, ``remotes.json``,
        ``settings.yml``.

        Returns:
            Путь к директории-шаблону с установленной конфигурацией.

        Raises:
            RuntimeError: Если ``conan`` не найден в PATH или установка завершилась
                с ненулевым кодом возврата.
        """
        if not shutil.which("conan"):
            raise RuntimeError("Утилита conan не найдена в PATH.")

        self._setup_dir = Path(tempfile.mkdtemp(prefix="conan_setup_"))
        logger.info(
            f"Устанавливаем конфигурацию Conan из {self._config_url!r} "
            f"в {self._setup_dir} …"
        )

        env = {**os.environ, "CONAN_HOME": str(self._setup_dir)}
        try:
            result = subprocess.run(
                ["conan", "config", "install", self._config_url],
                capture_output=True,
                text=True,
                timeout=self._CONFIG_INSTALL_TIMEOUT,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            self.cleanup()
            raise RuntimeError(
                f"Таймаут при установке конфигурации Conan ({self._CONFIG_INSTALL_TIMEOUT} с)."
            ) from exc

        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip()
            self.cleanup()
            raise RuntimeError(
                f"conan config install завершился с ошибкой (код {result.returncode}): {error}"
            )

        logger.info("Конфигурация Conan установлена успешно.")
        return self._setup_dir

    def cleanup(self) -> None:
        """
        Удаляет директорию-шаблон с конфигурацией Conan.

        Безопасно вызывать повторно и при ``setup()`` не вызывавшемся.
        """
        if self._setup_dir and self._setup_dir.exists():
            shutil.rmtree(self._setup_dir, ignore_errors=True)
            logger.debug(f"Удалена директория конфигурации Conan: {self._setup_dir}")
            self._setup_dir = None


class Conan2Runner(BaseConanRunner):
    """
    Запускает команды Conan 2.x через ``subprocess``.

    Обрабатывает таймауты и ненулевые коды возврата.
    Каждый вызов ``run()`` копирует ``conan_home_template`` в свою изолированную
    временную директорию — безопасен для использования из нескольких потоков.

    ``conan_home_template`` должен быть подготовлен заранее через
    ``ConanEnvironmentManager.setup()`` и передан при создании экземпляра.
    """

    _CONAN_NOT_FOUND_MSG: str = "Утилита conan не найдена. Проверьте PATH."
    _CLEAN_CACHE_CMD: list[str] = ["conan", "remove", "*", "-c"]
    _CLEAN_CACHE_TIMEOUT: int = 60

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
                task=task,
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
