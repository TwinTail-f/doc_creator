"""
Протоколы (structural interfaces) для слоя фетчеров.


Фетчерам не нужен конкретный ``PipelineContext`` — им достаточно знать,
что у объекта есть ``config`` и ``tfs_client``.  ``PipelineContext``
удовлетворяет этому протоколу структурно (duck typing), без явного наследования.
"""

from typing import Protocol, runtime_checkable

from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.parser.clients.tfs_client_protocol import TFSClientProtocol


@runtime_checkable
class PipelineContextProtocol(Protocol):
    """
    Минимальный интерфейс контекста пайплайна, необходимый фетчерам.

    Намеренно содержит только те поля, к которым обращается слой фетчеров
    (``config`` и ``tfs_client``).  Это позволяет:

    - тестировать фетчеры с лёгким фейком вместо полного ``PipelineContext``;
    - избежать циклического импорта между ``fetchers/base`` и ``steps/base``.
    """

    config: ParserConfigSchema
    tfs_client: TFSClientProtocol | None
