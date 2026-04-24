"""
Централизованный логгер проекта.

Предоставляет единственный настроенный экземпляр ``logger`` для использования
во всех модулях проекта. Формат вывода включает временну́ю метку, имя модуля,
имя функции и номер строки.

Usage::

    from autodoc.infrastructure.logger import logger
    logger.info("Сообщение")
"""

import logging


def setup_logging(logger_name: str = "doc_parser") -> logging.Logger:
    """
    Настраивает логгер с выводом модуля и функции.

    Args:
        logger_name: Имя логгера.

    Returns:
        Настроенный экземпляр logging.Logger.
    """
    log = logging.getLogger(logger_name)

    if not log.handlers:
        log.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            fmt="[%(asctime)s] | (%(module)s:%(funcName)s:%(lineno)d) -- %(levelname)s -- %(message)s",
            datefmt="%H:%M:%S",
        )

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)

        log.addHandler(console_handler)

    return log


logger = setup_logging()
