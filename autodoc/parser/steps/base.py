"""
Базовые типы шагов пайплайна парсера: контекст и абстрактный шаг.

Абстракции фетчеров (``FetchResult``, ``IFetcher``, ``BaseTFSFetcher``) намеренно
вынесены в ``autodoc.parser.fetchers.base`` — они относятся к слою загрузки данных,
а не к слою шагов.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autodoc.config.schemas import ParserConfigSchema
from autodoc.models.component import Component
from autodoc.models.parsed_result import ParsedResult
from autodoc.parser.fetchers.base import BaseTFSFetcher, FetchResult, IFetcher


@dataclass
class PipelineContext:
    """
    Контекст выполнения пайплайна парсера.

    Единственный канал передачи состояния между шагами.
    Каждый шаг читает нужные данные и записывает результат своей работы.

    Поле ``docker_links`` отсутствует намеренно — после переноса
    ``apply_docker_links`` в ``DockerResolveStep`` оно больше не используется
    следующими шагами. При необходимости диагностики данные доступны через
    ``ctx.intermediate['docker_links']``.

    Attributes:
        config: Валидированная конфигурация парсера.
        tmp_dir: Временная директория для промежуточных файлов.
        components: Список компонентов, накапливаемый шагами пайплайна.
        result: Финальный результат, заполняется ``FinalizeStep``.
        intermediate: Произвольные данные для диагностики и передачи между шагами.
    """

    config: ParserConfigSchema
    tmp_dir: Path
    components: list[Component] = field(default_factory=list)
    result: ParsedResult | None = None
    intermediate: dict[str, Any] = field(default_factory=dict)


class BaseParseStep(ABC):
    """
    Базовый шаг пайплайна парсера.

    ``name`` объявлен как class-атрибут. ``__init_subclass__`` проверяет его
    наличие при объявлении класса — ошибка конфигурации проявляется до запуска
    программы, а не во время выполнения пайплайна.
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
