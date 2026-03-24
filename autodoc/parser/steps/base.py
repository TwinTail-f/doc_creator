"""
Базовые типы пайплайна парсера: контекст и абстрактный шаг.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from autodoc.config.schemas import ParserConfigSchema
from autodoc.models.component import Component
from autodoc.models.parsed_result import ParsedResult


@dataclass
class PipelineContext:
    """
    Контекст выполнения пайплайна парсера.

    Единственный канал коммуникации между шагами.

    3.15 Поле ``docker_links`` удалено — после переноса ``apply_docker_links``
    в ``DockerResolveStep`` оно больше не читается ни одним последующим шагом.
    Если нужно для диагностики — шаг записывает в ``ctx.intermediate['docker_links']``.
    """

    config: ParserConfigSchema
    tmp_dir: Path
    components: List[Component] = field(default_factory=list)
    result: Optional[ParsedResult] = None
    intermediate: Dict[str, Any] = field(default_factory=dict)


class BaseParseStep(ABC):
    """
    Базовый шаг пайплайна парсера.

    2.4 ``name`` объявлен как class-атрибут. ``__init_subclass__`` проверяет
    его наличие при объявлении класса — ошибка появляется до запуска программы.
    """

    name: str = ''
    is_critical: bool = True

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not getattr(cls, '__abstractmethods__', None) and not cls.name:
            raise TypeError('%s должен определить атрибут name' % cls.__name__)

    @abstractmethod
    def execute(self, ctx: PipelineContext) -> None:
        """
        Выполняет логику шага.

        Args:
            ctx: Контекст пайплайна. Шаг читает нужные данные и записывает результат.
        """
