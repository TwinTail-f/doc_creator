"""
Менеджер конфигураций с поддержкой форматов JSON и YAML.
"""

import json
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import ValidationError

from autodoc.common.logger import logger
from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.exceptions import ConfigError

_TConfig = TypeVar("_TConfig")


class ConfigManager:
    """
    Менеджер для загрузки и валидации конфигурационных файлов.

    Поддерживает форматы JSON и YAML. Если имя файла передано без расширения,
    автоматически ищет подходящий файл в ``SUPPORTED_FORMATS``.

    Attributes:
        configs_dir: Путь к директории с конфигурационными файлами.
    """

    SUPPORTED_FORMATS: list[str] = [".yaml", ".yml", ".json"]

    # Нормализация расширений для группировки: .yml и .yaml — один формат.
    _EXT_TO_KEY: dict[str, str] = {".yaml": "yaml", ".yml": "yaml", ".json": "json"}

    EXAMPLES_SUBDIR: str = "examples"

    def __init__(self, configs_dir: str | Path) -> None:
        """
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

    def load_parser_config(self, config_file: str | None = None) -> ParserConfigSchema | None:
        """
        Загружает и валидирует конфигурацию парсера.

        Args:
            config_file: Имя файла. Если ``None`` — определяется автоматически.

        Returns:
            Валидированная конфигурация или ``None`` при любой ошибке.
        """
        try:
            filepath = self._resolve_path(config_file or "parser_config")
            raw = self._parse_file(filepath)
            result = self._validate(raw, ParserConfigSchema, filepath.name)
            logger.info(f"{filepath.name} успешно загружен и провалидирован")
            return result
        except ConfigError as e:
            logger.error(str(e))
            return None

    def load_confluence_config(
        self, config_file: str | None = None
    ) -> ConfluenceConfigSchema | None:
        """
        Загружает и валидирует конфигурацию Confluence.

        Args:
            config_file: Имя файла. Если ``None`` — определяется автоматически.

        Returns:
            Валидированная конфигурация или ``None`` при любой ошибке.
        """
        try:
            filepath = self._resolve_path(config_file or "confluence_config")
            raw = self._parse_file(filepath)
            result = self._validate(raw, ConfluenceConfigSchema, filepath.name)
            logger.info(f"{filepath.name} успешно загружен и провалидирован")
            return result
        except ConfigError as e:
            logger.error(str(e))
            return None

    def list_available_configs(self) -> dict[str, list[str]]:
        """
        Возвращает доступные конфиг-файлы из ``configs_dir``, сгруппированные по формату.

        Файлы из подпапки ``examples/`` не включаются в результат.

        Returns:
            Словарь, отображающий расширение формата (без ведущей точки) на
            отсортированный список имён файлов этого формата в ``configs_dir``.
        """
        result: dict[str, list[str]] = {key: [] for key in dict.fromkeys(self._EXT_TO_KEY.values())}
        if not self.configs_dir.is_dir():
            return result
        examples_path = self.configs_dir / self.EXAMPLES_SUBDIR
        for item in self.configs_dir.iterdir():
            if item == examples_path:  # пропускаем examples/
                continue
            if item.is_file() and item.suffix.lower() in self.SUPPORTED_FORMATS:
                result[self._EXT_TO_KEY[item.suffix.lower()]].append(item.name)
        return result

    def list_example_configs(self) -> dict[str, list[str]]:
        """
        Возвращает файлы-примеры из ``configs/examples/``, сгруппированные по формату.

        Returns:
            Словарь расширение → список имён файлов в ``configs_dir/examples/``.
            Если подпапка отсутствует — все списки пустые.
        """
        result: dict[str, list[str]] = {key: [] for key in dict.fromkeys(self._EXT_TO_KEY.values())}
        examples_dir = self.configs_dir / self.EXAMPLES_SUBDIR
        if not examples_dir.is_dir():
            return result
        for item in examples_dir.iterdir():
            if item.is_file() and item.suffix.lower() in self.SUPPORTED_FORMATS:
                result[self._EXT_TO_KEY[item.suffix.lower()]].append(item.name)
        return result

    def load_raw(self, filename: str) -> dict[str, Any]:
        """
        Загружает конфиг-файл без схемной валидации.

        Поддерживает автопоиск по базовому имени (без расширения).

        Args:
            filename: Имя файла или базовое имя без расширения.

        Returns:
            Загруженные данные в виде словаря.

        Raises:
            ConfigError: Если файл не найден или не удалось загрузить.
        """
        return self._parse_file(self._resolve_path(filename))

    def validate_config_file(self, filepath: str) -> dict[str, Any]:
        """
        Проверяет синтаксическую корректность файла конфигурации и возвращает его содержимое.

        Args:
            filepath: Абсолютный путь к файлу.

        Returns:
            Содержимое файла в виде словаря.

        Raises:
            ConfigError: Если файл не найден, формат не поддерживается
                         или содержимое невалидно.
        """
        path = Path(filepath)
        if not path.exists():
            raise ConfigError(f"Файл не найден: {filepath}")

        suffix = path.suffix.lower()
        if suffix not in self.SUPPORTED_FORMATS:
            raise ConfigError(
                f"Неподдерживаемый формат: {suffix}. " f"Поддерживаемые: {self.SUPPORTED_FORMATS}"
            )

        return self._parse_file(path)

    def _resolve_path(self, filename: str) -> Path:
        """
        Разрешает имя файла в абсолютный путь внутри ``configs_dir``.

        Если ``filename`` содержит известное расширение — возвращает путь напрямую.
        Если расширения нет — перебирает ``SUPPORTED_FORMATS`` и возвращает
        первый найденный файл.

        Args:
            filename: Имя файла (с расширением или без).

        Returns:
            Абсолютный путь к файлу.

        Raises:
            ConfigError: Если директория не найдена или файл не существует.
        """
        if not self.configs_dir.is_dir():
            raise ConfigError(
                f"Директория с конфигами не найдена или не является директорией: {self.configs_dir}"
            )

        if Path(filename).suffix.lower() in self.SUPPORTED_FORMATS:
            return self.configs_dir / filename

        for ext in self.SUPPORTED_FORMATS:
            candidate = self.configs_dir / f"{filename}{ext}"
            if candidate.exists():
                return candidate

        available = [item.name for item in self.configs_dir.iterdir() if not item.is_dir()]
        raise ConfigError(
            f'Конфиг "{filename}" не найден в {self.configs_dir}. '
            f"Доступные файлы: {available}. "
            f"Поддерживаемые форматы: {self.SUPPORTED_FORMATS}"
        )

    def _parse_file(self, filepath: Path) -> dict[str, Any]:
        """
        Читает и парсит файл конфигурации.

        Единственное место, где происходит чтение диска.
        Все ошибки преобразуются в ``ConfigError``.

        Args:
            filepath: Путь к файлу.

        Returns:
            Содержимое файла в виде словаря.

        Raises:
            ConfigError: При любой ошибке чтения или парсинга.
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

    def _validate(
        self, raw: dict[str, Any], schema_cls: type[_TConfig], source: str = ""
    ) -> _TConfig:
        """
        Валидирует словарь через Pydantic-схему.

        Args:
            raw: Данные для валидации.
            schema_cls: Класс схемы.
            source: Имя источника для сообщения об ошибке (обычно имя файла).

        Returns:
            Провалидированный объект схемы.

        Raises:
            ConfigError: Если данные не соответствуют схеме.
        """
        try:
            return schema_cls(**raw)
        except ValidationError as e:
            label = f" {source}" if source else ""
            raise ConfigError(f"Ошибка валидации{label}: {e}") from e
