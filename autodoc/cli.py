"""
Click CLI для запуска парсера и паблишера документации компонентов.

Команды:
    parse               — сбор данных компонентов из TFS + Conan + Docker
    publish release     — публикация единой страницы релиза в Confluence
    publish passports   — публикация паспортов компонентов в Confluence
    publish all         — паспорта + итоговая страница за один вызов
    config list         — список доступных конфиг-файлов
    config validate     — валидация конфиг-файла
    info                — версия и сводка возможностей
"""

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from autodoc.config.manager import ConfigManager
from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.exceptions import ConfigError, DocGeneratorError, PublishError
from autodoc.infrastructure.logger import logger
from autodoc.models.parsed_result import ParsedResult
from autodoc.parser.parser import ComponentParser
from autodoc.parser.steps.conan_step import ConanEnrichStep
from autodoc.parser.steps.validation_step import ArtifactoryValidationStep
from autodoc.publisher.publisher import DocumentPublisher
from autodoc.models.publish_report import PublishReport

console = Console()


_VERSION = "2.0.0"
_RELEASE_TEMPLATE = "release_doc.jinja2"
_PROFILE_TEMPLATE = "profile_centric.jinja2"
_PASSPORT_TEMPLATE = "component_passport.jinja2"
_DEFAULT_RELEASE_PAGE_TITLE: str = "Release Documentation"
_DEFAULT_PROFILE_PAGE_TITLE: str = "Profile Documentation"


class _CliCtx:
    """Контекст, разделяемый между командами Click."""

    def __init__(self, base_dir: Path, configs_dir: Path, verbose: bool) -> None:
        self.base_dir = base_dir
        self.configs_dir = configs_dir
        self.verbose = verbose
        self.config_manager = ConfigManager(str(configs_dir))


# ---------------------------------------------------------------------------
# Корневая группа
# ---------------------------------------------------------------------------


@click.group(invoke_without_command=True)
@click.option(
    "--base-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=".",
    show_default=True,
    help="Базовая директория проекта",
)
@click.option(
    "--configs-dir",
    type=click.Path(file_okay=False, dir_okay=True),
    default=None,
    help="Директория с конфигами (по умолчанию <base-dir>/configs)",
)
@click.option("-v", "--verbose", is_flag=True, help="Подробный вывод логов")
@click.pass_context
def cli(
    ctx: click.Context, base_dir: str, configs_dir: str | None, verbose: bool
) -> None:
    """
    Doc Generator CLI — инструмент сбора и публикации документации компонентов платформы.

    \b
    Примеры:
        doc-generator parse
        doc-generator parse --skip-conan --save-intermediate
        doc-generator publish all
        doc-generator config list
    """
    base = Path(base_dir).resolve()
    cfgs = Path(configs_dir).resolve() if configs_dir else base / "configs"

    if not cfgs.exists():
        console.print(f"❌ Директория конфигов не найдена: {cfgs}", style="red bold")
        sys.exit(1)

    ctx.ensure_object(dict)
    ctx.obj["cli"] = _CliCtx(base, cfgs, verbose)

    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


