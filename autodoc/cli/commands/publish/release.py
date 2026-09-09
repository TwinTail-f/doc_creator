"""Команда publish release."""

import click

from autodoc.cli.constants import DEFAULT_RELEASE_PAGE_TITLE, RELEASE_TEMPLATE
from autodoc.cli.commands.publish.single_page import (
    single_page_options,
    run_single_page_command,
)


@click.command("release")
@single_page_options
@click.pass_context
def publish_release(
    ctx: click.Context,
    page_title: str | None,
    cli_root_page_id: str | None,
    cli_root_page_name: str | None,
    no_passport_links: bool,
) -> None:
    """Публикация релизной документации."""
    run_single_page_command(
        ctx,
        strategy_type="release",
        template_name=RELEASE_TEMPLATE,
        default_title=DEFAULT_RELEASE_PAGE_TITLE,
        panel_header="🚀 Публикация релизной документации",
        page_title=page_title,
        cli_root_page_id=cli_root_page_id,
        cli_root_page_name=cli_root_page_name,
        include_passport_links=not no_passport_links,
    )
