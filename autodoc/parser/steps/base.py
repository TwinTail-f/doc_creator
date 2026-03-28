"""
Базовые типы пайплайна парсера: контекст и абстрактный шаг.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from autodoc.config.schemas import ParserConfigSchema
from autodoc.models.component import Component
from autodoc.models.parsed_result import ParsedResult

if TYPE_CHECKING:
    from autodoc.parser.tfs_client import TFSClient

_T = TypeVar('_T')



@dataclass
class FetchResult(Generic[_T]):
    """Тонкая обёртка над результатом fetch — значение + предупреждения."""
    value: _T
    warnings: list[str] = field(default_factory=list)


class IFetcher(ABC, Generic[_T]):
    """Интерфейс двухфазового фетчера: configure() → fetch()."""

    @abstractmethod
    def configure(self, ctx: 'PipelineContext') -> None:
        """Читает нужные данные из ctx и сохраняет в self._*."""
        ...

    @abstractmethod
    def fetch(self, *args: Any, **kwargs: Any) -> 'FetchResult[_T]':
        """Загружает данные. Должен вызываться после configure()."""
        ...


class BaseTFSFetcher(IFetcher[_T]):
    """
    Базовый фетчер с доступом к TFSClient-синглтону.

    Конструктор только получает экземпляр синглтона и устанавливает флаг
    ``_configured = False``. Вся работа с конфигом — в ``configure(ctx)``.
    """

    def __init__(self) -> None:
        self._tfs = None          # set lazily in configure()
        self._configured: bool = False

    def _guarded_fetch(self, *args: Any, **kwargs: Any) -> 'FetchResult[_T]':
        if not getattr(self, '_configured', False):
            raise RuntimeError(
                '%s: call configure() before fetch()' % self.__class__.__name__
            )
        return self._do_fetch(*args, **kwargs)

    @abstractmethod
    def configure(self, ctx: 'PipelineContext') -> None: ...

    @abstractmethod
    def _do_fetch(self, *args: Any, **kwargs: Any) -> 'FetchResult[_T]': ...


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
    components: list[Component] = field(default_factory=list)
    result: ParsedResult | None = None
    intermediate: dict[str, Any] = field(default_factory=dict)

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
