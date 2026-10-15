"""Команда publish all."""

import click

from autodoc.cli.constants import (
    DEFAULT_KIT_LATEST_PAGE_TITLE,
    DEFAULT_KIT_PINNED_PAGE_TITLE,
    DEFAULT_PROFILE_PAGE_TITLE,
    DEFAULT_RELEASE_PAGE_TITLE,
)
from autodoc.cli.context import CliCtx
from autodoc.cli.helpers import (
    cli_error_boundary,
    console,
    load_parsed_data,
    make_publisher,
    print_publish_result,
)


@click.command("all")
@click.pass_context
def publish_all(ctx: click.Context) -> None:
    """Публикация типов из ``publish_all.targets`` конфига; по умолчанию — всех."""
    cli_ctx: CliCtx = ctx.obj

    with cli_error_boundary("🚀 Комплексная публикация документации"):
        publisher, confluence_config = make_publisher(cli_ctx)
        parsed_data = load_parsed_data(cli_ctx.base_dir)
        strategies = confluence_config.strategies

        console.print(
            f"🔄 Публикация: {', '.join(confluence_config.publish_all.targets)}…", style="cyan"
        )
        result = publisher.publish_all(
            parsed_data=parsed_data,
            release_page_title=strategies.release.page_title or DEFAULT_RELEASE_PAGE_TITLE,
            profile_page_title=strategies.profile_centric.page_title or DEFAULT_PROFILE_PAGE_TITLE,
            kit_pinned_page_title=strategies.kit_pinned.page_title or DEFAULT_KIT_PINNED_PAGE_TITLE,
            kit_latest_page_title=strategies.kit_latest.page_title or DEFAULT_KIT_LATEST_PAGE_TITLE,
        )

        console.print(
            f"  Страниц опубликовано: {result.pages_published}",
            style="dim",
        )
        print_publish_result(result)
