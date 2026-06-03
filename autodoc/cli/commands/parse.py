import sys

import click
from rich.panel import Panel

from autodoc.exceptions import ConfigError, NetworkError, ParsingError
from autodoc.parser.parser import ComponentParser
from autodoc.parser.steps.conan_step import ConanEnrichStep
from autodoc.parser.steps.validation_step import ArtifactoryValidationStep
from autodoc.cli.context import CliCtx
from autodoc.cli.helpers import console


def _load_config(cli_ctx: CliCtx, config: str | None):
    """Загружает конфигурацию парсера. Завершает процесс при ошибке."""
    parser_config = cli_ctx.config_manager.load_parser_config(config)
    if parser_config is None:
        raise ConfigError(
            "Не удалось загрузить конфигурацию парсера: "
            "файл не найден или содержит ошибки валидации."
        )
    console.print(
        f"✅ Конфигурация загружена (платформа: {parser_config.platform_version})",
        style="green",
    )
    return parser_config


def _build_parser(
    parser_config,
    data_dir,
    skip_conan: bool,
    skip_validation: bool,
) -> ComponentParser:
    """Собирает пайплайн парсера, опционально исключая шаги."""
    if not skip_conan and not skip_validation:
        return ComponentParser(parser_config, data_dir)

    exclude = []
    if skip_conan:
        exclude.append(ConanEnrichStep)
    if skip_validation:
        exclude.append(ArtifactoryValidationStep)

    skipped = [cls.__name__ for cls in exclude]
    console.print(f"⚠️  Пропущены шаги: {', '.join(skipped)}", style="yellow")
    return ComponentParser.with_steps_excluded(parser_config, data_dir, exclude)


@click.command()
@click.option("--config", default=None, help="Имя файла конфига парсера")
@click.option(
    "--save-intermediate",
    is_flag=True,
    help="Сохранять JSON-снимок после каждого шага пайплайна",
)
@click.option("--skip-conan", is_flag=True, help="Пропустить шаг Conan graph info")
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
    cli_ctx: CliCtx = ctx.obj

    console.print(
        Panel.fit("[bold blue]🚀 Запуск парсера документации[/bold blue]", style="blue")
    )

    # Загрузка конфигурации — бросает ConfigError при отсутствии или невалидном файле
    console.print("📋 Загрузка конфигурации…", style="cyan")
    try:
        parser_config = _load_config(cli_ctx, config)
    except ConfigError as e:
        console.print(f"❌ Ошибка конфигурации: {e}", style="red bold")
        sys.exit(1)

    data_dir = cli_ctx.base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    parser = _build_parser(parser_config, data_dir, skip_conan, skip_validation)

    # Запуск пайплайна — бросает NetworkError (TFS/Artifactory/Conan)
    # или ParsingError (манифест, JSON, YAML)
    console.print("🔄 Запуск пайплайна…", style="cyan")
    try:
        result = parser.parse(save_intermediate=save_intermediate)
    except NetworkError as e:
        console.print(f"❌ Сетевая ошибка: {e}", style="red bold")
        sys.exit(1)
    except ParsingError as e:
        console.print(f"❌ Ошибка парсинга: {e}", style="red bold")
        sys.exit(1)

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
