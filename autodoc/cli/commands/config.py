import sys

import click
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
from rich.panel import Panel
from rich.table import Table

from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
# TODO(review): autodoc.config.schemas.parser_config отсутствует в кодовой базе —
# импорт ниже не разрешится, пока модуль не будет добавлен. Это не входит
# в текущую задачу (autodoc/config/** не в её рамках).
from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.exceptions import ConfigError
from autodoc.cli.context import CliCtx
from autodoc.cli.helpers import console

config = click.Group("config", help="Управление конфигурационными файлами.")

# Порядок проверки схем при автоопределении типа конфига в config_validate().
_CONFIG_SCHEMAS: tuple[tuple[type[BaseModel], str], ...] = (
    (ParserConfigSchema, "parser"),
    (ConfluenceConfigSchema, "confluence"),
)


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
        raw = cli_ctx.config_manager.validate_config_file(str(filepath))
    except ConfigError as e:
        console.print(f"❌ Файл невалиден: {e}", style="red bold")
        sys.exit(1)

    console.print(f"✅ Синтаксис файла корректен: {config_file}", style="green bold")

    # Определяем схему, пробуя каждую по очереди — без перебора ключей.
    # Первая схема, которая успешно валидируется, считается подходящей.
    validation_errors: list[str] = []
    for schema_cls, schema_name in _CONFIG_SCHEMAS:
        try:
            schema_cls(**raw)
        except PydanticValidationError as e:
            validation_errors.append(f"схема {schema_name}: {e}")
            continue
        console.print(
            f"✅ Pydantic валидация пройдена (схема: {schema_name})", style="green"
        )
        return

    console.print(
        "⚠️  JSON/YAML синтаксически корректен, но не соответствует "
        "ни одной известной схеме:\n" + "\n".join(validation_errors),
        style="yellow",
    )
