"""Команда publish passports."""
import sys

import click
from rich.panel import Panel

from autodoc.exceptions import ConfigError, DocGeneratorError, PublishError
from autodoc.cli.constants import PASSPORT_TEMPLATE
from autodoc.cli.context import CliCtx
from autodoc.cli.helpers import (
    _load_parsed_data,
    _make_publisher,
    _print_publish_result,
    console,
)
from autodoc.cli.commands.publish._quote_hint import _QuoteHintCommand


@click.command("passports", cls=_QuoteHintCommand)
@click.option(
    "--passports-root-parent-id", "passports_root_parent_id", default=None,
    help="ID корневой страницы иерархии паспортов (переопределяет конфиг)",
)
@click.option(
    "--passports-root-parent-name", "passports_root_parent_name", default=None,
    help=(
        "Название корневой страницы иерархии паспортов (переопределяет конфиг). "
        'Если содержит пробелы — заключите в кавычки: --passports-root-parent-name "Моя страница"'
    ),
)
@click.pass_context
def publish_passports(
    ctx: click.Context,
    passports_root_parent_id: str | None,
    passports_root_parent_name: str | None,
) -> None:
    """Публикация паспортов компонентов в виде иерархии страниц."""
    if passports_root_parent_name and passports_root_parent_id:
        raise click.UsageError(
            "Укажите только один флаг: --passports-root-parent-name или --passports-root-parent-id."
        )

    cli_ctx: CliCtx = ctx.obj

    try:
        console.print(
            Panel.fit(
                "[bold blue]🚀 Публикация паспортов компонентов[/bold blue]",
                style="blue",
            )
        )

        publisher, conf_config = _make_publisher(cli_ctx)

        target_root = publisher.resolve_page_id(
            passports_root_parent_name or conf_config.passports_root_parent_name,
            passports_root_parent_id or conf_config.passports_root_parent_id,
            "passports_root_parent",
        )

        parsed_data = _load_parsed_data(cli_ctx.base_dir)

        console.print("🔄 Публикация паспортов… (может занять время)", style="cyan")
        result = publisher.publish(
            strategy_type="passports",
            parsed_data=parsed_data,
            root_page_id=target_root,
            template_name=PASSPORT_TEMPLATE,
            batch_size=conf_config.publish_batch_size,
            batch_delay_seconds=conf_config.publish_batch_delay_seconds,
            target_release_version=conf_config.target_release_version,
        )

        _print_publish_result(result)

    except (ConfigError, DocGeneratorError, PublishError) as e:
        console.print(f"❌ Ошибка: {e}", style="red bold")
        sys.exit(1)
