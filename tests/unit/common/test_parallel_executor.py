"""Модульные тесты для autodoc/common/parallel_executor.py.

ParallelExecutor запускает список вызываемых объектов одновременно с использованием пула потоков.
Тесты проверяют упорядочение результатов, изоляцию исключений и граничные случаи.
"""

import time
from typing import Any

import pytest

from autodoc.common.parallel_executor import ParallelExecutor

_TASK_COUNT: int = 4
_SLEEP_SHORT_SEC: float = 0.01
_SLEEP_LONG_SEC: float = 0.05
_MAX_WORKERS_SEQUENTIAL: int = 1
_MAX_WORKERS_PARALLEL: int = 8
_TIMEOUT_GUARD_SEC: int = 5


# T4A.2.1 — результаты возвращаются в порядке отправки, несмотря на неравномерное завершение
@pytest.mark.business_logic
def test_parallel_executor_results_in_submission_order() -> None:
    """Результаты возвращаются в порядке отправки, а не в порядке завершения.

    Задача 0 спит дольше всех, поэтому заканчивается последней; задача 3 спит меньше всех, поэтому
    заканчивается первой. Исполнитель должен сохранить исходное сопоставление индексов.
    Это самый важный тест в этом файле.
    """
    sleep_durations: list[float] = [
        _SLEEP_LONG_SEC,  # задача 0 — заканчивается последней
        _SLEEP_SHORT_SEC * 2,
        _SLEEP_SHORT_SEC,
        0.0,  # задача 3 — заканчивается первой
    ]
    expected_values: list[int] = list(range(_TASK_COUNT))

    def staggered_fn(index_and_sleep: tuple[int, float]) -> int:
        """Спит заданное время, затем возвращает индекс задачи как результат."""
        index, sleep = index_and_sleep
        time.sleep(sleep)
        return index

    executor = ParallelExecutor(max_workers=_MAX_WORKERS_PARALLEL)
    items: list[tuple[int, float]] = list(zip(expected_values, sleep_durations))
    results: list[int | None] = executor.execute(staggered_fn, items)

    assert results == expected_values


# T4A.2.2 — один неудачный задание не отменяет остальные
@pytest.mark.business_logic
def test_parallel_executor_exception_in_one_task_does_not_cancel_others() -> None:
    """Исключения в отдельных задачах изолированы; другие задачи всё ещё выдают результаты.

    Если одна задача вызывает исключение, её слот становится None, а остальные задачи
    выполняются до конца. Исключение не распространяется на вызывающий код.
    """

    def task_fn(index: int) -> int | None:
        """Возвращает индекс для задач 0 и 2; вызывает ValueError для задачи 1."""
        if index == 1:
            raise ValueError("intentional failure")
        return index

    executor = ParallelExecutor(max_workers=_MAX_WORKERS_PARALLEL)
    results: list[int | None] = executor.execute(task_fn, [0, 1, 2])

    assert results[0] == 0, "задача 0 должна выдать свой результат"
    assert results[1] is None, "неудачная задача должна выдать None"
    assert results[2] == 2, "задача 2 должна выдать свой результат"


# T4A.2.3 — все задачи вызывающие ошибки не вешаются
@pytest.mark.timeout(_TIMEOUT_GUARD_SEC)
@pytest.mark.business_logic
def test_parallel_executor_all_tasks_raise_does_not_hang() -> None:
    """execute() возвращается без взаимной блокировки, когда каждая задача вызывает ValueError.

    ValueError — один из ожидаемых операционных типов ошибок, которые
    ParallelExecutor перехватывает для каждой задачи по отдельности (см.
    docstring ``_execute_pool``); поэтому все результаты None, а исключение
    не распространяется на вызывающий код.
    """

    def always_fail(_: Any) -> None:
        raise ValueError("всегда падает")

    executor = ParallelExecutor(max_workers=_MAX_WORKERS_PARALLEL)
    results: list[None] = executor.execute(always_fail, [0, 1, 2])

    assert results == [None, None, None]


# T4A.2.4 — max_workers=1 выполняет задачи последовательно
@pytest.mark.business_logic
def test_parallel_executor_max_workers_one_is_sequential() -> None:
    """С max_workers=1 задачи выполняются последовательно в порядке отправки.

    Один рабочий предотвращает любой параллелизм; результаты должны быть в порядке отправки
    и могут быть проверены путём добавления в простой список без блокировки.
    """
    execution_order: list[int] = []

    def record_fn(index: int) -> int:
        """Добавляет в общий список, затем возвращает индекс."""
        execution_order.append(index)
        return index

    executor = ParallelExecutor(max_workers=_MAX_WORKERS_SEQUENTIAL)
    items: list[int] = list(range(_TASK_COUNT))
    results: list[int | None] = executor.execute(record_fn, items)

    assert results == items
    assert execution_order == items


# T4A.2.5 — пустой ввод возвращает пустой вывод
@pytest.mark.business_logic
def test_parallel_executor_empty_task_list_returns_empty() -> None:
    """execute([]) возвращает [] немедленно, не вызывая ошибку или запуская потоки.

    Защищает короткий путь, который избегает создания ThreadPoolExecutor
    для пустой очереди работ.
    """
    executor = ParallelExecutor(max_workers=_MAX_WORKERS_PARALLEL)
    results: list[Any] = executor.execute(lambda x: x, [])

    assert results == []
