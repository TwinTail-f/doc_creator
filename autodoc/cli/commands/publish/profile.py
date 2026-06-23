"""Команда publish profile."""
import click

from autodoc.cli.constants import DEFAULT_PROFILE_PAGE_TITLE, PROFILE_TEMPLATE
from autodoc.cli.commands.publish.quote_hint import QuoteHintCommand
from autodoc.cli.commands.publish.single_page import (
    _single_page_options,
    run_single_page_command,
)


@click.command("profile", cls=QuoteHintCommand)
@_single_page_options
@click.pass_context
def publish_profile(
    ctx: click.Context,
    page_title: str | None,
    cli_root_page_id: str | None,
    cli_root_page_name: str | None,
    no_passport_links: bool,
) -> None:
    """Публикация документации в представлении от профилей сборки."""
    run_single_page_command(
        ctx,
        strategy_type="profile_centric",
        template_name=PROFILE_TEMPLATE,
        default_title=DEFAULT_PROFILE_PAGE_TITLE,
        panel_header="🚀 Публикация документации от профилей",
        page_title=page_title,
        cli_root_page_id=cli_root_page_id,
        cli_root_page_name=cli_root_page_name,
        no_passport_links=no_passport_links,
    )
