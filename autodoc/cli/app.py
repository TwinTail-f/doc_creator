import sys
from pathlib import Path

import click

from autodoc.common.logger import LOGS_DIR_NAME, logger, start_session_file_log
from autodoc.cli.context import CliCtx
from autodoc.cli.helpers import console
from autodoc.cli.commands.parse import parse
from autodoc.cli.commands.publish import publish
from autodoc.cli.commands.config import config
from autodoc.cli.commands.info import info
from autodoc.cli.commands.logs import logs

# Соответствие подкоманды верхнего уровня имени модуля для файла логов сессии.
_MODULE_BY_SUBCOMMAND = {"parse": "parser", "publish": "publisher"}


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
def cli(ctx: click.Context, base_dir: Path, configs_dir: Path | None, verbose: bool) -> None:
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

    module_name = _MODULE_BY_SUBCOMMAND.get(ctx.invoked_subcommand)
    if module_name is not None:
        close_log = start_session_file_log(logger, module_name, base / LOGS_DIR_NAME)
        ctx.call_on_close(close_log)


# Регистрируем все команды и подгруппы
cli.add_command(parse)
cli.add_command(publish)
cli.add_command(config)
cli.add_command(info)
cli.add_command(logs)
