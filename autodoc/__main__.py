"""
Точка входа для CLI autodoc.
Запуск:
    autodoc parse
    autodoc publish release

Инструмент предназначен для запуска на Linux.
"""

from autodoc.cli.app import cli


def main() -> None:
    cli(obj={})


if __name__ == "__main__":
    main()
