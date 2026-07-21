"""Модульные тесты для autodoc/common/parallel_executor.py.

ParallelExecutor запускает список вызываемых объектов одновременно с использованием пула потоков.
Тесты проверяют упорядочение результатов, изоляцию исключений и граничные случаи.
"""

import logging
import threading
import time
from typing import Any

import pytest
from pytest_mock import MockerFixture

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
    Это самый важный тест в этом файле: вызывающий код (например, парсинг
    списка файлов или публикация списка страниц) сопоставляет ``results[i]``
    с исходным ``items[i]`` по позиции by design (``zip(items, results)`` и
    т.п.). Если бы порядок совпадал с порядком завершения, а не отправки,
    результат i-й задачи мог бы тихо приписаться совсем другому входному
    элементу — без исключения, просто с неверными данными.
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

    Одного лишь совпадения ``execution_order == items`` недостаточно: список
    без блокировки мог бы случайно оказаться в правильном порядке и при
    фактически параллельном выполнении (например, если бы max_workers
    почему-то не ограничивал пул до одного потока). Поэтому дополнительно
    фиксируем ``threading.get_ident()`` в каждом вызове ``record_fn`` — если
    все вызовы прошли в одном и том же потоке, параллелизма не было
    гарантированно, а не только "по совпадению порядка".
    """
    execution_order: list[int] = []
    thread_ids: set[int] = set()

    def record_fn(index: int) -> int:
        """Добавляет в общий список и фиксирует id потока, затем возвращает индекс."""
        execution_order.append(index)
        thread_ids.add(threading.get_ident())
        return index

    executor = ParallelExecutor(max_workers=_MAX_WORKERS_SEQUENTIAL)
    items: list[int] = list(range(_TASK_COUNT))
    results: list[int | None] = executor.execute(record_fn, items)

    assert results == items
    assert execution_order == items
    assert len(thread_ids) == 1, "все задачи должны были выполниться в одном и том же потоке"


@pytest.mark.business_logic
def test_parallel_executor_empty_task_list_returns_empty_without_spawning_threads(
    mocker: MockerFixture,
) -> None:
    """execute([]) возвращает [] немедленно, не создавая ThreadPoolExecutor."""
    pool_spy = mocker.patch("autodoc.common.parallel_executor.ThreadPoolExecutor")
    executor = ParallelExecutor(max_workers=_MAX_WORKERS_PARALLEL)

    results: list[Any] = executor.execute(lambda x: x, [])

    assert results == []
    pool_spy.assert_not_called()


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "extra_kwargs, expected_batch_size, expected_batch_delay, match",
    [
        # отрицательный batch_size откатывается на дефолт 0 (пакетная обработка отключена)
        pytest.param({"batch_size": -1}, 0, 0.0, "batch_size", id="negative-batch-size"),
        # отрицательный batch_delay откатывается на дефолт 0.0 (пауза между пакетами отключена).
        # batch_size=1 задан отдельно и намеренно НЕ равен 0: batch_size=1 — это
        # не то же самое, что отключённый батчинг (см.
        # test_parallel_executor_batch_size_boundary_behavior ниже) — при
        # любом batch_size > 0, включая 1, исполнение всё равно идёт через
        # _execute_in_batches, так что здесь нужен именно валидный
        # положительный batch_size, чтобы было к чему применять batch_delay.
        pytest.param(
            {"batch_size": 1, "batch_delay": -0.5}, 1, 0.0, "batch_delay", id="negative-batch-delay"
        ),
    ],
)
def test_parallel_executor_negative_constructor_arg_warns_and_falls_back_to_default(
    caplog: pytest.LogCaptureFixture,
    extra_kwargs: dict[str, float],
    expected_batch_size: int,
    expected_batch_delay: float,
    match: str,
) -> None:
    """Отрицательные batch_size/batch_delay не обрывают публикацию: конструктор логирует
    WARNING и откатывается на дефолт (0 / 0.0), а не поднимает исключение.
    """
    with caplog.at_level(logging.WARNING):
        executor = ParallelExecutor(max_workers=_MAX_WORKERS_PARALLEL, **extra_kwargs)

    assert executor._batch_size == expected_batch_size
    assert executor._batch_delay == expected_batch_delay

    warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any(match in m for m in warning_messages)

    # Исполнитель с откаченным значением остаётся рабочим, а не в поломанном состоянии.
    results = executor.execute(lambda x: x, list(range(_TASK_COUNT)))
    assert results == list(range(_TASK_COUNT))


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "batch_size, expect_batches_called, expected_sleep_calls",
    [
        # batch_size=0 (граница, а не отрицательное значение, должен полностью
        # обходить пакетную ветку: _execute_in_batches не вызывается, пауз
        # между "пакетами" нет.
        pytest.param(0, False, 0, id="batch-size-0-skips-batching-entirely"),
        # batch_size=1 - не то же самое, что отключённый батчинг, и это не баг:
        # задачи всё равно идут через _execute_in_batches со своей паузой
        # batch_delay между каждой парой соседних задач (TASK_COUNT - 1 пауза).
        # Смысл режима — троттлинг обращений к внешнему сервису (не чаще
        # одного запроса за раз), а не последовательность сама по себе;
        # поэтому batch_size=1 с ненулевым batch_delay намеренно ведёт себя
        # иначе, чем batch_size=0 (см. docstring ParallelExecutor).
        pytest.param(1, True, _TASK_COUNT - 1, id="batch-size-1-still-batches-with-delay"),
        # batch_size=3 при TASK_COUNT=4: два пакета (3 задачи + 1 задача) ->
        # ровно одна пауза между ними. Добавлено, чтобы проверить не только
        # крайние 0/1, но и типичный batch_size > 1 с несколькими полными
        # пакетами. batch_size=-1 сюда намеренно не добавлен: он уже покрыт
        # test_parallel_executor_negative_constructor_arg_warns_and_falls_back_to_default
        # (сворачивается в 0 ещё в конструкторе), так что в этом тесте вёл
        # бы себя ровно как batch_size=0 - новой информации о границе
        # батчинга такой повтор бы не добавил.
        pytest.param(3, True, 1, id="batch-size-3-multiple-batches"),
    ],
)
def test_parallel_executor_batch_size_boundary_behavior(
    mocker: MockerFixture,
    batch_size: int,
    expect_batches_called: bool,
    expected_sleep_calls: int,
) -> None:
    """Поведение на границах и в общем случае batch_size (0, 1 и обычное
    значение > 1) проверяется не по итоговому списку результатов (он
    одинаков во всех режимах), а по фактическим вызовам: попал ли путь
    выполнения в ``_execute_in_batches`` и сколько раз реально была вызвана
    пауза ``time.sleep`` между пакетами.
    """
    batches_spy = mocker.spy(ParallelExecutor, "_execute_in_batches")
    mock_sleep = mocker.patch("autodoc.common.parallel_executor.time.sleep")
    executor = ParallelExecutor(
        max_workers=_MAX_WORKERS_PARALLEL, batch_size=batch_size, batch_delay=0.01
    )

    results: list[int | None] = executor.execute(lambda x: x, list(range(_TASK_COUNT)))

    assert results == list(range(_TASK_COUNT))
    assert batches_spy.called is expect_batches_called
    assert mock_sleep.call_count == expected_sleep_calls
