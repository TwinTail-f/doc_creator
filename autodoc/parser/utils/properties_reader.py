"""
Утилита для чтения файлов формата .properties.
"""

from collections.abc import Generator
from pathlib import Path

# Поддерживаемые разделители ключ-значение.
# Новый формат манифестов использует «=», старый формат — «:».
_SEPARATOR_EQ: str = "="
_SEPARATOR_COLON: str = ":"


def _logical_lines(filepath: Path) -> Generator[str, None, None]:
    """
    Генератор логических строк файла ``.properties``.

    Объединяет физические строки с продолжением (оканчивающиеся на ``\\``)
    в одну логическую строку. Пустые строки и комментарии (``#``) пропускаются
    здесь же, чтобы не засорять основную логику парсинга.

    Args:
        filepath: Путь к файлу ``.properties``.

    Yields:
        Логические строки без символа продолжения и без обрамляющих пробелов.

    Raises:
        OSError: Если файл не найден или недоступен для чтения.
    """
    with filepath.open("r", encoding="utf-8") as f:
        pending = ""
        for raw in f:
            if raw.endswith("\\\n"):
                pending += raw[:-2]
            else:
                pending += raw.rstrip("\n")
                line = pending.strip()
                pending = ""
                if line and not line.startswith("#"):
                    yield line
        # Последняя строка, если файл не заканчивается переводом строки
        if pending:
            line = pending.strip()
            if line and not line.startswith("#"):
                yield line


def read_properties(filepath: Path) -> dict[str, str]:
    """
    Читает ``.properties``-файл в словарь ключ-значение.

    Поддерживает два формата разделителей:

    - **Новый формат** — ``key= value`` (разделитель ``=``).
    - **Старый формат** — ``key: value`` (разделитель ``:``).

    Формат определяется автоматически для каждой строки: если ``=`` встречается
    раньше ``:``, используется ``=``; если только ``:`` — используется ``:``.

    Поддерживает многострочные значения (строки, заканчивающиеся на ``\\``).
    Игнорирует комментарии (``#``) и пустые строки.

    Args:
        filepath: Путь к файлу ``.properties``.

    Returns:
        Словарь ``ключ → значение``. Ключи и значения обрезаются от пробелов.

    Raises:
        OSError: Если файл не найден или недоступен для чтения.
    """
    props: dict[str, str] = {}
    for line in _logical_lines(filepath):
        sep = _detect_separator(line)
        if sep is None:
            continue
        key, val = line.split(sep, 1)
        props[key.strip()] = val.strip()
    return props


def _detect_separator(line: str) -> str | None:
    """
    Определяет разделитель ключ-значение в строке ``.properties``.

    Приоритет отдаётся ``=`` (новый формат): если ``=`` встречается в строке
    раньше ``:``, используется ``=``. Если ``=`` отсутствует, но есть ``:``
    (старый формат) — используется ``:``. Если ни одного разделителя нет —
    возвращает ``None``.

    Args:
        line: Строка файла ``.properties`` (уже очищенная от пробелов).

    Returns:
        Символ-разделитель (``'='`` или ``':'``) или ``None``, если ни один
        из разделителей не найден.
    """
    pos_eq = line.find(_SEPARATOR_EQ)
    pos_colon = line.find(_SEPARATOR_COLON)

    if pos_eq == -1 and pos_colon == -1:
        return None
    if pos_eq == -1:
        return _SEPARATOR_COLON
    if pos_colon == -1:
        return _SEPARATOR_EQ
    # Оба присутствуют — берём тот, что встречается раньше
    return _SEPARATOR_EQ if pos_eq <= pos_colon else _SEPARATOR_COLON
