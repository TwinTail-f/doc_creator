"""
Менеджер конфигураций с поддержкой форматов JSON и YAML.
"""

import json
from pathlib import Path
from typing import Any
from pydantic import ValidationError

import yaml

from autodoc.config.schemas import ConfluenceConfigSchema, ParserConfigSchema
from autodoc.exceptions import ConfigError
from autodoc.infrastructure.logger import logger


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

    def __init__(self, configs_dir: str) -> None:
        """
        Инициализирует менеджер конфигураций.

        Args:
            configs_dir: Абсолютный путь к папке ``configs/``.

        Raises:
            ConfigError: Если директория не существует.
        """
        self.configs_dir = Path(configs_dir)
        if not self.configs_dir.is_dir():
            raise ConfigError(f"Директория с конфигами не найдена: {configs_dir}")
        logger.info(f"Инициализирован: {configs_dir}")

    def load_parser_config(self, config_file: str | None = None) -> ParserConfigSchema:
        """
        Загружает и валидирует конфигурацию парсера.

        Если ``config_file`` не указан, автоматически ищет файл
        ``parser_config`` с одним из поддерживаемых расширений.

        Args:
            config_file: Имя файла конфига. Если ``None`` — определяется автоматически.

        Returns:
            Валидированная конфигурация парсера.

        Raises:
            ConfigError: Если файл не найден или схема не прошла валидацию.
        """
        filename = config_file or self._find_config_file("parser_config")
        raw = self._load_config(filename)
        try:
            validated = ParserConfigSchema(**raw)
            logger.info(f"{filename} успешно загружен и провалидирован")
            return validated
        except ValidationError as e:
            raise ConfigError(f"Ошибка валидации {filename}: {e}") from e

    def load_confluence_config(
        self, config_file: str | None = None
    ) -> ConfluenceConfigSchema:
        """
        Загружает и валидирует конфигурацию Confluence.

        Args:
            config_file: Имя файла конфига. Если ``None`` — определяется автоматически.

        Returns:
            Валидированная конфигурация Confluence.

        Raises:
            ConfigError: Если файл не найден или схема не прошла валидацию.
        """
        filename = config_file or self._find_config_file("confluence_config")
        raw = self._load_config(filename)
        try:
            validated = ConfluenceConfigSchema(**raw)
            logger.info(f"{filename} успешно загружен и провалидирован")
            return validated
        except ValidationError as e:
            raise ConfigError(f"Ошибка валидации {filename}: {e}") from e

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

        try:
            if path.suffix == ".json":
                with path.open("r", encoding="utf-8") as f:
                    json.load(f)
            elif path.suffix in (".yaml", ".yml"):
                with path.open("r", encoding="utf-8") as f:
                    yaml.safe_load(f)
            else:
                return False, f"Неподдерживаемый формат: {path.suffix}"
            return True, None
        except (json.JSONDecodeError, yaml.YAMLError, OSError) as e:
            return False, f"Ошибка валидации: {e}"

    def list_available_configs(self) -> dict[str, list[str]]:
        """
        Возвращает список конфигурационных файлов в директории.

        Returns:
            Словарь вида ``{"json": [...], "yaml": [...]}``.
        """
        configs: dict[str, list[str]] = {"json": [], "yaml": []}
        try:
            for entry in self.configs_dir.iterdir():
                if entry.suffix == ".json":
                    configs["json"].append(entry.name)
                elif entry.suffix in (".yaml", ".yml"):
                    configs["yaml"].append(entry.name)
        except OSError as e:
            logger.warning(f"Ошибка при чтении директории конфигов: {e}")
        return configs

    def _find_config_file(self, basename: str) -> str:
        """
        Ищет файл конфигурации по базовому имени (без расширения).

        Args:
            basename: Базовое имя файла (например ``"parser_config"``).

        Returns:
            Имя найденного файла (с расширением).

        Raises:
            ConfigError: Если файл не найден ни в одном поддерживаемом формате.
        """
        for ext in self.SUPPORTED_FORMATS:
            candidate = self.configs_dir / f"{basename}{ext}"
            if candidate.exists():
                return candidate.name

        available = [e.name for e in self.configs_dir.iterdir()]
        raise ConfigError(
            f'Конфиг "{basename}" не найден в {self.configs_dir}\n'
            f"Доступные файлы: {available}\n"
            f"Поддерживаемые форматы: {self.SUPPORTED_FORMATS}"
        )

    def _load_config(self, filename: str) -> dict[str, Any]:
        """
        Загружает конфигурационный файл по имени.

        Args:
            filename: Имя файла (с расширением).

        Returns:
            Загруженные данные в виде словаря.

        Raises:
            ConfigError: Если файл не найден, формат неподдерживаемый
                или содержимое невалидно.
        """
        filepath = self.configs_dir / filename
        if not filepath.exists():
            raise ConfigError(f"Конфиг-файл не найден: {filepath}")

        suffix = filepath.suffix.lower()
        try:
            if suffix == ".json":
                return self._load_json(filepath)
            elif suffix in (".yaml", ".yml"):
                return self._load_yaml(filepath)
            else:
                raise ConfigError(
                    f"Неподдерживаемый формат: {suffix}. "
                    f"Поддерживаемые: {self.SUPPORTED_FORMATS}"
                )
        except ConfigError:
            raise
        except ValidationError as e:
            raise ConfigError(f"Ошибка при загрузке {filename}: {e}") from e

    def _load_json(self, filepath: Path) -> dict[str, Any]:
        """
        Читает JSON-файл.

        Args:
            filepath: Путь к файлу.

        Returns:
            Содержимое файла в виде словаря.

        Raises:
            ConfigError: Если файл содержит невалидный JSON или недоступен.
        """
        try:
            with filepath.open("r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigError(f"Невалидный JSON в {filepath.name}: {e}") from e
        except OSError as e:
            raise ConfigError(f"Ошибка чтения {filepath.name}: {e}") from e

    def _load_yaml(self, filepath: Path) -> dict[str, Any]:
        """
        Читает YAML-файл.

        Args:
            filepath: Путь к файлу.

        Returns:
            Содержимое файла в виде словаря.

        Raises:
            ConfigError: Если файл содержит невалидный YAML или корневой
                элемент не является словарём.
        """
        try:
            with filepath.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                raise ConfigError(
                    f"YAML-файл {filepath.name} должен содержать объект (dict), "
                    f"получен {type(data).__name__}"
                )
            return data
        except yaml.YAMLError as e:
            raise ConfigError(f"Невалидный YAML в {filepath.name}: {e}") from e
        except OSError as e:
            raise ConfigError(f"Ошибка чтения {filepath.name}: {e}") from e
