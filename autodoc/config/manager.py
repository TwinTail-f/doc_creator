"""
Менеджер конфигураций с поддержкой форматов JSON и YAML.
"""

import json
from pathlib import Path
from typing import Any
from pydantic import ValidationError

import yaml

from autodoc.config.schemas import ConfluenceConfigSchema, ParserConfigSchema
from autodoc.infrastructure.logger import logger


class ConfigManager:
    """
    Менеджер для загрузки и валидации конфигурационных файлов.

    Поддерживает форматы JSON и YAML. При явно переданном имени файла
    ищет именно его; если имя не указано — перебирает поддерживаемые
    расширения в порядке ``SUPPORTED_FORMATS``.

    Ошибки логируются на месте и не пробрасываются наверх через исключения —
    методы возвращают ``None`` при любой предсказуемой проблеме
    (файл не найден, неподдерживаемый формат, невалидная схема).
    Исключения сохраняются только там, где ошибку нельзя предвидеть заранее
    (невалидный JSON/YAML).

    Attributes:
        configs_dir: Путь к директории с конфигурационными файлами.
    """

    SUPPORTED_FORMATS: list[str] = [".json", ".yaml", ".yml"]

    def __init__(self, configs_dir: str) -> None:
        """
        Инициализирует менеджер конфигураций.

        Директория проверяется сразу. Если она не существует — об этом
        сообщается в лог, но исключение не бросается: методы ``load_*``
        вернут ``None`` при первом же обращении.

        Args:
            configs_dir: Абсолютный путь к папке ``configs/``.
        """
        self.configs_dir = Path(configs_dir)
        if not self.configs_dir.is_dir():
            logger.error(f"Директория с конфигами не найдена: {configs_dir}")
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
        if not self.configs_dir.is_dir():
            logger.error(f"Директория с конфигами недоступна: {self.configs_dir}")
            return None

        filename = config_file or self._find_config_file("parser_config")
        if filename is None:
            return None

        raw = self._load_config(filename)
        if raw is None:
            return None

        try:
            validated = ParserConfigSchema(**raw)
            logger.info(f"{filename} успешно загружен и провалидирован")
            return validated
        except ValidationError as e:
            logger.error(f"Ошибка валидации {filename}: {e}")
            return None

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
        if not self.configs_dir.is_dir():
            logger.error(f"Директория с конфигами недоступна: {self.configs_dir}")
            return None

        filename = config_file or self._find_config_file("confluence_config")
        if filename is None:
            return None

        raw = self._load_config(filename)
        if raw is None:
            return None

        try:
            validated = ConfluenceConfigSchema(**raw)
            logger.info(f"{filename} успешно загружен и провалидирован")
            return validated
        except ValidationError as e:
            logger.error(f"Ошибка валидации {filename}: {e}")
            return None

    def load_raw(self, filename: str) -> dict[str, Any] | None:
        """
        Загружает конфиг-файл без схемной валидации.

        Args:
            filename: Имя файла (с расширением).

        Returns:
            Загруженные данные в виде словаря или ``None`` при ошибке.
        """
        if not self.configs_dir.is_dir():
            logger.error(f"Директория с конфигами недоступна: {self.configs_dir}")
            return None
        return self._load_config(filename)

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
            if suffix == ".json":
                with path.open("r", encoding="utf-8") as f:
                    json.load(f)
            else:  # .yaml / .yml
                with path.open("r", encoding="utf-8") as f:
                    yaml.safe_load(f)
            return True, None
        except (json.JSONDecodeError, yaml.YAMLError, OSError) as e:
            return False, f"Ошибка валидации: {e}"

    def list_available_configs(self) -> dict[str, list[str]]:
        """
        Возвращает список конфигурационных файлов в директории.

        Returns:
            Словарь вида ``{"json": [...], "yaml": [...]}`` или пустой при недоступной директории.
        """
        configs: dict[str, list[str]] = {"json": [], "yaml": []}

        if not self.configs_dir.is_dir():
            logger.warning(f"Директория конфигов недоступна: {self.configs_dir}")
            return configs

        try:
            for entry in self.configs_dir.iterdir():
                if entry.suffix == ".json":
                    configs["json"].append(entry.name)
                elif entry.suffix in (".yaml", ".yml"):
                    configs["yaml"].append(entry.name)
        except OSError as e:
            logger.warning(f"Ошибка при чтении директории конфигов: {e}")

        return configs

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

        available = [e.name for e in self.configs_dir.iterdir() if not e.is_dir()]
        logger.error(
            f'Конфиг "{basename}" не найден в {self.configs_dir}. '
            f"Доступные файлы: {available}. "
            f"Поддерживаемые форматы: {self.SUPPORTED_FORMATS}"
        )
        return None

    def _load_config(self, filename: str) -> dict[str, Any] | None:
        """
        Загружает конфигурационный файл по имени.

        Args:
            filename: Имя файла (с расширением).

        Returns:
            Загруженные данные в виде словаря или ``None`` при ошибке.
        """
        filepath = self.configs_dir / filename

        if not filepath.exists():
            logger.error(f"Конфиг-файл не найден: {filepath}")
            return None

        suffix = filepath.suffix.lower()
        if suffix == ".json":
            return self._load_json(filepath)
        elif suffix in (".yaml", ".yml"):
            return self._load_yaml(filepath)
        else:
            logger.error(
                f"Неподдерживаемый формат: {suffix}. "
                f"Поддерживаемые: {self.SUPPORTED_FORMATS}"
            )
            return None

    def _load_json(self, filepath: Path) -> dict[str, Any] | None:
        """
        Читает JSON-файл.

        Args:
            filepath: Путь к файлу.

        Returns:
            Содержимое файла в виде словаря или ``None`` при ошибке чтения/парсинга.
        """
        if not filepath.is_file():
            logger.error(f"Файл недоступен для чтения: {filepath.name}")
            return None

        try:
            with filepath.open("r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Невалидный JSON в {filepath.name}: {e}")
            return None
        except OSError as e:
            logger.error(f"Ошибка чтения {filepath.name}: {e}")
            return None

    def _load_yaml(self, filepath: Path) -> dict[str, Any] | None:
        """
        Читает YAML-файл.

        Args:
            filepath: Путь к файлу.

        Returns:
            Содержимое файла в виде словаря или ``None`` при ошибке чтения/парсинга.
        """
        if not filepath.is_file():
            logger.error(f"Файл недоступен для чтения: {filepath.name}")
            return None

        try:
            with filepath.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            logger.error(f"Невалидный YAML в {filepath.name}: {e}")
            return None
        except OSError as e:
            logger.error(f"Ошибка чтения {filepath.name}: {e}")
            return None

        if not isinstance(data, dict):
            logger.error(
                f"YAML-файл {filepath.name} должен содержать объект (dict), "
                f"получен {type(data).__name__}"
            )
            return None

        return data
