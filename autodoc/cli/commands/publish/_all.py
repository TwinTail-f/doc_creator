"""Группа publish и команда publish all."""
import sys

import click
from rich.panel import Panel

from autodoc.exceptions import ConfigError, DocGeneratorError, PublishError
from autodoc.cli.constants import (
    DEFAULT_RELEASE_PAGE_TITLE,
    PASSPORT_TEMPLATE,
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
from autodoc.cli.commands.publish._release import publish_release, publish_profile
from autodoc.cli.commands.publish._passports import publish_passports


@click.group()
def publish() -> None:
    """Публикация документации в Confluence."""


publish.add_command(publish_release)
publish.add_command(publish_profile)
publish.add_command(publish_passports)


@publish.command("all", cls=_QuoteHintCommand)
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
@click.option(
    "--release-root-page-id", "release_root_page_id", default=None,
    help="ID корневой родительской страницы релизной документации (переопределяет конфиг)",
)
@click.option(
    "--release-root-page-name", "release_root_page_name", default=None,
    help=(
        "Название корневой родительской страницы релизной документации (переопределяет конфиг). "
        'Если содержит пробелы — заключите в кавычки: --release-root-page-name "Моя страница"'
    ),
)
@click.option(
    "--release-doc-page-name", "release_doc_page_name", default=None,
    help=(
        "Заголовок страницы релизной документации "
        "(переопределяет release_docs_page_title из конфига)"
    ),
)
@click.option(
    "--with-additional-page-profile", "with_additional_page_profile", is_flag=True,
    help=(
        "Опубликовать дополнительную страницу в представлении от профилей сборки. "
        "Публикуется как дочерняя страница по отношению к странице релизной документации."
    ),
)
@click.option(
    "--additional-page-profile-name", "additional_page_profile_name", default=None,
    help=(
        "Заголовок дополнительной страницы профилей. "
        "Требует флага --with-additional-page-profile. "
        'Если содержит пробелы — заключите в кавычки: --additional-page-profile-name "Моя страница"'
    ),
)
@click.option(
    "--no-passport-links", is_flag=True,
    help="Не вставлять ссылки на паспорта в страницы документации",
)
@click.pass_context
def publish_all(
    ctx: click.Context,
    passports_root_parent_id: str | None,
    passports_root_parent_name: str | None,
    release_root_page_id: str | None,
    release_root_page_name: str | None,
    release_doc_page_name: str | None,
    with_additional_page_profile: bool,
    additional_page_profile_name: str | None,
    no_passport_links: bool,
) -> None:
    """Публикация паспортов, релизной документации и опционально страницы профилей за один вызов."""
    if passports_root_parent_name and passports_root_parent_id:
        raise click.UsageError(
            "Укажите только один флаг: --passports-root-parent-name или --passports-root-parent-id."
        )
    if release_root_page_name and release_root_page_id:
        raise click.UsageError(
            "Укажите только один флаг: --release-root-page-name или --release-root-page-id."
        )
    if additional_page_profile_name and not with_additional_page_profile:
        raise click.UsageError(
            "Флаг --additional-page-profile-name требует указания флага --with-additional-page-profile."
        )

    cli_ctx: CliCtx = ctx.obj

    try:
        console.print(
            Panel.fit(
                "[bold blue]🚀 Публикация: паспорта + релиз[/bold blue]",
                style="blue",
            )
        )

        publisher, conf_config = _make_publisher(cli_ctx)
        parsed_data = _load_parsed_data(cli_ctx.base_dir)

        final_title = (
            release_doc_page_name
            or conf_config.release_docs_page_title
            or DEFAULT_RELEASE_PAGE_TITLE
        )

        cli_passports_root: str | None = None
        if passports_root_parent_name or passports_root_parent_id:
            cli_passports_root = publisher.resolve_page_id(
                passports_root_parent_name or conf_config.passports_root_parent_name,
                passports_root_parent_id or conf_config.passports_root_parent_id,
                "passports_root_parent",
            )

        cli_release_parent: str | None = None
        if release_root_page_name or release_root_page_id:
            cli_release_parent = publisher.resolve_page_id(
                release_root_page_name or conf_config.release_docs_root_parent_name,
                release_root_page_id or conf_config.release_docs_root_parent_id,
                "release_docs_root_parent",
                required=False,
            )

        console.print("🔄 Публикация…", style="cyan")
        result = publisher.publish_all(
            parsed_data=parsed_data,
            passports_root_page_id=cli_passports_root,
            release_parent_id=cli_release_parent,
            release_page_title=final_title,
            release_template_name=RELEASE_TEMPLATE,
            passport_template_name=PASSPORT_TEMPLATE,
            include_passport_links=not no_passport_links,
            with_additional_page_profile=with_additional_page_profile,
            additional_page_profile_name=additional_page_profile_name,
            profile_template_name=PROFILE_TEMPLATE,
        )

        console.print(
            f"  Страниц опубликовано: {result.pages_published}",
            style="dim",
        )
        _print_publish_result(result)

    except (ConfigError, DocGeneratorError, PublishError) as e:
        console.print(f"❌ Ошибка: {e}", style="red bold")
        sys.exit(1)
