"""Команда publish kit-fixed."""

import click

from autodoc.cli.commands.publish.single_page import (
    kit_page_options,
    run_kit_page_command,
)
from autodoc.cli.constants import DEFAULT_KIT_FIXED_PAGE_TITLE, KIT_FIXED_TEMPLATE


@click.command("kit-fixed")
@kit_page_options
@click.pass_context
def publish_kit_fixed(
    ctx: click.Context,
    page_title: str | None,
    cli_root_page_id: str | None,
    cli_root_page_name: str | None,
) -> None:
    """Публикация комплекта для встраивания компонентов (фиксированные версии по каналам)."""
    run_kit_page_command(
        ctx,
        strategy_type="kit_fixed",
        template_name=KIT_FIXED_TEMPLATE,
        default_title=DEFAULT_KIT_FIXED_PAGE_TITLE,
        panel_header="🚀 Публикация комплекта для встраивания (фиксированные версии)",
        page_title=page_title,
        cli_root_page_id=cli_root_page_id,
        cli_root_page_name=cli_root_page_name,
    )
