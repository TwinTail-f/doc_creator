"""Вспомогательный Click-класс с подсказкой о кавычках."""
from typing import Any

import click

_NAME_OPTIONS: tuple[str, ...] = (
    "--root-page-name",
    "--passports-root-parent-name",
    "--release-root-page-name",
    "--additional-page-profile-name",
)


class _QuoteHintCommand(click.Command):
    """Click-команда с подсказкой о кавычках при лишних аргументах."""

    def make_context(
        self,
        info_name: str | None,
        args: list[str],
        parent: click.Context | None = None,
        **extra: Any,
    ) -> click.Context:
        """Оборачивает стандартный make_context, добавляя подсказку о кавычках."""
        try:
            return super().make_context(info_name, args, parent=parent, **extra)
        except click.UsageError as e:
            if "unexpected extra argument" in str(e).lower() and any(
                opt in args for opt in _NAME_OPTIONS
            ):
                raise click.UsageError(
                    f"{e}\n\n"
                    "💡 Если название страницы содержит пробелы, заключите его в кавычки:\n"
                    '   --root-page-name "Название страницы"\n'
                    '   --passports-root-parent-name "Название страницы"\n'
                    '   --release-root-page-name "Название страницы"'
                ) from e
            raise
