"""
Утилита для чтения файлов формата .properties.
"""

from pathlib import Path

# Поддерживаемые разделители ключ-значение.
# Новый формат манифестов использует «=», старый формат — «:».
_SEPARATOR_EQ: str = "="
_SEPARATOR_COLON: str = ":"


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
    content = filepath.read_text(encoding="utf-8")

    # Склеиваем строки с переносом (заканчивающиеся на '\')
    content = content.replace("\\\n", "")

    props: dict[str, str] = {}
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
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
