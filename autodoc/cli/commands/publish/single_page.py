"""Общая логика и опции команд публикации одной страницы (release, profile, kit-*)."""

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
)
from autodoc.exceptions import DocGeneratorError
from autodoc.publisher.strategies import registry

# Опции, общие для ВСЕХ команд публикации одной страницы, независимо от того,
# поддерживает ли конкретная стратегия ссылки на паспорта.
_COMMON_SINGLE_PAGE_OPTIONS: list[Callable] = [
    click.option(
        "--page-title",
        default=None,
        help="Заголовок страницы (переопределяет strategies.<strategy_type>.page_title из конфига)",
    ),
    click.option(
        "--root-page-id",
        "cli_root_page_id",
        default=None,
        help="ID корневой родительской страницы (переопределяет конфиг)",
    ),
    click.option(
        "--root-page-name",
        "cli_root_page_name",
        default=None,
        help=(
            "Название корневой родительской страницы (переопределяет конфиг). "
            'Если содержит пробелы — заключите в кавычки: --root-page-name "Моя страница"'
        ),
    ),
]


def single_page_options(f: Callable) -> Callable:
    """Декоратор: добавляет к команде общий набор Click-опций для публикации одной страницы.

    Команды ``publish release`` и ``publish profile`` принимают одинаковый
    набор флагов, включая ``--no-passport-links`` — их конвертеры умеют
    показывать ссылки на паспорта компонентов, и это поведение можно отключить.

    Args:
        f: Функция Click-команды, к которой применяются опции.

    Returns:
        Та же функция, обёрнутая декораторами ``click.option``.
    """
    decorators = [
        *_COMMON_SINGLE_PAGE_OPTIONS,
        click.option(
            "--no-passport-links",
            is_flag=True,
            help="Отключить ссылки на паспорта компонентов",
        ),
    ]
    return functools.reduce(lambda fn, dec: dec(fn), reversed(decorators), f)


def kit_page_options(f: Callable) -> Callable:
    """Декоратор: добавляет к команде набор Click-опций для страниц «комплекта
    встраивания» (``kit-fixed``, ``kit-latest``).

    В отличие от ``single_page_options``, здесь нет флага ``--no-passport-links``:
    эти страницы — простые списки Conan-ссылок и не имеют понятия ссылок на
    паспорта компонентов (см. ``KitFixedConverter``/``KitLatestConverter``,
    у которых ``wants_passport_links`` всегда ``False``).

    Args:
        f: Функция Click-команды, к которой применяются опции.

    Returns:
        Та же функция, обёрнутая декораторами ``click.option``.
    """
    return functools.reduce(lambda fn, dec: dec(fn), reversed(_COMMON_SINGLE_PAGE_OPTIONS), f)


