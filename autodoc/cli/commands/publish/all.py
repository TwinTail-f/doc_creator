"""Команда publish all."""

import click

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

        console.print(
            f"🔄 Публикация: {', '.join(confluence_config.publish_all.targets)}…", style="cyan"
        )
        result = publisher.publish_all(parsed_data=parsed_data)

        console.print(
            f"  Страниц опубликовано: {result.pages_published}",
            style="dim",
        )
        print_publish_result(result)
