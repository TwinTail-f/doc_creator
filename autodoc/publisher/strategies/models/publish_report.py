"""Модель результата выполнения стратегии публикации."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PublishReport:
    """
    Типизированный результат выполнения стратегии публикации.

    Заменяет ``dict[str, Any]`` — контракт проверяется статически.

    Attributes:
        success: ``True`` если публикация завершилась без ошибок.
        pages_published: Количество успешно опубликованных страниц.
        pages_failed: Количество страниц, публикация которых завершилась ошибкой.
        errors: Список текстовых сообщений об ошибках.
        failed_pages: Структурированная информация о каждой неудавшейся странице
                      в формате ``{'page_title': str, 'reason': str}``.
        details: Подробные записи об успешно опубликованных страницах.
    """

    success: bool
    pages_published: int
    pages_failed: int = 0
    errors: list[str] = field(default_factory=list)
    failed_pages: list[dict[str, Any]] = field(default_factory=list)
    details: list[dict[str, Any]] = field(default_factory=list)

    @staticmethod
    def merge(*reports: "PublishReport") -> "PublishReport":
        """Объединяет несколько отчётов о публикации в один сводный.

        Args:
            *reports: Отчёты для объединения.

        Returns:
            Сводный отчёт с агрегированными счётчиками и ошибками.
        """
        return PublishReport(
            success=all(r.success for r in reports),
            pages_published=sum(r.pages_published for r in reports),
            pages_failed=sum(r.pages_failed for r in reports),
            errors=[e for r in reports for e in r.errors],
            failed_pages=[p for r in reports for p in r.failed_pages],
            details=[d for r in reports for d in r.details],
        )
