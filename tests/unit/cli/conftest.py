"""Общие fixtures и фабрики для тестов пакета tests/unit/cli.

Область видимости этих fixtures ограничена tests/unit/cli а.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.strategies.models.publish_report import PublishReport

_CONFIG_RESOURCES_DIR: Path = Path(__file__).parents[1] / "config" / "resources"

VALID_PARSER_CONFIG: dict[str, Any] = json.loads(
    (_CONFIG_RESOURCES_DIR / "valid_parser_config.json").read_text()
)
"""Минимальный набор полей, удовлетворяющий обязательным полям ParserConfigSchema."""

VALID_CONFLUENCE_CONFIG: dict[str, Any] = json.loads(
    (_CONFIG_RESOURCES_DIR / "valid_confluence_config.json").read_text()
)
"""Минимальный набор полей, удовлетворяющий обязательным полям ConfluenceConfigSchema."""


@pytest.fixture()
def configs_dir(tmp_path: Path) -> Path:
    """Создаёт пустую директорию конфигов внутри tmp_path.

    Требуется, так как корневая команда ``cli`` завершается с кодом 1, если
    директория, переданная в ``--configs-dir``, не существует.

    Args:
        tmp_path: Встроенная pytest-фикстура с временной директорией.

    Returns:
        Путь к пустой директории конфигов.
    """
    directory = tmp_path / "configs"
    directory.mkdir()
    return directory


def write_parser_config(
    directory: Path,
    filename: str = "parser_config.json",
    **overrides: Any,
) -> Path:
    """Записывает минимальный валидный конфиг парсера в JSON-файл.

    Args:
        directory: Директория, в которую записывается файл.
        filename: Имя файла конфига парсера.
        **overrides: Поля, переопределяющие значения из ``VALID_PARSER_CONFIG``
            (значение ``None`` удаляет поле из итогового словаря).

    Returns:
        Путь к записанному файлу конфига.
    """
    data = {**VALID_PARSER_CONFIG, **overrides}
    data = {k: v for k, v in data.items() if v is not None}
    path = directory / filename
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def write_confluence_config(
    directory: Path,
    filename: str = "confluence_config.json",
    **overrides: Any,
) -> Path:
    """Записывает минимальный валидный конфиг Confluence в JSON-файл.

    Args:
        directory: Директория, в которую записывается файл.
        filename: Имя файла конфига Confluence.
        **overrides: Поля, переопределяющие значения из ``VALID_CONFLUENCE_CONFIG``.

    Returns:
        Путь к записанному файлу конфига.
    """
    data = {**VALID_CONFLUENCE_CONFIG, **overrides}
    path = directory / filename
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def make_confluence_config(**overrides: Any) -> ConfluenceConfigSchema:
    """Создаёт валидный экземпляр ConfluenceConfigSchema в памяти, без записи на диск.

    Args:
        **overrides: Поля, переопределяющие значения из ``VALID_CONFLUENCE_CONFIG``.

    Returns:
        Провалидированный экземпляр ``ConfluenceConfigSchema``.
    """
    data = {**VALID_CONFLUENCE_CONFIG, **overrides}
    return ConfluenceConfigSchema(**data)


def make_parsed_result(**overrides: Any) -> ParsedResult:
    """Создаёт минимальный валидный экземпляр ParsedResult.

    Args:
        **overrides: Поля, переопределяющие значения по умолчанию
            (``generated_at``, ``platform_version``).

    Returns:
        Провалидированный экземпляр ``ParsedResult``.
    """
    data: dict[str, Any] = {
        "generated_at": "2024-01-01T00:00:00",
        "platform_version": "2.0",
        **overrides,
    }
    return ParsedResult(**data)


def write_parsed_data(base_dir: Path, parsed_result: ParsedResult) -> Path:
    """Сохраняет ParsedResult в ``<base_dir>/data/parsed_data.json``.

    Использует тот же путь, который читает ``load_parsed_data()`` из
    ``autodoc/cli/helpers.py``.

    Args:
        base_dir: Базовая директория проекта.
        parsed_result: Результат парсинга для сохранения.

    Returns:
        Путь к записанному файлу ``parsed_data.json``.
    """
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "parsed_data.json"
    path.write_text(parsed_result.model_dump_json(), encoding="utf-8")
    return path


def make_publish_report(
    success: bool = True,
    pages_published: int = 3,
    **overrides: Any,
) -> PublishReport:
    """Создаёт PublishReport для успешного или неуспешного сценария публикации.

    Args:
        success: Признак успешного завершения публикации.
        pages_published: Количество опубликованных страниц.
        **overrides: Дополнительные поля ``PublishReport`` (например, ``errors``).

    Returns:
        Экземпляр ``PublishReport`` с заданными параметрами.
    """
    data: dict[str, Any] = {
        "success": success,
        "pages_published": pages_published,
        **overrides,
    }
    if not success and "errors" not in data:
        data["errors"] = ["boom"]
    return PublishReport(**data)
