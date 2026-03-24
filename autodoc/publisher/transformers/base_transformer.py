"""
Абстрактный базовый класс трансформеров данных.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict

from autodoc.models.parsed_result import ParsedResult


class BaseDataTransformer(ABC):
    """
    Абстрактный базовый класс трансформеров данных.

    Преобразует ``ParsedResult`` в view-model, пригодный для рендеринга
    конкретного шаблона. Следует паттерну Стратегия.
    """

    @abstractmethod
    def transform(self, data: ParsedResult) -> Dict[str, Any]:
        """
        Преобразует данные в view-model для шаблона.

        Args:
            data: Полный набор данных парсера.

        Returns:
            Словарь с иерархической структурой, готовый для шаблонизатора.
        """
