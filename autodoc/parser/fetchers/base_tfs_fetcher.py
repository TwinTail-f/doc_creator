"""
Базовый фетчер с отложенным доступом к TFSClient-синглтону.
"""

from abc import abstractmethod

from autodoc.parser.clients.tfs_client_protocol import TFSClientProtocol
from autodoc.parser.fetchers.base_fetcher import FetcherBase
from autodoc.parser.pipeline.context_protocol import PipelineContextProtocol


class BaseTFSFetcher[T](FetcherBase[T]):
    """
    Базовый фетчер с отложенным доступом к ``TFSClient``-синглтону.

    Весь доступ к конфигурации и синглтону — в ``configure(ctx)``.
    """

    def __init__(self) -> None:
        """Инициализирует фетчер; ``_tfs`` заполняется в методе ``configure()``."""
        self._tfs: TFSClientProtocol | None = None

    @abstractmethod
    def configure(self, ctx: PipelineContextProtocol) -> None:
        """
        Инициализирует фетчер данными из контекста пайплайна.

        Должен вызываться перед ``fetch()``. Реализация извлекает нужные
        поля из ``ctx.config`` и ``ctx.tfs_client``.

        Args:
            ctx: Контекст пайплайна с конфигурацией и TFS-клиентом.
        """
