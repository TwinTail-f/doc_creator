# autodoc/cli/commands/info.py

import click
from rich.panel import Panel

from autodoc.cli._constants import _VERSION
from autodoc.cli._helpers import console


@click.command()
def info() -> None:
    """Показать версию и список возможностей."""
    console.print(
        Panel(
            f"[bold cyan]Doc Generator v{_VERSION}[/bold cyan]\n\n"
            "✓ Автоматический сбор данных компонентов из TFS\n"
            "✓ Сбор данных о опубликованных компонентах на artifactory посредством вызова команды conan graph info\n"
            "✓ Публикация паспортов компонентов (publish passports)\n"
            "✓ Публикация релизной документации от компонентов (publish release)\n"
            "✓ Публикация документации от профилей (publish profile)\n"
            "✓ Команда publish all (паспорта + релиз за один вызов)\n",
            title="Doc Generator",
            style="blue",
        )
    )
