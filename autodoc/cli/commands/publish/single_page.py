"""Общая логика и опции команд публикации одной страницы (release, profile)."""
import functools
from typing import Callable

import click

from autodoc.cli.context import CliCtx
from autodoc.cli.helpers import (
    cli_error_boundary,
    console,
    load_parsed_data,
    make_publisher,
    print_publish_result,
    require_exclusive,
)

_ROOT_PAGE_NAME_FLAG: str = "--root-page-name"
_ROOT_PAGE_ID_FLAG: str = "--root-page-id"


def single_page_options(f: Callable) -> Callable:
    """Декоратор: добавляет к команде общий набор Click-опций для публикации одной страницы.

    Команды ``publish release`` и ``publish profile`` принимают одинаковый
    набор флагов (``--page-title``, ``--root-page-id`` и т.д.) — вынесен
    сюда, чтобы не дублировать одинаковые ``@click.option`` в обоих файлах.

    Args:
        f: Функция Click-команды, к которой применяются опции.

    Returns:
        Та же функция, обёрнутая декораторами ``click.option``.
    """
    decorators = [
        click.option(
            "--page-title", default=None,
            help="Заголовок страницы (переопределяет release_docs_page_title из конфига)",
        ),
        click.option(
            "--root-page-id", "cli_root_page_id", default=None,
            help="ID корневой родительской страницы (переопределяет конфиг)",
        ),
        click.option(
            "--root-page-name", "cli_root_page_name", default=None,
            help=(
                "Название корневой родительской страницы (переопределяет конфиг). "
                'Если содержит пробелы — заключите в кавычки: --root-page-name "Моя страница"'
            ),
        ),
        click.option(
            "--no-passport-links", is_flag=True,
            help="Отключить ссылки на паспорта компонентов",
        ),
    ]
    return functools.reduce(lambda fn, dec: dec(fn), reversed(decorators), f)


def run_single_page_command(
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
    """Общая логика команд release и profile.

    Args:
        ctx: Контекст Click-команды.
        strategy_type: Тип стратегии публикации (``'release'`` или ``'profile_centric'``).
        template_name: Имя Jinja2-шаблона.
        default_title: Заголовок страницы по умолчанию, если он не задан ни флагом,
                       ни конфигурацией.
        panel_header: Текст заголовка панели, отображаемой при запуске команды.
        page_title: Заголовок страницы, заданный через CLI, либо ``None``.
        cli_root_page_id: ID корневой родительской страницы, заданный через CLI.
        cli_root_page_name: Название корневой родительской страницы, заданное через CLI.
        no_passport_links: Если ``True`` — отключает вставку ссылок на паспорта.
    """
    require_exclusive(
        cli_root_page_name,
        cli_root_page_id,
        name_flag=_ROOT_PAGE_NAME_FLAG,
        id_flag=_ROOT_PAGE_ID_FLAG,
    )

    cli_ctx: CliCtx = ctx.obj

    with cli_error_boundary(panel_header):
        parsed_data = load_parsed_data(cli_ctx.base_dir)
        console.print(
            f"✅ Данных: {len(parsed_data.components)} компонентов", style="green"
        )

        publisher, conf_config = make_publisher(cli_ctx)
        if strategy_type == "release":
            final_title = (
                page_title or conf_config.release_docs_page_title or default_title
            )
        else:
            final_title = (
                page_title or conf_config.profile_docs_page_title or default_title
            )

        console.print("🔄 Публикация в Confluence…", style="cyan")
        result = publisher.publish_single_page(
            strategy_type=strategy_type,
            parsed_data=parsed_data,
            page_title=final_title,
            template_name=template_name,
            root_page_name=cli_root_page_name,
            root_page_id=cli_root_page_id,
            include_passport_links=not no_passport_links,
        )

        print_publish_result(result)
