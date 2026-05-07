"""
Управляет жизненным циклом конфигурационной директории Conan.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from autodoc.common.logger import logger


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
