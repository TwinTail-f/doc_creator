"""
Результат выполнения одной команды ``conan graph info``.

Намеренно отделён от ``conan_runner`` — дата-класс без зависимостей,
используется как ``ConanRunner``-ами, так и ``ConanManager``-ом.
"""
from dataclasses import dataclass
from typing import Any

from autodoc.parser.conan.task_builder import ConanTask


@dataclass
class ConanRawResult:
    """
    Сырой результат выполнения одной команды ``conan graph info``.

    Содержит либо распарсенный JSON (при успехе), либо текст ошибки.
    Промежуточный тип — преобразуется в ``ConanEnrichData`` через ``ConanResultParser``.

    Attributes:
        task: Задача, породившая этот результат.
        success: ``True`` если команда завершилась с кодом 0 и JSON разобран.
        data: Разобранный JSON-ответ ``conan graph info``, если ``success=True``.
        error: Текст ошибки, если ``success=False``.
    """

    task: ConanTask
    success: bool
    data: dict[str, Any] | None
    error: str
