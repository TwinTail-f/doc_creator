# autodoc/cli/commands/parse.py

import sys
import click
from rich.panel import Panel

from autodoc.exceptions import ConfigError, DocGeneratorError
from autodoc.common.logger import logger
from autodoc.parser.parser import ComponentParser
from autodoc.parser.steps.conan_step import ConanEnrichStep
from autodoc.parser.steps.validation_step import ArtifactoryValidationStep
from autodoc.cli._context import _CliCtx
from autodoc.cli._helpers import console


@click.command()
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
