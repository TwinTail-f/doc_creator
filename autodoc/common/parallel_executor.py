"""
Инфраструктурный класс параллельного выполнения задач через ``ThreadPoolExecutor``.

Централизует логику многопоточного выполнения для всех компонентов проекта.
"""

import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections.abc import Callable

from autodoc.common.logger import logger
from autodoc.exceptions import ComponentParsingError, NetworkError, ParsingError

_DEFAULT_LOG_PROGRESS_INTERVAL: int = 50
_DEFAULT_BATCH_SIZE: int = 0
_DEFAULT_BATCH_DELAY: float = 0.0


class ParallelExecutor:
    """
    Обёртка над ``ThreadPoolExecutor`` для унифицированного параллельного выполнения.

    Возвращает результаты в том же порядке, что и входные данные.
    Если выполнение задачи завершилось ожидаемой операционной ошибкой
    (``NetworkError``, ``ParsingError``, ``ComponentParsingError``,
    ``ValueError``, ``KeyError``) — результат для соответствующего элемента
    равен ``None``, исключение логируется с полным traceback. Программные
    ошибки (например ``AttributeError``, ``TypeError``) пробрасываются дальше.

    Опциональные параметры ``batch_size`` и ``batch_delay`` включают
    пакетную обработку с паузами между пакетами.
    При ``batch_size=0`` (по умолчанию) все задачи выполняются одним пулом
    без разбивки на пакеты.

    Example::

        executor = ParallelExecutor(max_workers=8)
        results = executor.execute(parse_file, files, task_label="файлов")

        executor = ParallelExecutor(max_workers=64)
        raw_results = executor.execute(runner.run, tasks, task_label="задач Conan")

        executor = ParallelExecutor(max_workers=10, batch_size=10, batch_delay=0.5)
        results = executor.execute(publish_fn, pages, task_label="страниц")
    """

    def __init__(
        self,
        max_workers: int,
        log_progress_interval: int = _DEFAULT_LOG_PROGRESS_INTERVAL,
        batch_size: int = _DEFAULT_BATCH_SIZE,
        batch_delay: float = _DEFAULT_BATCH_DELAY,
    ) -> None:
        """
        Args:
            max_workers: Максимальное число одновременно работающих потоков.
            log_progress_interval: Интервал логирования прогресса (каждые N задач).
            batch_size: Размер пакета задач. При ``0`` разбивка на пакеты
                        не выполняется — все задачи запускаются в одном пуле.
            batch_delay: Задержка в секундах между пакетами. Применяется
                         только если ``batch_size > 0`` и пакетов более одного.

        Raises:
            ValueError: Если ``batch_size < 0`` или ``batch_delay < 0``.
        """
        if batch_size < 0:
            raise ValueError(f"batch_size должен быть неотрицательным, получено: {batch_size}")
        if batch_delay < 0:
            raise ValueError(f"batch_delay должен быть неотрицательным, получено: {batch_delay}")
        self._max_workers: int = max_workers
        self._log_progress_interval: int = log_progress_interval
        self._batch_size: int = batch_size
        self._batch_delay: float = batch_delay

    def execute[T, R](
        self,
        fn: Callable[[T], R],
        items: list[T],
        task_label: str = "задач",
    ) -> list[R | None]:
        """
        Выполняет ``fn`` для каждого элемента ``items`` параллельно.

        Если задан ``batch_size > 0``, задачи разбиваются на пакеты и между
        ними делается пауза ``batch_delay`` секунд (кроме последнего пакета).
        Результаты возвращаются в том же порядке, что и входные ``items``.

        Args:
            fn: Функция для применения к каждому элементу.
            items: Список входных данных.
            task_label: Метка задачи для строк логирования (например ``'файлов'``).

        Returns:
            Список результатов длиной ``len(items)`` в исходном порядке.
            При исключении в ``fn`` соответствующий элемент равен ``None``.
        """
        if not items:
            return []

        if self._batch_size > 0:
            return self._execute_in_batches(fn, items, task_label)
        return self._execute_pool(fn, items, task_label)

    def _execute_in_batches[T, R](
        self,
        fn: Callable[[T], R],
        items: list[T],
        task_label: str,
    ) -> list[R | None]:
        """
        Выполняет задачи пакетами с паузой между ними.

        Args:
            fn: Функция для применения к каждому элементу.
            items: Список входных данных.
            task_label: Метка задачи для строк логирования.

        Returns:
            Список результатов в исходном порядке.
        """
        total = len(items)
        total_batches = (total + self._batch_size - 1) // self._batch_size
        results: list[R | None] = [None] * total

        for batch_num, batch_start in enumerate(range(0, total, self._batch_size), start=1):
            batch_items = items[batch_start : batch_start + self._batch_size]
            batch_indices = list(range(batch_start, batch_start + len(batch_items)))
            logger.debug(f"Пакет {batch_num}/{total_batches}: {len(batch_items)} {task_label}")

            batch_results = self._execute_pool(fn, batch_items, task_label)
            for local_idx, global_idx in enumerate(batch_indices):
                results[global_idx] = batch_results[local_idx]

            is_last_batch = batch_start + self._batch_size >= total
            if self._batch_delay > 0 and not is_last_batch:
                logger.debug(f"Пауза {self._batch_delay}с перед следующим пакетом")
                time.sleep(self._batch_delay)

        return results

    def _execute_pool[T, R](
        self,
        fn: Callable[[T], R],
        items: list[T],
        task_label: str,
    ) -> list[R | None]:
        """
        Выполняет задачи параллельно в одном пуле потоков.

        Args:
            fn: Функция для применения к каждому элементу.
            items: Список входных данных.
            task_label: Метка задачи для строк логирования.

        Returns:
            Список результатов в исходном порядке.
        """
        results: list[R | None] = [None] * len(items)

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_to_idx = {executor.submit(fn, item): idx for idx, item in enumerate(items)}

            completed = 0
            total = len(items)

            for future in as_completed(future_to_idx):
                completed += 1
                if completed % self._log_progress_interval == 0 or completed == total:
                    logger.info(f"Прогресс: {completed}/{total} {task_label}…")

                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                # Перехватываем только ожидаемые ошибки операционного домена задач,
                # выполняемых через этот исполнитель (сеть, парсинг данных):
                # такая ошибка одной задачи не должна прерывать обработку
                # остальных. Программные ошибки (AttributeError, TypeError
                # и т.п.) пробрасываются дальше с полным traceback.
                except (
                    NetworkError,
                    ParsingError,
                    ComponentParsingError,
                    ValueError,
                    KeyError,
                ) as exc:
                    logger.exception(f"Ошибка при выполнении задачи #{idx}: {exc}")

        return results
