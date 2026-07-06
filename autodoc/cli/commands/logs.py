"""Команды управления директорией логов."""

import click

from autodoc.common.logger import LOGS_DIR_NAME, clear_logs_dir
from autodoc.cli.context import CliCtx
from autodoc.cli.helpers import console

logs = click.Group("logs", help="Управление директорией логов.")


@logs.command("clear")
@click.option("--yes", "-y", is_flag=True, help="Не запрашивать подтверждение")
@click.pass_context
def logs_clear(ctx: click.Context, yes: bool) -> None:
    """Удалить все файлы логов из директории logs/."""
    cli_ctx: CliCtx = ctx.obj
    logs_dir = cli_ctx.base_dir / LOGS_DIR_NAME

    if not yes:
        click.confirm(f"Удалить все файлы логов из {logs_dir}?", abort=True)

    deleted = clear_logs_dir(logs_dir)
    if not deleted:
        console.print("ℹ️  Нет файлов логов для удаления.", style="cyan")
        return

    console.print(f"✅ Удалено файлов: {len(deleted)}", style="green")
    for path in deleted:
        console.print(f"  • {path.name}", style="dim")
