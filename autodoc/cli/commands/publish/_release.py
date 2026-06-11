"""Команды publish release и publish profile."""
import sys

import click
from rich.panel import Panel

from autodoc.exceptions import ConfigError, DocGeneratorError, PublishError
from autodoc.cli.constants import (
    DEFAULT_PROFILE_PAGE_TITLE,
    DEFAULT_RELEASE_PAGE_TITLE,
    PROFILE_TEMPLATE,
    RELEASE_TEMPLATE,
)
from autodoc.cli.context import CliCtx
from autodoc.cli.helpers import (
    _load_parsed_data,
    _make_publisher,
    _print_publish_result,
    console,
)
from autodoc.cli.commands.publish._quote_hint import _QuoteHintCommand


def _run_single_page_command(
    ctx: click.Context,
    *,
    strategy_type: str,
    template_name: str,
    default_title: str,
    panel_header: str,
    page_title: str | None,
    cli_root_page_id: str | None,
    cli_root_page_name: str | None,
    no_passport_links: bool,
) -> None:
    """Общая логика команд release и profile."""
    if cli_root_page_name and cli_root_page_id:
        raise click.UsageError(
            "Укажите только один флаг: --root-page-name или --root-page-id."
        )

    cli_ctx: CliCtx = ctx.obj

    try:
        console.print(
            Panel.fit(f"[bold blue]{panel_header}[/bold blue]", style="blue")
        )

        parsed_data = _load_parsed_data(cli_ctx.base_dir)
        console.print(
            f"✅ Данных: {len(parsed_data.components)} компонентов", style="green"
        )

        publisher, conf_config = _make_publisher(cli_ctx)
        final_title = page_title or conf_config.release_docs_page_title or default_title

        parent_id = publisher.resolve_page_id(
            cli_root_page_name or conf_config.release_docs_root_parent_name,
            cli_root_page_id or conf_config.release_docs_root_parent_id,
            "release_docs_root_parent",
            required=False,
        )

        console.print("🔄 Публикация в Confluence…", style="cyan")
        result = publisher.publish(
            strategy_type=strategy_type,
            parsed_data=parsed_data,
            page_title=final_title,
            template_name=template_name,
            parent_id=parent_id,
            include_passport_links=not no_passport_links,
        )

        _print_publish_result(result)

    except (ConfigError, DocGeneratorError, PublishError) as e:
        console.print(f"❌ Ошибка: {e}", style="red bold")
        sys.exit(1)


@click.command("release", cls=_QuoteHintCommand)
@click.option(
    "--page-title", default=None,
    help="Заголовок страницы (переопределяет release_docs_page_title из конфига)",
)
@click.option(
    "--root-page-id", "cli_root_page_id", default=None,
    help="ID корневой родительской страницы (переопределяет конфиг)",
)
@click.option(
    "--root-page-name", "cli_root_page_name", default=None,
    help=(
        "Название корневой родительской страницы (переопределяет конфиг). "
        'Если содержит пробелы — заключите в кавычки: --root-page-name "Моя страница"'
    ),
)
@click.option(
    "--no-passport-links", is_flag=True,
    help="Отключить ссылки на паспорта компонентов",
)
@click.pass_context
def publish_release(
    ctx: click.Context,
    page_title: str | None,
    cli_root_page_id: str | None,
    cli_root_page_name: str | None,
    no_passport_links: bool,
) -> None:
    """Публикация релизной документации."""
    _run_single_page_command(
        ctx,
        strategy_type="release",
        template_name=RELEASE_TEMPLATE,
        default_title=DEFAULT_RELEASE_PAGE_TITLE,
        panel_header="🚀 Публикация релизной документации",
        page_title=page_title,
        cli_root_page_id=cli_root_page_id,
        cli_root_page_name=cli_root_page_name,
        no_passport_links=no_passport_links,
    )


@click.command("profile", cls=_QuoteHintCommand)
@click.option(
    "--page-title", default=None,
    help="Заголовок страницы (переопределяет release_docs_page_title из конфига)",
)
@click.option(
    "--root-page-id", "cli_root_page_id", default=None,
    help="ID корневой родительской страницы (переопределяет конфиг)",
)
@click.option(
    "--root-page-name", "cli_root_page_name", default=None,
    help=(
        "Название корневой родительской страницы (переопределяет конфиг). "
        'Если содержит пробелы — заключите в кавычки: --root-page-name "Моя страница"'
    ),
)
@click.option(
    "--no-passport-links", is_flag=True,
    help="Отключить ссылки на паспорта компонентов",
)
@click.pass_context
def publish_profile(
    ctx: click.Context,
    page_title: str | None,
    cli_root_page_id: str | None,
    cli_root_page_name: str | None,
    no_passport_links: bool,
) -> None:
    """Публикация документации в представлении от профилей сборки."""
    _run_single_page_command(
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
