import sys
from pathlib import Path

import click

from autodoc.cli.context import CliCtx
from autodoc.cli.helpers import console
from autodoc.cli.commands.parse import parse
from autodoc.cli.commands.publish.all import publish
from autodoc.cli.commands.config import config
from autodoc.cli.commands.info import info


@click.group()
@click.option(
    "--base-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    show_default=True,
    help="Базовая директория проекта",
)
@click.option(
    "--configs-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Директория с конфигами (по умолчанию <base-dir>/configs)",
)
@click.option("-v", "--verbose", is_flag=True, help="Подробный вывод логов")
@click.pass_context
def cli(
    ctx: click.Context, base_dir: Path, configs_dir: Path | None, verbose: bool
) -> None:
    """
    Инструмент сбора и публикации документации компонентов платформы.

    Примеры:
        doc-generator parse
        doc-generator parse --skip-conan --save-intermediate
        doc-generator publish all
        doc-generator config list
    """
    base = base_dir.resolve()
    cfgs = configs_dir.resolve() if configs_dir else base / "configs"

    if not cfgs.exists():
        console.print(f"❌ Директория конфигов не найдена: {cfgs}", style="red bold")
        sys.exit(1)

    ctx.obj = CliCtx(base, cfgs, verbose)


# Register all commands and subgroups
cli.add_command(parse)
cli.add_command(publish)
cli.add_command(config)
cli.add_command(info)
