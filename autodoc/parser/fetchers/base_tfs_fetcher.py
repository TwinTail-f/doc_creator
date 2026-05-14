"""
Базовый фетчер для фетчеров, работающих с TFS через TFSClientProtocol.
"""

from autodoc.parser.clients.tfs_client_protocol import TFSClientProtocol
from autodoc.parser.fetchers.base_fetcher import FetcherBase


class BaseTFSFetcher[T](FetcherBase[T]):
    """
    Базовый класс для фетчеров, обращающихся к TFS.

    Хранит ссылку на ``TFSClientProtocol``; конкретное значение
    устанавливается в ``configure(ctx)`` подклассом.
    Контракт ``configure()`` / ``fetch()`` унаследован от ``FetcherBase[T]``.
    """

    def __init__(self) -> None:
        """Инициализирует фетчер; ``_tfs`` заполняется в методе ``configure()``."""
        super().__init__()
        self._tfs: TFSClientProtocol | None = None
