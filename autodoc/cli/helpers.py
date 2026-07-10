import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import click
from pydantic import ValidationError as PydanticValidationError
from rich.console import Console
from rich.panel import Panel

from autodoc.common.logger import logger
from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.exceptions import ConfigError, DocGeneratorError, PublishError, ValidationError
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.publisher import DocumentPublisher
from autodoc.publisher.strategies.models.publish_report import PublishReport
from autodoc.cli.context import CliCtx

# Примечание: утилита предназначена для запуска на Linux.
# Unicode-эмодзи в выводе могут не отображаться в консоли Windows.

console = Console()


@contextmanager
def cli_error_boundary(panel_header: str) -> Generator[None, None, None]:
    """Контекстный менеджер для единообразной обработки ошибок CLI-команды.

    Выводит заголовок панели, перехватывает доменные исключения,
    печатает сообщение об ошибке и завершает процесс с кодом 1.

    Args:
        panel_header: Текст заголовка панели Rich для отображения перед запуском.

    Raises:
        SystemExit: При перехвате ConfigError, DocGeneratorError или PublishError.
    """
    console.print(Panel.fit(f"[bold blue]{panel_header}[/bold blue]", style="blue"))
    try:
        yield
    except (ConfigError, DocGeneratorError, PublishError) as e:
        console.print(f"❌ Ошибка: {e}", style="red bold")
        sys.exit(1)


def load_parsed_data(base_dir: Path) -> ParsedResult:
    """Загружает parsed_data.json и десериализует в ParsedResult.

    Args:
        base_dir: Базовая директория проекта; файл ищется в ``<base_dir>/data/parsed_data.json``.

    Returns:
        Десериализованный результат парсинга.

    Raises:
        DocGeneratorError: Если файл ``parsed_data.json`` не найден.
        ValidationError: Если файл пустой, содержит невалидный JSON или не
            соответствует ожидаемой схеме ``ParsedResult``.
    """
    data_file = base_dir / "data" / "parsed_data.json"
    if not data_file.exists():
        raise DocGeneratorError('Файл parsed_data.json не найден. Сначала запустите "parse".')

    raw = data_file.read_text(encoding="utf-8")
    if not raw.strip():
        raise ValidationError(
            f'Файл {data_file} пуст. Похоже, команда "parse" завершилась с ошибкой '
            'или была прервана до сохранения результата. Запустите "parse" заново.'
        )

    try:
        return ParsedResult.model_validate_json(raw)
    except PydanticValidationError as e:
        logger.debug(f"Не удалось разобрать {data_file}: {e}")
        raise ValidationError(
            f"Файл {data_file} повреждён или не соответствует ожидаемому формату. "
            f'Запустите "parse" заново (подробности ошибки валидации — в лог-файле запуска).'
        ) from e


def make_publisher(
    cli_ctx: CliCtx,
    config_file: str | None = None,
) -> tuple[DocumentPublisher, ConfluenceConfigSchema]:
    """Создаёт DocumentPublisher для публикации в Confluence.

    Загружает конфигурацию Confluence через ``cli_ctx.config_manager`` и
    оборачивает её в готовый к использованию ``DocumentPublisher``, чтобы
    каждой команде публикации не приходилось повторять эту инициализацию.

    Args:
        cli_ctx: Контекст CLI с доступом к менеджеру конфигураций.
        config_file: Имя файла конфига Confluence или ``None`` для автоопределения.

    Returns:
        Пара из ``DocumentPublisher`` и загруженной конфигурации Confluence.

    Raises:
        ConfigError: Если конфигурацию Confluence не удалось загрузить.
    """
    conf_config = cli_ctx.config_manager.load_confluence_config(config_file)
    if conf_config is None:
        raise ConfigError("Не удалось загрузить конфигурацию Confluence.")
    return DocumentPublisher(conf_config), conf_config


def print_publish_result(result: PublishReport) -> None:
    """Выводит результат публикации в консоль в едином для всех команд формате.

    При неуспехе или если ни одна страница не была опубликована — завершает
    процесс с кодом 1, чтобы CI/скрипты, вызывающие CLI, могли отличить
    неудачную публикацию от успешной.

    Args:
        result: Отчёт о публикации, возвращённый ``DocumentPublisher``.

    Raises:
        SystemExit: Если публикация завершилась с ошибками либо
            ``result.pages_published == 0``.
    """
    if result.success:
        console.print(
            Panel.fit(
                f"[bold green]✅ Публикация завершена успешно![/bold green]\n"
                f"Страниц создано/обновлено: {result.pages_published}",
                style="green",
            )
        )
    else:
        console.print("⚠️  Публикация завершена с ошибками:", style="yellow bold")
        for err in result.errors:
            console.print(f"  • {err}", style="yellow")

    publish_failed = not result.success or result.pages_published == 0
    if publish_failed:
        sys.exit(1)
