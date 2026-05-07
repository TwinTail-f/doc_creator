"""
Базовый фетчер с отложенным доступом к TFSClient-синглтону.
"""

from abc import abstractmethod

from autodoc.parser.clients.tfs_client_protocol import ITFSClient
from autodoc.parser.fetchers.i_fetcher import IFetcher
from autodoc.parser.pipeline.context_protocol import IPipelineContext


class BaseTFSFetcher[T](IFetcher[T]):
    """
    Базовый фетчер с отложенным доступом к ``TFSClient``-синглтону.

    Весь доступ к конфигурации и синглтону — в ``configure(ctx)``.
    """

    def __init__(self) -> None:
        """Инициализирует фетчер; ``_tfs`` заполняется в методе ``configure()``."""
        self._tfs: ITFSClient | None = None

    @abstractmethod
    def configure(self, ctx: IPipelineContext) -> None: ...
