"""Команда publish kit-pinned."""

import click

from autodoc.cli.commands.publish.single_page import (
    kit_page_options,
    run_kit_page_command,
)
from autodoc.cli.constants import DEFAULT_KIT_PINNED_PAGE_TITLE, KIT_PINNED_TEMPLATE


@click.command("kit-pinned")
@kit_page_options
@click.pass_context
def publish_kit_pinned(
    ctx: click.Context,
    page_title: str | None,
    cli_root_page_id: str | None,
    cli_root_page_name: str | None,
) -> None:
    """Публикация комплекта для встраивания компонентов (закреплённые версии по каналам)."""
    run_kit_page_command(
        ctx,
        strategy_type="kit_pinned",
        template_name=KIT_PINNED_TEMPLATE,
        default_title=DEFAULT_KIT_PINNED_PAGE_TITLE,
        panel_header="🚀 Публикация комплекта для встраивания (закреплённые версии)",
        page_title=page_title,
        cli_root_page_id=cli_root_page_id,
        cli_root_page_name=cli_root_page_name,
    )