def _run_publish_single_page_command(
    ctx: click.Context,
    *,
    strategy_type: str,
    template_name: str,
    default_title: str,
    panel_header: str,
    page_title: str | None,
    cli_root_page_id: str | None,
    cli_root_page_name: str | None,
    include_passport_links: bool,
) -> None:
    """Общая логика всех команд публикации одной страницы (release, profile,
    kit-fixed, kit-latest).

    Загружает данные, резолвит финальный заголовок страницы и публикует её
    через выбранную стратегию. Единственное, чем отличаются друг от друга
    вызывающие эту функцию команды, — какой ``strategy_type`` и какое
    значение ``include_passport_links`` они передают; для strategy_type,
    чей конвертер не поддерживает ссылки на паспорта (kit_fixed, kit_latest),
    значение include_passport_links ни на что не влияет — оно тихо
    отбрасывается на уровне стратегии (см. ``KitFixedPageStrategy``).

    Args:
        ctx: Контекст Click-команды.
        strategy_type: Тип стратегии публикации (ключ из ``registry.STRATEGIES``).
        template_name: Имя Jinja2-шаблона.
        default_title: Заголовок страницы по умолчанию, если он не задан ни флагом,
                       ни конфигурацией.
        panel_header: Текст заголовка панели, отображаемой при запуске команды.
        page_title: Заголовок страницы, заданный через CLI, либо ``None``.
        cli_root_page_id: ID корневой родительской страницы, заданный через CLI.
        cli_root_page_name: Название корневой родительской страницы, заданное через CLI.
        include_passport_links: Вставлять ли ссылки на паспорта компонентов
            (для strategy_type, которые их не поддерживают, значение игнорируется).

    Raises:
        DocGeneratorError: Если ``strategy_type`` не зарегистрирован в
            ``registry.STRATEGIES``, либо зарегистрирован, но не является
            одностраничной стратегией (например ``'passports'``).
    """
    cli_ctx: CliCtx = ctx.obj

    with cli_error_boundary(panel_header):
        if not registry.is_single_page_strategy(strategy_type):
            raise DocGeneratorError(
                f"Внутренняя ошибка: неизвестный тип стратегии публикации {strategy_type!r}. "
                f"Поддерживаются: {registry.single_page_strategy_types()}. "
                "Публикация остановлена, чтобы не создать страницу не в том режиме. "
                "Сообщите об этом разработчику."
            )

        parsed_data = load_parsed_data(cli_ctx.base_dir)
        console.print(f"✅ Данных: {len(parsed_data.components)} компонентов", style="green")

        publisher, confluence_config = make_publisher(cli_ctx)
        strategy_fields = getattr(confluence_config.strategies, strategy_type)
        final_title = page_title or strategy_fields.page_title or default_title

        console.print("🔄 Публикация в Confluence…", style="cyan")
        result = publisher.publish_single_page(
            strategy_type=strategy_type,
            parsed_data=parsed_data,
            page_title=final_title,
            template_name=template_name,
            root_page_name=cli_root_page_name,
            root_page_id=cli_root_page_id,
            include_passport_links=include_passport_links,
        )

        print_publish_result(result)


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
    """Точка входа команд ``publish release`` и ``publish profile``.

    Тонкая обёртка над ``_run_publish_single_page_command``: переводит флаг
    CLI ``--no-passport-links`` в ``include_passport_links``.

    Args:
        ctx: Контекст Click-команды.
        strategy_type: Тип стратегии публикации (``'release'`` или ``'profile_centric'``).
        template_name: Имя Jinja2-шаблона.
        default_title: Заголовок страницы по умолчанию.
        panel_header: Текст заголовка панели, отображаемой при запуске команды.
        page_title: Заголовок страницы, заданный через CLI, либо ``None``.
        cli_root_page_id: ID корневой родительской страницы, заданный через CLI.
        cli_root_page_name: Название корневой родительской страницы, заданное через CLI.
        no_passport_links: Если ``True`` — отключает вставку ссылок на паспорта.
    """
    _run_publish_single_page_command(
        ctx,
        strategy_type=strategy_type,
        template_name=template_name,
        default_title=default_title,
        panel_header=panel_header,
        page_title=page_title,
        cli_root_page_id=cli_root_page_id,
        cli_root_page_name=cli_root_page_name,
        include_passport_links=not no_passport_links,
    )


def run_kit_page_command(
    ctx: click.Context,
    *,
    strategy_type: str,
    template_name: str,
    default_title: str,
    panel_header: str,
    page_title: str | None,
    cli_root_page_id: str | None,
    cli_root_page_name: str | None,
) -> None:
    """Точка входа команд ``publish kit-fixed`` и ``publish kit-latest``.

    Тонкая обёртка над ``_run_publish_single_page_command``: у этих команд
    нет флага ``--no-passport-links`` (см. ``kit_page_options``), поэтому
    ``include_passport_links`` жёстко ``False`` — впрочем, для этих
    strategy_type значение всё равно ни на что не влияет.

    Args:
        ctx: Контекст Click-команды.
        strategy_type: Тип стратегии публикации (``'kit_fixed'`` или ``'kit_latest'``).
        template_name: Имя Jinja2-шаблона.
        default_title: Заголовок страницы по умолчанию.
        panel_header: Текст заголовка панели, отображаемой при запуске команды.
        page_title: Заголовок страницы, заданный через CLI, либо ``None``.
        cli_root_page_id: ID корневой родительской страницы, заданный через CLI.
        cli_root_page_name: Название корневой родительской страницы, заданное через CLI.
    """
    _run_publish_single_page_command(
        ctx,
        strategy_type=strategy_type,
        template_name=template_name,
        default_title=default_title,
        panel_header=panel_header,
        page_title=page_title,
        cli_root_page_id=cli_root_page_id,
        cli_root_page_name=cli_root_page_name,
        include_passport_links=False,
    )
