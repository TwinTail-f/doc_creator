# autodoc/cli/_app.py

import sys
from pathlib import Path

import click

from autodoc.cli._context import _CliCtx
from autodoc.cli._helpers import console
from autodoc.cli.commands.parse import parse
from autodoc.cli.commands.publish import publish
from autodoc.cli.commands.config import config
from autodoc.cli.commands.info import info


@click.group(invoke_without_command=True)
@click.option(
    "--base-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=".",
    show_default=True,
    help="Базовая директория проекта",
)
@click.option(
    "--configs-dir",
    type=click.Path(file_okay=False, dir_okay=True),
    default=None,
    help="Директория с конфигами (по умолчанию <base-dir>/configs)",
)
@click.option("-v", "--verbose", is_flag=True, help="Подробный вывод логов")
@click.pass_context
def cli(
    ctx: click.Context, base_dir: str, configs_dir: str | None, verbose: bool
) -> None:
    """
    Инструмент сбора и публикации документации компонентов платформы.

    \b
    Примеры:
        doc-generator parse
        doc-generator parse --skip-conan --save-intermediate
        doc-generator publish all
        doc-generator config list
    """
    base = Path(base_dir).resolve()
    cfgs = Path(configs_dir).resolve() if configs_dir else base / "configs"

    if not cfgs.exists():
        console.print(f"❌ Директория конфигов не найдена: {cfgs}", style="red bold")
        sys.exit(1)

    ctx.ensure_object(dict)
    ctx.obj["cli"] = _CliCtx(base, cfgs, verbose)

    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


# Register all commands and subgroups
cli.add_command(parse)
cli.add_command(publish)
cli.add_command(config)
cli.add_command(info)
