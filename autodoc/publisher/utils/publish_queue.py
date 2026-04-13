"""Управление очередью задач публикации с пакетной обработкой."""

import time
from collections.abc import Callable
from typing import TypeVar

from autodoc.infrastructure.logger import logger

T = TypeVar("T")
R = TypeVar("R")

_DEFAULT_BATCH_SIZE: int = 10
_DEFAULT_BATCH_DELAY: float = 0.0


class PublishQueue:
    """
    Управляет очередью задач публикации с поддержкой пакетной обработки.

    Разбивает задачи на пакеты указанного размера и опционально делает
    паузу между пакетами, чтобы не перегружать сервер Confluence.

    Не занимается обработкой ошибок — это ответственность вызывающего кода.
    Исключения из ``fn`` прокидываются вызывающей стороне без изменений.
    """

    def __init__(
        self,
        batch_size: int = _DEFAULT_BATCH_SIZE,
        batch_delay_seconds: float = _DEFAULT_BATCH_DELAY,
    ) -> None:
        """
        Args:
            batch_size: Количество элементов в одном пакете. Минимум 1.
            batch_delay_seconds: Задержка в секундах между пакетами.
                                 ``0`` — без задержки.

        Raises:
            ValueError: Если ``batch_size < 1`` или ``batch_delay_seconds < 0``.
        """
        if batch_size < 1:
            raise ValueError(
                f"batch_size должен быть не менее 1, получено: {batch_size}"
            )
        if batch_delay_seconds < 0:
            raise ValueError(
                f"batch_delay_seconds должен быть неотрицательным, "
                f"получено: {batch_delay_seconds}"
            )
        self._batch_size: int = batch_size
        self._batch_delay: float = batch_delay_seconds

    @property
    def batch_size(self) -> int:
        """Количество элементов в одном пакете."""
        return self._batch_size

    @property
    def batch_delay_seconds(self) -> float:
        """Задержка между пакетами в секундах."""
        return self._batch_delay

    def process(self, items: list[T], fn: Callable[[T], R]) -> list[R]:
        """
        Обрабатывает элементы пакетами, вызывая ``fn`` для каждого.

        Между пакетами делает паузу ``batch_delay_seconds``, если она задана
        и обрабатываемых пакетов больше одного. Исключения из ``fn`` не
        перехватываются — обработка ошибок остаётся за вызывающим кодом.

        Args:
            items: Список задач для обработки.
            fn: Функция, вызываемая для каждого элемента.

        Returns:
            Список результатов в том же порядке, что и ``items``.
        """
        results: list[R] = []
        total = len(items)
        if total == 0:
            return results

        total_batches = (total + self._batch_size - 1) // self._batch_size

        for batch_idx, batch_start in enumerate(
            range(0, total, self._batch_size), start=1
        ):
            batch = items[batch_start : batch_start + self._batch_size]
            logger.debug(
                f"Пакет {batch_idx}/{total_batches}: {len(batch)} страниц"
            )
            for item in batch:
                results.append(fn(item))

            is_last_batch = batch_start + self._batch_size >= total
            if self._batch_delay > 0 and not is_last_batch:
                logger.debug(
                    f"Пауза {self._batch_delay}с перед следующим пакетом"
                )
                time.sleep(self._batch_delay)

        return results