# ---------------------------------------------------------------------------
# Команда: parse
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--config", default=None, help="Имя файла конфига парсера")
@click.option(
    "--save-intermediate",
    is_flag=True,
    help="Сохранять JSON-снимок после каждого шага пайплайна",
)
@click.option(
    "--skip-conan",
    is_flag=True,
    help="Пропустить шаг Conan graph info",
)
@click.option(
    "--skip-validation",
    is_flag=True,
    help="Пропустить шаг валидации ссылок Artifactory",
)
@click.pass_context
def parse(
    ctx: click.Context,
    config: str | None,
    save_intermediate: bool,
    skip_conan: bool,
    skip_validation: bool,
) -> None:
    """
    Запустить парсер для сбора данных компонентов.

    Скачивает манифесты, собирает options, запускает Conan graph info,
    получает Docker-ссылки и сохраняет результат в data/parsed_data.json.
    """
    cli_ctx: _CliCtx = ctx.obj["cli"]

    try:
        console.print(
            Panel.fit(
                "[bold blue]🚀 Запуск парсера документации[/bold blue]",
                style="blue",
            )
        )

        console.print("📋 Загрузка конфигурации…", style="cyan")
        parser_config = cli_ctx.config_manager.load_parser_config(config)
        if parser_config is None:
            raise ConfigError(
                f"Не удалось загрузить конфигурацию парсера: "
                f"файл не найден или содержит ошибки валидации."
            )
        console.print(
            f"✅ Конфигурация загружена (платформа: {parser_config.platform_version})",
            style="green",
        )

        data_dir = cli_ctx.base_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        # Кастомный пайплайн если нужно пропустить шаги
        if skip_conan or skip_validation:
            exclude = []
            if skip_conan:
                exclude.append(ConanEnrichStep)
            if skip_validation:
                exclude.append(ArtifactoryValidationStep)
            parser = ComponentParser.with_steps_excluded(
                parser_config, data_dir, exclude
            )
            skipped = [cls.__name__ for cls in exclude]
            console.print(
                f"⚠️  Пропущены шаги: {", ".join(skipped)}",
                style="yellow",
            )
        else:
            parser = ComponentParser(parser_config, data_dir)

        console.print("🔄 Запуск пайплайна…", style="cyan")
        result = parser.parse(save_intermediate=save_intermediate)

        # Сохраняем финальный результат
        output_file = data_dir / "parsed_data.json"
        output_file.write_text(result.model_dump_json(indent=2), encoding="utf-8")

        console.print(
            Panel.fit(
                f"[bold green]✅ Парсер завершил работу успешно![/bold green]\n"
                f"Компонентов: {len(result.components)}\n"
                f"Результат: {output_file}",
                style="green",
            )
        )

    except ConfigError as e:
        console.print(f"❌ Ошибка конфигурации: {e}", style="red bold")
        sys.exit(1)
    except DocGeneratorError as e:
        console.print(f"❌ Ошибка обработки: {e}", style="red bold")
        sys.exit(1)


@cli.group()
def publish() -> None:
    """Публикация документации в Confluence."""


def _load_parsed_data(base_dir: Path) -> ParsedResult:
    """Загружает parsed_data.json и десериализует в ParsedResult."""
    data_file = base_dir / "data" / "parsed_data.json"
    if not data_file.exists():
        console.print(
            "❌ Файл parsed_data.json не найден. Сначала запустите " '"parse".',
            style="red bold",
        )
        sys.exit(1)
    return ParsedResult.model_validate_json(data_file.read_text(encoding="utf-8"))


