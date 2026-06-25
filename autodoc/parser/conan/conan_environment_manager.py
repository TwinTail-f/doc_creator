"""
Управляет жизненным циклом конфигурационной директории Conan.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from autodoc.common.logger import logger


class ConanEnvironmentManager:
    """
    Управляет жизненным циклом конфигурационной директории Conan.

    Выполняет однократную установку конфигурации из Artifactory (``conan config install``)
    и авторизацию во всех remote-репозиториях из установленной конфигурации.
    Созданная директория используется как шаблон для изолированных временных копий
    в ``Conan2Runner.run()``.
    """

    _CONFIG_INSTALL_TIMEOUT: int = 120
    _LOGIN_TIMEOUT: int = 30

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
        Устанавливает конфигурацию Conan и выполняет вход во все remotes.

        Создаёт изолированную временную директорию, устанавливает в неё конфигурацию
        Conan из Artifactory и авторизуется в каждом remote из установленной конфигурации.

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

        for remote in self._get_remote_names(env):
            self._login_remote(remote, env)

        return self._setup_dir

    def _get_remote_names(self, env: dict[str, str]) -> list[str]:
        """
        Возвращает список имён всех Conan remotes из установленной конфигурации.

        Args:
            env: Переменные окружения с установленным ``CONAN_HOME``.

        Returns:
            Список имён remote-репозиториев.

        Raises:
            RuntimeError: Если команда ``conan remote list`` завершилась с ошибкой.
        """
        result = subprocess.run(
            ["conan", "remote", "list", "--format=json"],
            capture_output=True,
            text=True,
            timeout=self._LOGIN_TIMEOUT,
            env=env,
        )
        if result.returncode != 0:
            # Conan иногда пишет детали ошибки в stdout вместо stderr.
            error = result.stderr.strip() or result.stdout.strip()
            self.cleanup()
            raise RuntimeError(
                f"conan remote list завершился с ошибкой (код {result.returncode}): {error}"
            )

        remotes = json.loads(result.stdout)
        names = [r["name"] for r in remotes]
        logger.info(f"Найдены Conan remotes: {names}")
        return names

    def _login_remote(self, remote_name: str, env: dict[str, str]) -> None:
        """
        Авторизуется в одном Conan remote через ``conan remote login``.

        Args:
            remote_name: Имя remote-репозитория Conan.
            env: Переменные окружения с установленным ``CONAN_HOME``.

        Raises:
            RuntimeError: Если команда ``conan remote login`` завершилась с ошибкой.
        """
        logger.info(f'Авторизуемся в Conan remote "{remote_name}" …')
        result = subprocess.run(
            [
                "conan",
                "remote",
                "login",
                "--password",
                self._password,
                remote_name,
                self._username,
            ],
            capture_output=True,
            text=True,
            timeout=self._LOGIN_TIMEOUT,
            env=env,
        )
        if result.returncode != 0:
            # Conan иногда пишет детали ошибки в stdout вместо stderr.
            error = result.stderr.strip() or result.stdout.strip()
            self.cleanup()
            raise RuntimeError(
                f'conan remote login в "{remote_name}" завершился с ошибкой '
                f"(код {result.returncode}): {error}"
            )
        logger.info(f'Авторизация в "{remote_name}" прошла успешно.')

    def _install_config(self, env: dict[str, str]) -> None:
        """
        Устанавливает конфигурацию Conan из Artifactory через ``conan config install``.

        Args:
            env: Переменные окружения с установленным ``CONAN_HOME``.

        Raises:
            RuntimeError: Если ``config_url`` некорректен или команда завершилась с ошибкой.
        """
        # Встраиваем credentials в URL: https://user:token@host/...
        split = urlsplit(self._config_url)
        if not split.scheme or not split.netloc:
            raise RuntimeError(f"Некорректный config_url: {self._config_url}")
        netloc_with_creds = f"{self._username}:{self._password}@{split.netloc}"
        # SplitResult — это NamedTuple, и _replace() — его официальный публичный
        # метод "вернуть копию с заменёнными полями" (наследуется от namedtuple).
        # Префикс "_" здесь — не маркер приватности, а соглашение namedtuple,
        # чтобы не пересекаться с именами полей самого тапла (netloc, scheme и т.д.).
        url_with_creds = urlunsplit(split._replace(netloc=netloc_with_creds))

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
