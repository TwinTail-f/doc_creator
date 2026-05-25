import sys

import click
from pydantic import ValidationError as PydanticValidationError
from rich.panel import Panel
from rich.table import Table

from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.exceptions import ConfigError
from autodoc.cli.context import CliCtx
from autodoc.cli.helpers import console

config = click.Group("config", help="Управление конфигурационными файлами.")


@config.command("list")
@click.pass_context
def config_list(ctx: click.Context) -> None:
    """Список доступных конфигурационных файлов."""
    cli_ctx: CliCtx = ctx.obj

    available = cli_ctx.config_manager.list_available_configs()
    examples = cli_ctx.config_manager.list_example_configs()

    console.print(Panel.fit("[bold]Доступные конфигурации[/bold]", style="blue"))

    for output_format, files in available.items():
        if files:
            table = Table(
                title=f"{output_format.upper()} конфигурации", show_header=True
            )
            table.add_column("Файл", style="cyan")
            for fname in files:
                table.add_row(fname)
            console.print(table)
        else:
            console.print(
                f"{output_format.upper()} конфиги: [yellow]не найдены[/yellow]"
            )

    # Примеры
    has_examples = any(examples.values())
    if has_examples:
        console.print("\n[bold]Примеры (configs/examples/)[/bold]")
        for output_format, files in examples.items():
            for fname in files:
                console.print(f"  [dim]{output_format}: {fname}[/dim]")


@config.command("validate")
@click.argument("config-file")
@click.pass_context
def config_validate(ctx: click.Context, config_file: str) -> None:
    """Валидировать синтаксис конфигурационного файла."""
    cli_ctx: CliCtx = ctx.obj

    filepath = cli_ctx.configs_dir / config_file
    try:
        cli_ctx.config_manager.validate_config_file(str(filepath))
    except ConfigError as e:
        console.print(f"❌ Файл невалиден: {e}", style="red bold")
        sys.exit(1)

    console.print(f"✅ Синтаксис файла корректен: {config_file}", style="green bold")

    # Загружаем сырые данные один раз, до любой схемной валидации.
    try:
        raw = cli_ctx.config_manager.load_raw(config_file)
    except ConfigError as e:
        console.print(f"❌ Не удалось загрузить файл: {e}", style="red bold")
        sys.exit(1)

    # Определяем схему по наличию ключевых полей — не через перебор исключений.
    is_parser = "tfs_token" in raw and "platform_version" in raw
    is_confluence_publisher = "url" in raw and "token" in raw and "space" in raw

    if is_parser:
        try:
            ParserConfigSchema(**raw)
            console.print(
                "✅ Pydantic валидация пройдена (схема: parser)", style="green"
            )
        except PydanticValidationError as e:
            console.print(
                f"⚠️  Схема parser: файл загружается, но содержит ошибки валидации:\n{e}",
                style="yellow",
            )
    elif is_confluence_publisher:
        try:
            ConfluenceConfigSchema(**raw)
            console.print(
                "✅ Pydantic валидация пройдена (схема: confluence)", style="green"
            )
        except PydanticValidationError as e:
            console.print(
                f"⚠️  Схема confluence: файл загружается, но содержит ошибки валидации:\n{e}",
                style="yellow",
            )
    else:
        console.print(
            "⚠️  JSON/YAML синтаксически корректен, но не соответствует "
            "ни одной известной схеме.",
            style="yellow",
        )
