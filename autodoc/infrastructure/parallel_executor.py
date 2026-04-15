"""
Инфраструктурный класс параллельного выполнения задач через ``ThreadPoolExecutor``.

Централизует логику многопоточного выполнения, ранее дублировавшуюся в
``ConanManager``, ``ArtifactoryValidationStep`` и ``ManifestParser``.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum
from typing import Callable, TypeVar

from autodoc.infrastructure.logger import logger

# _T — тип входного элемента, передаваемого в fn
# _R — тип результата, возвращаемого fn
_T = TypeVar("_T")
_R = TypeVar("_R")

_DEFAULT_LOG_PROGRESS_INTERVAL: int = 50


class LogLevel(Enum):
    """Допустимые уровни логирования для ``ParallelExecutor``."""

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING


class ParallelExecutor:
    """
    Обёртка над ``ThreadPoolExecutor`` для унифицированного параллельного выполнения.

    Возвращает результаты в том же порядке, что и входные данные.
    Если выполнение задачи завершилось исключением — результат для соответствующего
    элемента равен ``None``, исключение логируется как предупреждение.

    Example::

        executor = ParallelExecutor(max_workers=8)
        results = executor.execute(parse_file, files, task_label="файлов")

        executor = ParallelExecutor(max_workers=64, log_level=LogLevel.INFO)
        raw_results = executor.execute(runner.run, tasks, task_label="задач Conan")
    """

    def __init__(
        self,
        max_workers: int,
        log_progress_interval: int = _DEFAULT_LOG_PROGRESS_INTERVAL,
        log_level: LogLevel = LogLevel.INFO,
    ) -> None:
        """
        Args:
            max_workers: Максимальное число одновременно работающих потоков.
            log_progress_interval: Интервал логирования прогресса (каждые N задач).
            log_level: Уровень логирования прогресса. По умолчанию ``LogLevel.INFO``.
        """
        self._max_workers = max_workers
        self._log_progress_interval = log_progress_interval
        self._log_level = log_level

    def execute(
        self,
        fn: Callable[[_T], _R],
        items: list[_T],
        task_label: str = "задач",
    ) -> list[_R | None]:
        """
        Выполняет ``fn`` для каждого элемента ``items`` параллельно.

        Результаты возвращаются в том же порядке, что и входные ``items``.
        Прогресс логируется каждые ``log_progress_interval`` завершённых задач,
        а также при обработке последней задачи.

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

        results: list[_R | None] = [None] * len(items)

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_to_idx = {
                executor.submit(fn, item): idx for idx, item in enumerate(items)
            }

            completed = 0
            total = len(items)

            for future in as_completed(future_to_idx):
                completed += 1
                if completed % self._log_progress_interval == 0 or completed == total:
                    logger.log(
                        self._log_level.value,
                        f"Прогресс: {completed}/{total} {task_label}…",
                    )

                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                # Сознательно ловим все исключения:
                # исполнитель принимает произвольные вызываемые объекты от пользователя,
                # поэтому любая ошибка в fn должна быть залогирована, но не прерывать
                # обработку остальных элементов — чтобы остались результаты других задач.
                except Exception as exc:
                    logger.warning(f"Ошибка при выполнении задачи #{idx}: {exc}")

        return results
