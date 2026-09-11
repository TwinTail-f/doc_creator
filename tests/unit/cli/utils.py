"""
Фабрики и константы для тестов пакета tests/unit/cli.

Обычные функции и константы (в отличие от fixtures) не должны жить в
conftest.py — вынесены сюда и импортируются явно там, где нужны.
"""

import json
from pathlib import Path
from typing import Any

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


def write_parser_config(
    directory: Path,
    filename: str = "parser_config.json",
    **overrides: Any,
) -> Path:
    """
    Записывает минимальный валидный конфиг парсера в JSON-файл.

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
    """
    Записывает минимальный валидный конфиг Confluence в JSON-файл.

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
    """
    Создаёт валидный экземпляр ConfluenceConfigSchema в памяти, без записи на диск.

    Args:
        **overrides: Поля, переопределяющие значения из ``VALID_CONFLUENCE_CONFIG``.

    Returns:
        Провалидированный экземпляр ``ConfluenceConfigSchema``.
    """
    data = {**VALID_CONFLUENCE_CONFIG, **overrides}
    return ConfluenceConfigSchema(**data)


def strategy_override(section: str, **fields: Any) -> dict[str, Any]:
    """
    Собирает overrides для make_confluence_config() с валидной секцией
    strategies.<section>: если вызывающий не передал ни root_parent_id, ни
    root_parent_name явно, подставляет заглушку root_parent_id, чтобы секция
    прошла валидацию ConfluenceConfigSchema (см. StrategiesConfig._require_root_parent_for_explicit_sections).

    Явный root_parent_id=None (или root_parent_name=None) в fields НЕ переопределяется —
    так тесты могут осознанно проверить сценарий "секция есть, родителя нет".
    """
    if "root_parent_id" not in fields and "root_parent_name" not in fields:
        fields["root_parent_id"] = "test-parent-id"
    return {"strategies": {section: fields}}


def make_parsed_result(**overrides: Any) -> ParsedResult:
    """
    Создаёт минимальный валидный экземпляр ParsedResult.

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
    """
    Сохраняет ParsedResult в ``<base_dir>/data/parsed_data.json``.

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
    """
    Создаёт PublishReport для успешного или неуспешного сценария публикации.

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
    return PublishReport(**data)
