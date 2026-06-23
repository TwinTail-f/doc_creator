"""Команда publish passports."""
import click

from autodoc.cli.constants import PASSPORT_TEMPLATE
from autodoc.cli.context import CliCtx
from autodoc.cli.helpers import (
    cli_error_boundary,
    console,
    load_parsed_data,
    make_publisher,
    print_publish_result,
    require_exclusive,
)
from autodoc.cli.commands.publish._quote_hint import _QuoteHintCommand

_PASSPORTS_ROOT_NAME_FLAG: str = "--passports-root-parent-name"
_PASSPORTS_ROOT_ID_FLAG: str = "--passports-root-parent-id"


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
    require_exclusive(
        passports_root_parent_name,
        passports_root_parent_id,
        name_flag=_PASSPORTS_ROOT_NAME_FLAG,
        id_flag=_PASSPORTS_ROOT_ID_FLAG,
    )

    cli_ctx: CliCtx = ctx.obj

    with cli_error_boundary("🚀 Публикация паспортов компонентов"):
        publisher, conf_config = make_publisher(cli_ctx)
        parsed_data = load_parsed_data(cli_ctx.base_dir)

        console.print("🔄 Публикация паспортов… (может занять время)", style="cyan")
        result = publisher.publish_passports(
            parsed_data=parsed_data,
            template_name=PASSPORT_TEMPLATE,
            passports_root_parent_name=passports_root_parent_name,
            passports_root_parent_id=passports_root_parent_id,
        )

        print_publish_result(result)
