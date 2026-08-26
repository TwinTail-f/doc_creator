"""Команда publish kit-latest."""

import click

from autodoc.cli.commands.publish.single_page import (
    kit_page_options,
    run_kit_page_command,
)
from autodoc.cli.constants import DEFAULT_KIT_LATEST_PAGE_TITLE, KIT_LATEST_TEMPLATE


@click.command("kit-latest")
@kit_page_options
@click.pass_context
def publish_kit_latest(
    ctx: click.Context,
    page_title: str | None,
    cli_root_page_id: str | None,
    cli_root_page_name: str | None,
) -> None:
    """Публикация ссылок на последние сборки компонентов (без фиксации версии) по каналам."""
    run_kit_page_command(
        ctx,
        strategy_type="kit_latest",
        template_name=KIT_LATEST_TEMPLATE,
        default_title=DEFAULT_KIT_LATEST_PAGE_TITLE,
        panel_header="🚀 Публикация ссылок на последние сборки компонентов",
        page_title=page_title,
        cli_root_page_id=cli_root_page_id,
        cli_root_page_name=cli_root_page_name,
    )
