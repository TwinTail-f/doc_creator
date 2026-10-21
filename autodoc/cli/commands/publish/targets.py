"""Команда publish targets."""

import click

from autodoc.cli.context import CliCtx
from autodoc.cli.helpers import (
    cli_error_boundary,
    console,
    load_parsed_data,
    make_publisher,
    print_publish_result,
)


@click.command("targets")
@click.pass_context
def publish_targets(ctx: click.Context) -> None:
    """Публикация типов страниц, выбранных в конфиге (publish_targets)."""
    cli_ctx: CliCtx = ctx.obj

    with cli_error_boundary("🚀 Комплексная публикация документации"):
        publisher, confluence_config = make_publisher(cli_ctx)
        parsed_data = load_parsed_data(cli_ctx.base_dir)

        console.print(
            f"🔄 Публикация: {', '.join(confluence_config.publish_targets)}…", style="cyan"
        )
        result = publisher.publish_targets(parsed_data=parsed_data)

        console.print(
            f"  Страниц опубликовано: {result.pages_published}",
            style="dim",
        )
        print_publish_result(result)
