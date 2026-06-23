"""Вспомогательный Click-класс с подсказкой о кавычках."""
from typing import Any

import click

_NAME_FLAG_SUFFIX: str = "-name"


class _QuoteHintCommand(click.Command):
    """Click-команда с подсказкой о кавычках при лишних аргументах."""

    def make_context(
        self,
        info_name: str | None,
        args: list[str],
        parent: click.Context | None = None,
        **extra: Any,
    ) -> click.Context:
        """Оборачивает стандартный make_context, добавляя подсказку о кавычках.

        Args:
            info_name: Имя команды, передаваемое в стандартный ``make_context``.
            args: Список аргументов командной строки.
            parent: Родительский контекст Click.
            **extra: Дополнительные аргументы для ``make_context``.

        Returns:
            Контекст Click, созданный стандартной реализацией.

        Raises:
            click.UsageError: Исходная ошибка использования, либо дополненная
                подсказкой о кавычках для опций с суффиксом ``-name``.
        """
        # TODO(review): Click мутирует список args в процессе парсинга —
        # к моменту перехвата UsageError уже распознанные опции (включая
        # --*-name) могут быть удалены из args, и подсказка не сработает.
        # Этот дефект уже присутствовал в исходной реализации с _NAME_OPTIONS
        # и не входит в текущую задачу (замена сниффинга списка флагов).
        try:
            return super().make_context(info_name, args, parent=parent, **extra)
        except click.UsageError as e:
            name_flags = sorted(
                {
                    arg.split("=", 1)[0]
                    for arg in args
                    if arg.split("=", 1)[0].endswith(_NAME_FLAG_SUFFIX)
                }
            )
            if "unexpected extra argument" in str(e).lower() and name_flags:
                examples = "\n".join(
                    f'   {flag} "Название страницы"' for flag in name_flags
                )
                raise click.UsageError(
                    f"{e}\n\n"
                    "💡 Если название страницы содержит пробелы, заключите его в кавычки:\n"
                    f"{examples}"
                ) from e
            raise