def _make_publisher(
    cli_ctx: _CliCtx,
    config_file: str | None = None,
) -> tuple[DocumentPublisher, ConfluenceConfigSchema]:
    """Создаёт DocumentPublisher и возвращает его вместе с конфигом."""
    conf_config = cli_ctx.config_manager.load_confluence_config(config_file)
    rendering_dir = cli_ctx.base_dir / "autodoc" / "publisher" / "rendering"
    return DocumentPublisher(conf_config, rendering_dir), conf_config


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
    """Публикация релизной документации (вид от компонентов)."""
    cli_ctx: _CliCtx = ctx.obj["cli"]

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
            page_title or conf_config.page_title or _DEFAULT_RELEASE_PAGE_TITLE
        )

        console.print("🔄 Публикация в Confluence…", style="cyan")
        result = publisher.publish(
            strategy_type="release",
            parsed_data=parsed_data,
            page_title=final_title,
            template_name=_RELEASE_TEMPLATE,
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
    cli_ctx: _CliCtx = ctx.obj["cli"]

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
            page_title or conf_config.page_title or _DEFAULT_PROFILE_PAGE_TITLE
        )

        console.print("🔄 Публикация в Confluence…", style="cyan")
        result = publisher.publish(
            strategy_type="profile_centric",
            parsed_data=parsed_data,
            page_title=final_title,
            template_name=_PROFILE_TEMPLATE,
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
    cli_ctx: _CliCtx = ctx.obj["cli"]

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
            template_name=_PASSPORT_TEMPLATE,
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
    cli_ctx: _CliCtx = ctx.obj["cli"]

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
            page_title or conf_config.page_title or _DEFAULT_RELEASE_PAGE_TITLE
        )

        console.print("🔄 Публикация…", style="cyan")
        result = publisher.publish_all(
            parsed_data=parsed_data,
            passports_root_page_id=target_root,
            release_page_title=final_title,
            release_template_name=_RELEASE_TEMPLATE,
            passport_template_name=_PASSPORT_TEMPLATE,
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


# ---------------------------------------------------------------------------
# Группа: config
# ---------------------------------------------------------------------------


@cli.group()
def config() -> None:
    """Управление конфигурационными файлами."""


@config.command("list")
@click.pass_context
def config_list(ctx: click.Context) -> None:
    """Список доступных конфигурационных файлов."""
    cli_ctx: _CliCtx = ctx.obj["cli"]

    available = cli_ctx.config_manager.list_available_configs()

    console.print(Panel.fit("[bold]Доступные конфигурации[/bold]", style="blue"))

    for fmt, files in available.items():
        if files:
            table = Table(title=f"{fmt.upper()} конфигурации", show_header=True)
            table.add_column("Файл", style="cyan")
            for fname in files:
                table.add_row(fname)
            console.print(table)
        else:
            console.print(f"{fmt.upper()} конфиги: [yellow]не найдены[/yellow]")


@config.command("validate")
@click.argument("config-file")
@click.pass_context
def config_validate(ctx: click.Context, config_file: str) -> None:
    """Валидировать синтаксис конфигурационного файла."""
    from pydantic import ValidationError as PydanticValidationError
    from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
    from autodoc.config.schemas.parser_config import ParserConfigSchema

    cli_ctx: _CliCtx = ctx.obj["cli"]

    filepath = cli_ctx.configs_dir / config_file
    is_valid, error = cli_ctx.config_manager.validate_config_file(str(filepath))

    if not is_valid:
        console.print(f"❌ Файл невалиден: {error}", style="red bold")
        sys.exit(1)

    console.print(f"✅ Синтаксис файла корректен: {config_file}", style="green bold")

    # Загружаем сырые данные один раз, до любой схемной валидации.
    try:
        raw = cli_ctx.config_manager.load_raw(config_file)
    except ConfigError as e:
        console.print(f"❌ Не удалось загрузить файл: {e}", style="red bold")
        sys.exit(1)

    # Определяем схему по наличию ключевых полей — не через перебор исключений.
    is_parser = "tfs_token" in raw and "platform_version" in raw
    is_confluence = "url" in raw and "token" in raw and "space" in raw

    if is_parser:
        try:
            ParserConfigSchema(**raw)
            console.print(
                "✅ Pydantic валидация пройдена (схема: parser)", style="green"
            )
        except PydanticValidationError as e:
            console.print(
                f"⚠️  Схема parser: файл загружается, но содержит ошибки валидации:\n{e}",
                style="yellow",
            )
    elif is_confluence:
        try:
            ConfluenceConfigSchema(**raw)
            console.print(
                "✅ Pydantic валидация пройдена (схема: confluence)", style="green"
            )
        except PydanticValidationError as e:
            console.print(
                f"⚠️  Схема confluence: файл загружается, но содержит ошибки валидации:\n{e}",
                style="yellow",
            )
    else:
        console.print(
            "⚠️  JSON/YAML синтаксически корректен, но не соответствует "
            "ни одной известной схеме.",
            style="yellow",
        )


# ---------------------------------------------------------------------------
# Команда: info
# ---------------------------------------------------------------------------


@cli.command()
def info() -> None:
    """Показать версию и список возможностей."""
    console.print(
        Panel(
            f"[bold cyan]Doc Generator v{_VERSION}[/bold cyan]\n\n"
            "✓ Автоматический сбор данных компонентов из TFS\n"
            "✓ Интеграция с Conan package manager\n"
            "✓ Получение Docker-ссылок из YAML профилей\n"
            "✓ Публикация паспортов компонентов (publish passports)\n"
            "✓ Публикация релизной документации от компонентов (publish release)\n"
            "✓ Публикация документации от профилей (publish profile)\n"
            "✓ Команда publish all (паспорта + релиз за один вызов)\n",
            title="Doc Generator",
            style="blue",
        )
    )


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


def _print_publish_result(result: PublishReport) -> None:
    """Выводит результат публикации в консоль."""
    if result.success:
        console.print(
            Panel.fit(
                f"[bold green]✅ Публикация завершена успешно![/bold green]\n"
                f"Страниц создано/обновлено: {result.pages_published}",
                style="green",
            )
        )
    else:
        console.print("⚠️  Публикация завершена с ошибками:", style="yellow bold")
        for err in result.errors:
            console.print(f"  • {err}", style="yellow")
        if result.pages_published == 0:
            sys.exit(1)


if __name__ == "__main__":
    cli(obj={})
