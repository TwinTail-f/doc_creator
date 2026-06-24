"""Группа publish и команда publish all."""
import click

from autodoc.cli.constants import (
    DEFAULT_PROFILE_PAGE_TITLE,
    DEFAULT_RELEASE_PAGE_TITLE,
    PASSPORT_TEMPLATE,
    PROFILE_TEMPLATE,
    RELEASE_TEMPLATE,
)
from autodoc.cli.context import CliCtx
from autodoc.cli.helpers import (
    cli_error_boundary,
    load_parsed_data,
    make_publisher,
    print_publish_result,
    require_exclusive,
    console,
)
from autodoc.cli.commands.publish.quote_hint import QuoteHintCommand
from autodoc.cli.commands.publish.release import publish_release
from autodoc.cli.commands.publish.profile import publish_profile
from autodoc.cli.commands.publish.passports import publish_passports


@click.group()
def publish() -> None:
    """Публикация документации в Confluence."""


publish.add_command(publish_release)
publish.add_command(publish_profile)
publish.add_command(publish_passports)


@publish.command("all", cls=QuoteHintCommand)
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
    "--release-root-page-id", "root_page_id", default=None,
    help="ID корневой родительской страницы релизной документации (переопределяет конфиг)",
)
@click.option(
    "--release-root-page-name", "root_page_name", default=None,
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
    root_page_id: str | None,
    root_page_name: str | None,
    release_doc_page_name: str | None,
    with_additional_page_profile: bool,
    additional_page_profile_name: str | None,
    no_passport_links: bool,
) -> None:
    """Публикация паспортов, релизной документации и опционально страницы профилей за один вызов."""
    require_exclusive(
        passports_root_parent_name,
        passports_root_parent_id,
        name_flag="--passports-root-parent-name",
        id_flag="--passports-root-parent-id",
    )
    require_exclusive(
        root_page_name,
        root_page_id,
        name_flag="--release-root-page-name",
        id_flag="--release-root-page-id",
    )
    if additional_page_profile_name and not with_additional_page_profile:
        raise click.UsageError(
            "Флаг --additional-page-profile-name требует указания флага --with-additional-page-profile."
        )

    cli_ctx: CliCtx = ctx.obj

    with cli_error_boundary("🚀 Публикация: паспорта + релиз"):
        publisher, conf_config = make_publisher(cli_ctx)
        parsed_data = load_parsed_data(cli_ctx.base_dir)

        final_title = (
            release_doc_page_name
            or conf_config.release_docs_page_title
            or DEFAULT_RELEASE_PAGE_TITLE
        )

        include_passport_links = not no_passport_links

        profile_title = (
            additional_page_profile_name or DEFAULT_PROFILE_PAGE_TITLE
            if with_additional_page_profile
            else None
        )

        console.print("🔄 Публикация…", style="cyan")
        result = publisher.publish_all(
            parsed_data=parsed_data,
            passports_root_parent_name=passports_root_parent_name,
            passports_root_parent_id=passports_root_parent_id,
            release_root_page_name=root_page_name,
            release_root_page_id=root_page_id,
            release_page_title=final_title,
            release_template_name=RELEASE_TEMPLATE,
            passport_template_name=PASSPORT_TEMPLATE,
            include_passport_links=include_passport_links,
            profile_title=profile_title,
            profile_template_name=PROFILE_TEMPLATE if with_additional_page_profile else None,
        )

        console.print(
            f"  Страниц опубликовано: {result.pages_published}",
            style="dim",
        )
        print_publish_result(result)
