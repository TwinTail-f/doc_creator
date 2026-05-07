"""
Обёртка результата fetch с предупреждениями.
"""

from dataclasses import dataclass, field


@dataclass
class FetchResult[T]:
    """
    Тонкая обёртка над результатом fetch — значение и список предупреждений.

    Позволяет шагам пайплайна получить дополнительный контекст о нештатных
    ситуациях, не бросая исключений.

    Attributes:
        value: Основной результат операции загрузки.
        warnings: Накопленный список предупреждений, возникших в ходе загрузки.
    """

    value: T
    warnings: list[str] = field(default_factory=list)
