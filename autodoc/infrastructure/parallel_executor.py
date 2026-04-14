"""
Инфраструктурный класс параллельного выполнения задач через ``ThreadPoolExecutor``.

Централизует логику многопоточного выполнения, ранее дублировавшуюся в
``ConanManager``, ``ArtifactoryValidationStep`` и ``ManifestParser``.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, TypeVar

from autodoc.infrastructure.logger import logger

_T = TypeVar("_T")
_R = TypeVar("_R")

_SUPPORTED_LOG_LEVELS: frozenset[str] = frozenset({"debug", "info", "warning"})
_DEFAULT_LOG_PROGRESS_INTERVAL: int = 50


class ParallelExecutor:
    """
    Обёртка над ``ThreadPoolExecutor`` для унифицированного параллельного выполнения.

    Возвращает результаты в том же порядке, что и входные данные.
    Если выполнение задачи завершилось исключением — результат для соответствующего
    элемента равен ``None``, исключение логируется как предупреждение.

    Example::

        executor = ParallelExecutor(max_workers=8)
        results = executor.execute(parse_file, files, task_label="файлов")

        executor = ParallelExecutor(max_workers=64, log_level="info")
        raw_results = executor.execute(runner.run, tasks, task_label="задач Conan")
    """

    def __init__(
        self,
        max_workers: int,
        log_progress_interval: int = _DEFAULT_LOG_PROGRESS_INTERVAL,
        log_level: str = "info",
    ) -> None:
        """
        Args:
            max_workers: Максимальное число одновременно работающих потоков.
            log_progress_interval: Интервал логирования прогресса (каждые N задач).
            log_level: Уровень логирования прогресса — ``'debug'``, ``'info'``
                       или ``'warning'``. По умолчанию ``'info'``.
        """
        if log_level not in _SUPPORTED_LOG_LEVELS:
            raise ValueError(
                f"Неподдерживаемый log_level: {log_level!r}. "
                f"Допустимые значения: {sorted(_SUPPORTED_LOG_LEVELS)}"
            )

        self._max_workers = max_workers
        self._log_progress_interval = log_progress_interval
        self._log: Callable[..., None] = getattr(logger, log_level)

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
                    self._log(f"Прогресс: {completed}/{total} {task_label}…")

                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                # Broad catch is intentional: the executor accepts arbitrary
                # user-provided callables; any exception from fn must be
                # logged and skipped so that remaining tasks continue processing.
                except Exception as exc:
                    logger.warning(f"Ошибка при выполнении задачи #{idx}: {exc}")

        return results
