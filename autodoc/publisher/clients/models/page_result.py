"""DTO результата операции с страницей Confluence."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PageResult:
    """Результат операции создания или обновления страницы Confluence."""

    id: str
    version: int
    status: str
    """``'created'`` при создании, ``'updated'`` при обновлении."""
    message: str = ""
    """Читаемое описание результата для логирования."""
