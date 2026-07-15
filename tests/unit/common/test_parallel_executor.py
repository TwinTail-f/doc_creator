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


@pytest.mark.business_logic
def test_parallel_executor_all_tasks_failing_returns_all_none() -> None:
    """Если ValueError падает в каждой задаче, execute() возвращает [None, None, None].

    Граничный случай изоляции исключений (см.
    ``test_parallel_executor_exception_in_one_task_does_not_cancel_others``):
    здесь падают все задачи, а не одна, — то есть в пуле нет ни одного
    успешного результата, который мог бы замаскировать ошибку агрегации.
    """

    def always_fail(_: Any) -> None:
        raise ValueError("всегда падает")

    executor = ParallelExecutor(max_workers=_MAX_WORKERS_PARALLEL)
    results: list[None] = executor.execute(always_fail, [0, 1, 2])

    assert results == [None, None, None]


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


@pytest.mark.business_logic
def test_parallel_executor_empty_task_list_returns_empty() -> None:
    """execute([]) возвращает [] немедленно, не вызывая ошибку или запуская потоки.

    Защищает короткий путь, который избегает создания ThreadPoolExecutor
    для пустой очереди работ.
    """
    executor = ParallelExecutor(max_workers=_MAX_WORKERS_PARALLEL)
    results: list[Any] = executor.execute(lambda x: x, [])

    assert results == []


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "extra_kwargs, match",
    [
        # отрицательный batch_size
        pytest.param({"batch_size": -1}, "batch_size", id="negative-batch-size"),
        # отрицательный batch_delay (batch_size задан, чтобы задержка вообще была применима)
        pytest.param({"batch_size": 1, "batch_delay": -0.5}, "batch_delay", id="negative-batch-delay"),
    ],
)
def test_parallel_executor_negative_constructor_arg_raises_value_error(
    extra_kwargs: dict[str, float], match: str
) -> None:
    """Конструктор отклоняет отрицательные ``batch_size``/``batch_delay``, не откатываясь на дефолт.

    Отрицательное значение — явная ошибка вызывающего кода (сетевая операция,
    молчаливая подмена значения недопустима), поэтому конструктор должен упасть
    сразу, а не создать исполнитель с некорректным внутренним состоянием.
    """
    with pytest.raises(ValueError, match=match):
        ParallelExecutor(max_workers=_MAX_WORKERS_PARALLEL, **extra_kwargs)


@pytest.mark.business_logic
def test_parallel_executor_zero_batch_size_is_valid_and_disables_batching() -> None:
    """``batch_size=0`` (граница, а не отрицательное значение) — валидный дефолт.

    Отделяет граничный случай ``== 0`` от собственно проверяемого ``< 0``:
    ноль не должен попадать под валидацию как ошибка.
    """
    executor = ParallelExecutor(max_workers=_MAX_WORKERS_PARALLEL, batch_size=0)
    results: list[int | None] = executor.execute(lambda x: x, list(range(_TASK_COUNT)))

    assert results == list(range(_TASK_COUNT))
