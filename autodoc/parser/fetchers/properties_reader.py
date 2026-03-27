"""
Утилита для чтения файлов формата .properties.
"""
from pathlib import Path

def read_properties(filepath: Path) -> dict[str, str]:
    """
    Читает ``.properties``-файл в словарь ключ-значение.

    Поддерживает многострочные значения (строки, заканчивающиеся на ``\\``).
    Игнорирует комментарии (``#``) и пустые строки.

    Args:
        filepath: Путь к файлу ``.properties``.

    Returns:
        Словарь ``ключ → значение``. Ключи и значения обрезаются от пробелов.

    Raises:
        OSError: Если файл не найден или недоступен для чтения.
    """
    content = filepath.read_text(encoding='utf-8')

    # Склеиваем строки с переносом (заканчивающиеся на '\')
    content = content.replace('\\\n', '')

    props: dict[str, str] = {}
    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            key, val = line.split('=', 1)
            props[key.strip()] = val.strip()

    return props
