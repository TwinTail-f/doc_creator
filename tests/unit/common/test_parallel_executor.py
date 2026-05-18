"""Unit tests for autodoc/common/parallel_executor.py.

ParallelExecutor runs a list of callables concurrently using a thread pool.
Tests verify result ordering, exception isolation, and edge cases.
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


# ---------------------------------------------------------------------------
# T4A.2.1 — results come back in submission order despite staggered completion
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_parallel_executor_results_in_submission_order() -> None:
    """Results are returned in submission order, not in completion order.

    Task 0 sleeps longest so it finishes last; task 3 sleeps shortest so it
    finishes first. The executor must preserve the original index mapping.
    This is the most critical test in this file.
    """
    sleep_durations: list[float] = [
        _SLEEP_LONG_SEC,  # task 0 — finishes last
        _SLEEP_SHORT_SEC * 2,
        _SLEEP_SHORT_SEC,
        0.0,  # task 3 — finishes first
    ]
    expected_values: list[int] = list(range(_TASK_COUNT))

    def staggered_fn(index_and_sleep: tuple[int, float]) -> int:
        """Sleep for the given duration then return the task index as the result."""
        index, sleep = index_and_sleep
        time.sleep(sleep)
        return index

    executor = ParallelExecutor(max_workers=_MAX_WORKERS_PARALLEL)
    items: list[tuple[int, float]] = list(zip(expected_values, sleep_durations))
    results: list[int | None] = executor.execute(staggered_fn, items)

    assert results == expected_values


# ---------------------------------------------------------------------------
# T4A.2.2 — one failing task does not cancel the others
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_parallel_executor_exception_in_one_task_does_not_cancel_others() -> None:
    """Exceptions in individual tasks are isolated; other tasks still produce results.

    If one task raises, its slot becomes None while the remaining tasks
    run to completion. No exception propagates to the caller.
    """

    def task_fn(index: int) -> int | None:
        """Return the index for tasks 0 and 2; raise ValueError for task 1."""
        if index == 1:
            raise ValueError("intentional failure")
        return index

    executor = ParallelExecutor(max_workers=_MAX_WORKERS_PARALLEL)
    results: list[int | None] = executor.execute(task_fn, [0, 1, 2])

    assert results[0] == 0, "task 0 must produce its result"
    assert results[1] is None, "failing task must produce None"
    assert results[2] == 2, "task 2 must produce its result"


# ---------------------------------------------------------------------------
# T4A.2.3 — all tasks raising does not hang
# ---------------------------------------------------------------------------


@pytest.mark.timeout(_TIMEOUT_GUARD_SEC)
@pytest.mark.business_logic
def test_parallel_executor_all_tasks_raise_does_not_hang() -> None:
    """execute() returns without deadlocking when every task raises RuntimeError.

    All results are None; no exception propagates to the caller.
    """

    def always_fail(_: Any) -> None:
        raise RuntimeError("always fails")

    executor = ParallelExecutor(max_workers=_MAX_WORKERS_PARALLEL)
    results: list[None] = executor.execute(always_fail, [0, 1, 2])

    assert results == [None, None, None]


# ---------------------------------------------------------------------------
# T4A.2.4 — max_workers=1 executes tasks sequentially
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_parallel_executor_max_workers_one_is_sequential() -> None:
    """With max_workers=1 tasks execute sequentially in submission order.

    A single worker prevents any parallelism; results must be in submission order
    and can be verified by appending to a plain list without a lock.
    """
    execution_order: list[int] = []

    def record_fn(index: int) -> int:
        """Append to the shared list then return the index."""
        execution_order.append(index)
        return index

    executor = ParallelExecutor(max_workers=_MAX_WORKERS_SEQUENTIAL)
    items: list[int] = list(range(_TASK_COUNT))
    results: list[int | None] = executor.execute(record_fn, items)

    assert results == items
    assert execution_order == items


# ---------------------------------------------------------------------------
# T4A.2.5 — empty input returns empty output
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_parallel_executor_empty_task_list_returns_empty() -> None:
    """execute([]) returns [] immediately without raising or spinning up threads.

    Guards the short-circuit path that avoids creating a ThreadPoolExecutor
    for an empty work queue.
    """
    executor = ParallelExecutor(max_workers=_MAX_WORKERS_PARALLEL)
    results: list[Any] = executor.execute(lambda x: x, [])

    assert results == []
