import sys
from pathlib import Path

from rich.console import Console

from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.publisher import DocumentPublisher
from autodoc.publisher.strategies.models.publish_report import PublishReport
from autodoc.cli.context import CliCtx

# Примечание: утилита предназначена для запуска на Linux.
# Unicode-эмодзи в выводе могут не отображаться в консоли Windows.

console = Console()


def _load_parsed_data(base_dir: Path) -> ParsedResult:
    """Загружает parsed_data.json и десериализует в ParsedResult."""
    data_file = base_dir / "data" / "parsed_data.json"
    if not data_file.exists():
        console.print(
            "❌ Файл parsed_data.json не найден. Сначала запустите " '"parse"',
            style="red bold",
        )
        sys.exit(1)
    return ParsedResult.model_validate_json(data_file.read_text(encoding="utf-8"))


def _make_publisher(
    cli_ctx: CliCtx,
    config_file: str | None = None,
) -> tuple[DocumentPublisher, ConfluenceConfigSchema]:
    """Создаёт DocumentPublisher и возвращает его вместе с конфигом."""
    conf_config = cli_ctx.config_manager.load_confluence_config(config_file)
    rendering_dir = cli_ctx.base_dir / "autodoc" / "publisher" / "rendering"
    return DocumentPublisher(conf_config, rendering_dir), conf_config


def _print_publish_result(result: PublishReport) -> None:
    """Выводит результат публикации в консоль."""
    from rich.panel import Panel

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
        if result.pages_published == 0:
            sys.exit(1)
