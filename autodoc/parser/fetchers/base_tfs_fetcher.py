"""
Базовый фетчер для фетчеров, работающих с TFS через TFSClient.
"""

from autodoc.parser.clients.tfs_client import TFSClient
from autodoc.parser.fetchers.base_fetcher import BaseFetcher


class BaseTFSFetcher[T](BaseFetcher[T]):
    """
    Базовый класс для фетчеров, обращающихся к TFS.

    Хранит ссылку на ``TFSClient``; конкретное значение
    устанавливается в ``configure(ctx)`` подклассом.
    Контракт ``configure()`` / ``fetch()`` унаследован от ``BaseFetcher[T]``.
    """

    def __init__(self) -> None:
        """Инициализирует фетчер; ``_tfs`` заполняется в методе ``configure()``."""
        super().__init__()
        self._tfs: TFSClient | None = None
