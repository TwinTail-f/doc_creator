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
    Управляет жизненным циклом конфигурационной директории Conan.

    Выполняет однократную установку конфигурации из Artifactory (``conan config install``)
    и авторизацию в удалённом репозитории (``conan remote login``). Созданная директория
    используется как шаблон для изолированных временных копий в ``Conan2Runner.run()``.

    Attributes:
        _config_url: URL zip-архива конфигурации Conan.
        _username: Логин пользователя Artifactory.
        _password: PAT-токен Artifactory.
        _setup_dir: Путь к созданной директории-шаблону; ``None`` до ``setup()``.
    """

    _CONFIG_INSTALL_TIMEOUT: int = 120
    _LOGIN_TIMEOUT: int = 30
    _CONAN_REMOTE_NAME: str = "components-conan2"

    def __init__(
        self,
        config_url: str,
        username: str,
        password: str,
    ) -> None:
        """
        Args:
            config_url: URL zip-архива конфигурации Conan (без credentials).
            username: Логин пользователя Artifactory / TFS.
            password: PAT-токен Artifactory.
        """
        self._config_url = config_url
        self._username = username
        self._password = password
        self._setup_dir: Path | None = None

    def setup(self) -> Path:
        """
        Устанавливает конфигурацию Conan и выполняет вход в remote.

        Создаёт изолированную временную директорию, устанавливает в неё конфигурацию
        Conan из Artifactory и авторизуется в remote репозитории.

        Returns:
            Путь к директории-шаблону с установленной конфигурацией Conan.

        Raises:
            RuntimeError: Если утилита ``conan`` не найдена в PATH или любой
                          из подпроцессов завершился с ненулевым кодом возврата.
        """
        if not shutil.which("conan"):
            raise RuntimeError("Утилита conan не найдена в PATH.")

        self._setup_dir = Path(tempfile.mkdtemp(prefix="conan_setup_"))
        env = {**os.environ, "CONAN_HOME": str(self._setup_dir)}

        self._install_config(env)
        self._login_remote(env)

        return self._setup_dir

    def _login_remote(self, env: dict[str, str]) -> None:
        """Авторизуется в Conan remote через ``conan remote login``."""
        logger.info(f"Авторизуемся в Conan remote '{self._CONAN_REMOTE_NAME}' …")
        result = subprocess.run(
            [
                "conan",
                "remote",
                "login",
                "--password",
                self._password,
                self._CONAN_REMOTE_NAME,
                self._username,
            ],
            capture_output=True,
            text=True,
            timeout=self._LOGIN_TIMEOUT,
            env=env,
        )
        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip()
            self.cleanup()
            raise RuntimeError(
                f"conan remote login завершился с ошибкой (код {result.returncode}): {error}"
            )
        logger.info(f"Авторизация в '{self._CONAN_REMOTE_NAME}' прошла успешно.")

    def _install_config(self, env: dict[str, str]) -> None:
        """Устанавливает конфигурацию Conan из Artifactory через ``conan config install``."""
        # Встраиваем credentials в URL: https://user:token@host/...
        parsed = self._config_url.split("://", 1)
        if len(parsed) != 2:
            raise RuntimeError(f"Некорректный config_url: {self._config_url}")
        scheme, rest = parsed
        url_with_creds = f"{scheme}://{self._username}:{self._password}@{rest}"

        logger.info(
            f"Устанавливаем конфигурацию Conan из {self._config_url} в {self._setup_dir} …"
        )
        result = subprocess.run(
            ["conan", "config", "install", url_with_creds],
            capture_output=True,
            text=True,
            timeout=self._CONFIG_INSTALL_TIMEOUT,
            env=env,
        )
        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip()
            self.cleanup()
            raise RuntimeError(
                f"conan config install завершился с ошибкой (код {result.returncode}): {error}"
            )
        logger.info("Конфигурация Conan установлена успешно.")

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
