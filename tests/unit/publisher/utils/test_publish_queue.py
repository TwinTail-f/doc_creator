"""Tests for autodoc.publisher.utils.publish_queue.PublishQueue."""

from __future__ import annotations

import pytest

from autodoc.publisher.utils.publish_queue import PublishQueue

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SLEEP_TARGET: str = "autodoc.publisher.utils.publish_queue.time.sleep"
DEFAULT_BATCH_SIZE: int = 2
DEFAULT_DELAY: float = 1.0
ZERO_DELAY: float = 0.0


# ---------------------------------------------------------------------------
# Initialisation — invalid arguments
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_init_raises_on_batch_size_zero() -> None:
    """PublishQueue raises ValueError when batch_size is 0."""
    with pytest.raises(ValueError):
        PublishQueue(batch_size=0)


@pytest.mark.business_logic
def test_init_raises_on_batch_size_negative() -> None:
    """PublishQueue raises ValueError when batch_size is negative."""
    with pytest.raises(ValueError):
        PublishQueue(batch_size=-5)


@pytest.mark.business_logic
def test_init_raises_on_negative_delay() -> None:
    """PublishQueue raises ValueError when batch_delay_seconds is negative."""
    with pytest.raises(ValueError):
        PublishQueue(batch_size=1, batch_delay_seconds=-0.1)


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


@pytest.mark.infrastructure
def test_batch_size_property_readable() -> None:
    """batch_size property returns the value passed to the constructor."""
    queue = PublishQueue(batch_size=3, batch_delay_seconds=ZERO_DELAY)
    assert queue.batch_size == 3


@pytest.mark.infrastructure
def test_batch_delay_property_readable() -> None:
    """batch_delay_seconds property returns the value passed to the constructor."""
    queue = PublishQueue(batch_size=1, batch_delay_seconds=2.5)
    assert queue.batch_delay_seconds == 2.5


# ---------------------------------------------------------------------------
# process — empty input
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_process_empty_list_returns_empty() -> None:
    """process([]) returns an empty list without calling fn."""
    queue = PublishQueue(batch_size=DEFAULT_BATCH_SIZE, batch_delay_seconds=ZERO_DELAY)
    call_count: list[int] = []
    result = queue.process([], lambda x: call_count.append(x))
    assert result == []


@pytest.mark.business_logic
def test_process_empty_list_does_not_call_fn() -> None:
    """fn is never invoked when the item list is empty."""
    queue = PublishQueue(batch_size=DEFAULT_BATCH_SIZE, batch_delay_seconds=ZERO_DELAY)
    calls: list[int] = []
    queue.process([], lambda x: calls.append(x))
    assert calls == []


# ---------------------------------------------------------------------------
# process — correctness
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_process_single_item_calls_fn_once() -> None:
    """fn is called exactly once for a single-element list."""
    queue = PublishQueue(batch_size=DEFAULT_BATCH_SIZE, batch_delay_seconds=ZERO_DELAY)
    calls: list[int] = []
    queue.process([42], lambda x: calls.append(x) or x)
    assert len(calls) == 1


@pytest.mark.business_logic
def test_process_returns_results_in_order() -> None:
    """Results are returned in the same order as the input items."""
    queue = PublishQueue(batch_size=DEFAULT_BATCH_SIZE, batch_delay_seconds=ZERO_DELAY)
    items = [1, 2, 3, 4, 5]
    result = queue.process(items, lambda x: x * 10)
    assert result == [10, 20, 30, 40, 50]


@pytest.mark.business_logic
def test_process_calls_fn_for_every_item() -> None:
    """fn is called exactly len(items) times."""
    queue = PublishQueue(batch_size=DEFAULT_BATCH_SIZE, batch_delay_seconds=ZERO_DELAY)
    items = ["a", "b", "c", "d", "e"]
    calls: list[str] = []
    queue.process(items, lambda x: calls.append(x) or x)
    assert len(calls) == len(items)


# ---------------------------------------------------------------------------
# process — sleep / throttling behaviour
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_process_single_batch_no_sleep(mocker) -> None:
    """time.sleep is not called when all items fit in one batch."""
    mock_sleep = mocker.patch(SLEEP_TARGET)
    queue = PublishQueue(batch_size=10, batch_delay_seconds=DEFAULT_DELAY)
    queue.process([1, 2, 3], lambda x: x)
    mock_sleep.assert_not_called()


@pytest.mark.business_logic
def test_process_two_batches_sleeps_once(mocker) -> None:
    """time.sleep is called exactly once for two batches (3 items, batch_size=2)."""
    mock_sleep = mocker.patch(SLEEP_TARGET)
    queue = PublishQueue(batch_size=2, batch_delay_seconds=DEFAULT_DELAY)
    queue.process([1, 2, 3], lambda x: x)
    assert mock_sleep.call_count == 1


@pytest.mark.business_logic
def test_process_three_batches_sleeps_twice(mocker) -> None:
    """time.sleep is called exactly twice for three batches (5 items, batch_size=2)."""
    mock_sleep = mocker.patch(SLEEP_TARGET)
    queue = PublishQueue(batch_size=2, batch_delay_seconds=DEFAULT_DELAY)
    queue.process([1, 2, 3, 4, 5], lambda x: x)
    assert mock_sleep.call_count == 2


@pytest.mark.business_logic
def test_process_no_sleep_after_last_batch(mocker) -> None:
    """time.sleep is not called after the final batch is processed."""
    mock_sleep = mocker.patch(SLEEP_TARGET)
    queue = PublishQueue(batch_size=2, batch_delay_seconds=DEFAULT_DELAY)
    # 4 items → 2 batches → sleep once (between batch 1 and 2), not after batch 2
    queue.process([1, 2, 3, 4], lambda x: x)
    assert mock_sleep.call_count == 1


@pytest.mark.business_logic
def test_process_zero_delay_no_sleep(mocker) -> None:
    """time.sleep is never called when batch_delay_seconds is 0."""
    mock_sleep = mocker.patch(SLEEP_TARGET)
    queue = PublishQueue(batch_size=1, batch_delay_seconds=ZERO_DELAY)
    queue.process([1, 2, 3], lambda x: x)
    mock_sleep.assert_not_called()


@pytest.mark.business_logic
def test_process_sleep_called_with_correct_delay(mocker) -> None:
    """time.sleep is called with the configured delay value."""
    mock_sleep = mocker.patch(SLEEP_TARGET)
    delay = 3.5
    queue = PublishQueue(batch_size=1, batch_delay_seconds=delay)
    queue.process([1, 2], lambda x: x)
    mock_sleep.assert_called_with(delay)


# ---------------------------------------------------------------------------
# process — error propagation
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_process_propagates_fn_exception() -> None:
    """Exceptions raised by fn propagate to the caller unchanged."""
    queue = PublishQueue(batch_size=DEFAULT_BATCH_SIZE, batch_delay_seconds=ZERO_DELAY)

    def failing_fn(x: int) -> int:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        queue.process([1], failing_fn)
