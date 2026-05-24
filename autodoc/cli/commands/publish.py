import sys

import click
from rich.panel import Panel

from autodoc.exceptions import ConfigError, DocGeneratorError, PublishError
from autodoc.cli.constants import (
    RELEASE_TEMPLATE,
    PROFILE_TEMPLATE,
    PASSPORT_TEMPLATE,
    DEFAULT_RELEASE_PAGE_TITLE,
    DEFAULT_PROFILE_PAGE_TITLE,
)
from autodoc.cli.context import CliCtx
from autodoc.cli.helpers import (
    console,
    _load_parsed_data,
    _make_publisher,
    _print_publish_result,
)


@click.group()
def publish() -> None:
    """Публикация документации в Confluence."""


@publish.command("release")
@click.option(
    "--page-title", default=None, help="Заголовок страницы (переопределяет конфиг)"
)
@click.option(
    "--no-passport-links",
    is_flag=True,
    help="Отключить ссылки на паспорта компонентов",
)
@click.pass_context
def publish_release(
    ctx: click.Context,
    page_title: str | None,
    no_passport_links: bool,
) -> None:
    """Публикация релизной документации."""
    cli_ctx: CliCtx = ctx.obj

    try:
        console.print(
            Panel.fit(
                "[bold blue]🚀 Публикация релизной документации[/bold blue]",
                style="blue",
            )
        )

        parsed_data = _load_parsed_data(cli_ctx.base_dir)
        console.print(
            f"✅ Данных: {len(parsed_data.components)} компонентов", style="green"
        )

        publisher, conf_config = _make_publisher(cli_ctx)
        final_title = (
            page_title or conf_config.page_title or DEFAULT_RELEASE_PAGE_TITLE
        )

        console.print("🔄 Публикация в Confluence…", style="cyan")
        result = publisher.publish(
            strategy_type="release",
            parsed_data=parsed_data,
            page_title=final_title,
            template_name=RELEASE_TEMPLATE,
            parent_id=conf_config.parent_id,
            include_passport_links=not no_passport_links,
        )

        _print_publish_result(result)

    except (ConfigError, DocGeneratorError, PublishError) as e:
        console.print(f"❌ Ошибка: {e}", style="red bold")
        sys.exit(1)


@publish.command("profile")
@click.option(
    "--page-title", default=None, help="Заголовок страницы (переопределяет конфиг)"
)
@click.option(
    "--no-passport-links",
    is_flag=True,
    help="Отключить ссылки на паспорта компонентов",
)
@click.pass_context
def publish_profile(
    ctx: click.Context,
    page_title: str | None,
    no_passport_links: bool,
) -> None:
    """Публикация документации от профилей сборки."""
    cli_ctx: CliCtx = ctx.obj

    try:
        console.print(
            Panel.fit(
                "[bold blue]🚀 Публикация документации от профилей[/bold blue]",
                style="blue",
            )
        )

        parsed_data = _load_parsed_data(cli_ctx.base_dir)
        console.print(
            f"✅ Данных: {len(parsed_data.components)} компонентов", style="green"
        )

        publisher, conf_config = _make_publisher(cli_ctx)
        final_title = (
            page_title or conf_config.page_title or DEFAULT_PROFILE_PAGE_TITLE
        )

        console.print("🔄 Публикация в Confluence…", style="cyan")
        result = publisher.publish(
            strategy_type="profile_centric",
            parsed_data=parsed_data,
            page_title=final_title,
            template_name=PROFILE_TEMPLATE,
            parent_id=conf_config.parent_id,
            include_passport_links=not no_passport_links,
        )

        _print_publish_result(result)

    except (ConfigError, DocGeneratorError, PublishError) as e:
        console.print(f"❌ Ошибка: {e}", style="red bold")
        sys.exit(1)


@publish.command("passports")
@click.option(
    "--root-page", default=None, help="ID корневой страницы иерархии паспортов"
)
@click.pass_context
def publish_passports(ctx: click.Context, root_page: str | None) -> None:
    """Публикация паспортов компонентов (иерархия страниц)."""
    cli_ctx: CliCtx = ctx.obj

    try:
        console.print(
            Panel.fit(
                "[bold blue]🚀 Публикация паспортов компонентов[/bold blue]",
                style="blue",
            )
        )

        publisher, conf_config = _make_publisher(cli_ctx)
        target_root = root_page or conf_config.passports_root_parent_id
        if not target_root:
            console.print(
                "❌ ID корневой страницы не указан. Передайте --root-page "
                "или добавьте passports_root_parent_id в конфиг.",
                style="red bold",
            )
            sys.exit(1)

        parsed_data = _load_parsed_data(cli_ctx.base_dir)

        console.print("🔄 Публикация паспортов… (может занять время)", style="cyan")
        result = publisher.publish(
            strategy_type="passports",
            parsed_data=parsed_data,
            root_page_id=target_root,
            template_name=PASSPORT_TEMPLATE,
            batch_size=conf_config.publish_batch_size,
            batch_delay_seconds=conf_config.publish_batch_delay_seconds,
            target_release_version=conf_config.target_release_version,
        )

        _print_publish_result(result)

    except (ConfigError, DocGeneratorError, PublishError) as e:
        console.print(f"❌ Ошибка: {e}", style="red bold")
        sys.exit(1)


@publish.command("all")
@click.option("--root-page", default=None, help="ID корневой страницы паспортов")
@click.option("--page-title", default=None, help="Заголовок итоговой страницы релиза")
@click.option(
    "--no-passport-links",
    is_flag=True,
    help="Не добавлять ссылки на паспорта в релизную страницу",
)
@click.pass_context
def publish_all(
    ctx: click.Context,
    root_page: str | None,
    page_title: str | None,
    no_passport_links: bool,
) -> None:
    """
    Опубликовать паспорта + релизную страницу за один вызов.

    Сначала публикуются паспорта (генерируется карта ID),
    затем релизная страница с внедрёнными ссылками на паспорта.
    """
    cli_ctx: CliCtx = ctx.obj

    try:
        console.print(
            Panel.fit(
                "[bold blue]🚀 Публикация: паспорта + релиз[/bold blue]",
                style="blue",
            )
        )

        publisher, conf_config = _make_publisher(cli_ctx)
        target_root = root_page or conf_config.passports_root_parent_id
        if not target_root:
            console.print(
                "❌ ID корневой страницы не указан для паспортов. "
                "Передайте --root-page или добавьте passports_root_parent_id в конфиг.",
                style="red bold",
            )
            sys.exit(1)

        parsed_data = _load_parsed_data(cli_ctx.base_dir)
        final_title = (
            page_title or conf_config.page_title or DEFAULT_RELEASE_PAGE_TITLE
        )

        console.print("🔄 Публикация…", style="cyan")
        result = publisher.publish_all(
            parsed_data=parsed_data,
            passports_root_page_id=target_root,
            release_page_title=final_title,
            release_template_name=RELEASE_TEMPLATE,
            passport_template_name=PASSPORT_TEMPLATE,
            release_parent_id=conf_config.parent_id,
            include_passport_links=not no_passport_links,
        )

        console.print(
            f"  Страниц опубликовано: {result.pages_published}",
            style="dim",
        )
        _print_publish_result(result)

    except (ConfigError, DocGeneratorError, PublishError) as e:
        console.print(f"❌ Ошибка: {e}", style="red bold")
        sys.exit(1)
