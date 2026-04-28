"""
Менеджер конфигураций с поддержкой форматов JSON и YAML.
"""

import json
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import ValidationError

from autodoc.config.schemas import ConfluenceConfigSchema, ParserConfigSchema
from autodoc.exceptions import ConfigError
from autodoc.infrastructure.logger import logger

_TConfig = TypeVar("_TConfig")


class ConfigManager:
    """
    Менеджер для загрузки и валидации конфигурационных файлов.

    Поддерживает форматы JSON и YAML. При явно переданном имени файла
    ищет именно его; если имя не указано — перебирает поддерживаемые
    расширения в порядке ``SUPPORTED_FORMATS``.

    Attributes:
        configs_dir: Путь к директории с конфигурационными файлами.
    """

    SUPPORTED_FORMATS: list[str] = [".json", ".yaml", ".yml"]

    def __init__(self, configs_dir: str | Path) -> None:
        """
        Инициализирует менеджер конфигураций.

        Args:
            configs_dir: Абсолютный путь к папке ``configs/``.
        """
        self.configs_dir = Path(configs_dir)
        if not self.configs_dir.is_dir():
            logger.error(
                f"Директория с конфигами не найдена или не является директорией: {configs_dir}"
            )
        else:
            logger.info(f"Инициализирован: {configs_dir}")

    def load_parser_config(
        self, config_file: str | None = None
    ) -> ParserConfigSchema | None:
        """
        Загружает и валидирует конфигурацию парсера.

        Если ``config_file`` не указан, автоматически ищет файл
        ``parser_config`` с одним из поддерживаемых расширений.

        Args:
            config_file: Имя файла конфига. Если ``None`` — определяется автоматически.

        Returns:
            Валидированная конфигурация парсера или ``None`` при любой ошибке.
        """
        return self._load_validated("parser_config", ParserConfigSchema, config_file)

    def load_confluence_config(
        self, config_file: str | None = None
    ) -> ConfluenceConfigSchema | None:
        """
        Загружает и валидирует конфигурацию Confluence.

        Args:
            config_file: Имя файла конфига. Если ``None`` — определяется автоматически.

        Returns:
            Валидированная конфигурация Confluence или ``None`` при любой ошибке.
        """
        return self._load_validated(
            "confluence_config", ConfluenceConfigSchema, config_file
        )

    def load_raw(self, filename: str) -> dict[str, Any]:
        """
        Загружает конфиг-файл без схемной валидации.

        Args:
            filename: Имя файла (с расширением).

        Returns:
            Загруженные данные в виде словаря.

        Raises:
            ConfigError: Если директория недоступна или файл не удалось загрузить.
        """
        if not self.configs_dir.is_dir():
            raise ConfigError(
                f"Директория с конфигами не найдена или не является директорией: {self.configs_dir}"
            )
        result = self._load_config(filename)
        if result is None:
            raise ConfigError(f"Не удалось загрузить файл конфигурации: {filename}")
        return result

    def validate_config_file(self, filepath: str) -> tuple[bool, str | None]:
        """
        Проверяет синтаксическую корректность файла конфигурации.

        Args:
            filepath: Абсолютный путь к файлу.

        Returns:
            Кортеж ``(valid, error_message)`` — при успехе ``(True, None)``.
        """
        path = Path(filepath)
        if not path.exists():
            return False, f"Файл не найден: {filepath}"

        suffix = path.suffix.lower()
        if suffix not in self.SUPPORTED_FORMATS:
            return False, (
                f"Неподдерживаемый формат: {suffix}. "
                f"Поддерживаемые: {self.SUPPORTED_FORMATS}"
            )

        try:
            self._parse_file(path)
            return True, None
        except ConfigError as e:
            return False, str(e)

    def _load_validated(
        self,
        basename: str,
        schema_cls: type[_TConfig],
        config_file: str | None,
    ) -> _TConfig | None:
        """
        Общая логика загрузки и схемной валидации конфига.

        Args:
            basename: Базовое имя файла для автопоиска (без расширения).
            schema_cls: Pydantic-схема для валидации.
            config_file: Явное имя файла или ``None`` для автопоиска.

        Returns:
            Провалидированная схема или ``None`` при любой ошибке.
        """
        if not self.configs_dir.is_dir():
            logger.error(
                f"Директория с конфигами не найдена или не является директорией: {self.configs_dir}"
            )
            return None

        filename = config_file or self._find_config_file(basename)
        if filename is None:
            return None

        raw = self._load_config(filename)
        if raw is None:
            return None

        try:
            validated = schema_cls(**raw)
            logger.info(f"{filename} успешно загружен и провалидирован")
            return validated
        except ValidationError as e:
            logger.error(f"Ошибка валидации {filename}: {e}")
            return None

    def _find_config_file(self, basename: str) -> str | None:
        """
        Ищет файл конфигурации по базовому имени (без расширения).

        Args:
            basename: Базовое имя файла (например ``"parser_config"``).

        Returns:
            Имя найденного файла (с расширением) или ``None``, если файл не найден.
        """
        for ext in self.SUPPORTED_FORMATS:
            candidate = self.configs_dir / f"{basename}{ext}"
            if candidate.exists():
                return candidate.name

        available = [
            item.name for item in self.configs_dir.iterdir() if not item.is_dir()
        ]
        logger.error(
            f'Конфиг "{basename}" не найден в {self.configs_dir}. '
            f"Доступные файлы: {available}. "
            f"Поддерживаемые форматы: {self.SUPPORTED_FORMATS}"
        )
        return None

    def _load_config(self, filename: str) -> dict[str, Any] | None:
        """
        Загружает конфигурационный файл по имени из ``configs_dir``.

        Args:
            filename: Имя файла (с расширением).

        Returns:
            Загруженные данные в виде словаря или ``None`` при ошибке.
        """
        filepath = self.configs_dir / filename

        if not filepath.exists():
            logger.error(f"Конфиг-файл не найден: {filepath}")
            return None

        if filepath.suffix.lower() not in self.SUPPORTED_FORMATS:
            logger.error(
                f"Неподдерживаемый формат: {filepath.suffix}. "
                f"Поддерживаемые: {self.SUPPORTED_FORMATS}"
            )
            return None

        try:
            return self._parse_file(filepath)
        except ConfigError as e:
            logger.error(str(e))
            return None

    def _parse_file(self, filepath: Path) -> dict[str, Any]:
        """
        Открывает и парсит файл конфигурации.

        Единственное место, где происходит реальное чтение диска.
        Все ошибки (I/O, парсинг формата, неверная структура) преобразуются
        в ``ConfigError`` — вызывающим методам не нужно знать о деталях.

        Args:
            filepath: Путь к файлу.

        Returns:
            Содержимое файла в виде словаря.

        Raises:
            ConfigError: При любой ошибке — файл не является файлом,
                         ошибка чтения, невалидный JSON/YAML или не dict.
        """
        if not filepath.is_file():
            raise ConfigError(f"Путь не указывает на файл: {filepath.name}")

        try:
            with filepath.open("r", encoding="utf-8") as f:
                if filepath.suffix.lower() == ".json":
                    data = json.load(f)
                else:  # .yaml / .yml
                    data = yaml.safe_load(f)
        except json.JSONDecodeError as e:
            raise ConfigError(f"Некорректный JSON в {filepath.name}: {e}") from e
        except yaml.YAMLError as e:
            raise ConfigError(f"Некорректный YAML в {filepath.name}: {e}") from e
        except OSError as e:
            raise ConfigError(f"Ошибка чтения {filepath.name}: {e}") from e

        if not isinstance(data, dict):
            raise ConfigError(
                f"Файл {filepath.name} должен содержать объект (dict), "
                f"получен {type(data).__name__}"
            )
        return data
