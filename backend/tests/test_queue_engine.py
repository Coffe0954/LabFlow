"""Unit-тесты алгоритма очереди (CLAUDE.md, раздел 7)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.services.queue_engine import (
    QueueItem,
    effective_key,
    order_queue,
    rank_queue,
    remaining_minutes,
)

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


def item(id: int, duration: float, waited_min: float = 0, pinned: int | None = None) -> QueueItem:
    return QueueItem(
        id=id,
        created_at=NOW - timedelta(minutes=waited_min),
        duration_min=duration,
        pinned_position=pinned,
    )


def ids(items: list[QueueItem]) -> list[int]:
    return [i.id for i in items]


def test_fast_lab_overtakes_long() -> None:
    """Быстрая лаба обгоняет длинную, если записались примерно одновременно."""
    long_lab = item(1, duration=40, waited_min=2)
    fast_lab = item(2, duration=10, waited_min=0)
    assert ids(order_queue([long_lab, fast_lab], NOW)) == [2, 1]


def test_long_waiter_overtakes_new_short() -> None:
    """Долго ждущий обгоняет новую короткую запись (aging)."""
    old_long = item(1, duration=60, waited_min=130)  # key = 60 − 0.5·130 = −5
    new_short = item(2, duration=5)  # key = 5
    assert ids(order_queue([new_short, old_long], NOW)) == [1, 2]


@pytest.mark.parametrize("k", [0.1, 0.5, 2.0])
@pytest.mark.parametrize("duration", [5, 30, 120])
def test_aging_guarantee_after_d_over_k(k: float, duration: float) -> None:
    """Через D/k минут запись обгоняет любую новую — бесконечного ожидания нет."""
    waiter = item(1, duration=duration, waited_min=duration / k + 0.01)
    newcomer = item(2, duration=0)  # самая короткая из возможных
    assert ids(order_queue([newcomer, waiter], NOW, k)) == [1, 2]


def test_key_decreases_while_waiting() -> None:
    entry = item(1, duration=20, waited_min=10)
    assert effective_key(entry, NOW) == pytest.approx(15)
    assert effective_key(entry, NOW + timedelta(minutes=10)) == pytest.approx(10)


def test_pinned_position_is_kept() -> None:
    """Закреплённая позиция сохраняется, остальные сортируются вокруг неё."""
    entries = [
        item(1, 10),
        item(2, 20),
        item(3, 90, pinned=1),  # самый длинный, но закреплён первым
        item(4, 30),
    ]
    assert ids(order_queue(entries, NOW)) == [3, 1, 2, 4]

    entries[2] = item(3, 90, pinned=3)
    assert ids(order_queue(entries, NOW)) == [1, 2, 3, 4]


def test_pinned_beyond_end_goes_last() -> None:
    entries = [item(1, 50, pinned=10), item(2, 10), item(3, 20)]
    assert ids(order_queue(entries, NOW)) == [2, 3, 1]


def test_two_pins_on_same_place_do_not_lose_anyone() -> None:
    entries = [item(1, 10, waited_min=5, pinned=1), item(2, 10, pinned=1), item(3, 5)]
    result = ids(order_queue(entries, NOW))
    assert result[:2] == [1, 2]  # кто закреплён раньше (раньше записался) — выше
    assert sorted(result) == [1, 2, 3]


def test_pins_at_the_end_fill_free_slot_above() -> None:
    entries = [item(1, 10, pinned=3), item(2, 10, pinned=3), item(3, 10, pinned=3)]
    assert sorted(ids(order_queue(entries, NOW))) == [1, 2, 3]


def test_empty_queue() -> None:
    assert order_queue([], NOW) == []
    assert rank_queue([], NOW, current_remaining_min=15) == []


def test_equal_keys_first_come_first_served() -> None:
    """При равном ключе раньше идёт тот, кто записался раньше."""
    # key у обоих = 10: 10 − 0 и 20 − 0.5·20
    newer = item(1, duration=10, waited_min=0)
    older = item(2, duration=20, waited_min=20)
    assert ids(order_queue([newer, older], NOW)) == [2, 1]

    same_a = item(5, duration=15, waited_min=3)
    same_b = item(4, duration=15, waited_min=3)  # тот же created_at — порядок по id
    assert ids(order_queue([same_a, same_b], NOW)) == [4, 5]


def test_wait_time_is_correct() -> None:
    """Ожидание = остаток у текущего + сумма D всех впереди."""
    entries = [item(1, 10), item(2, 20), item(3, 30)]
    ranked = rank_queue(entries, NOW, current_remaining_min=7)
    assert [r.position for r in ranked] == [1, 2, 3]
    assert [r.wait_minutes for r in ranked] == [7, 17, 37]


def test_wait_time_respects_pins() -> None:
    entries = [item(1, 10), item(2, 40, pinned=1)]
    ranked = rank_queue(entries, NOW)
    assert [(r.item.id, r.wait_minutes) for r in ranked] == [(2, 0), (1, 40)]


def test_remaining_minutes_for_current() -> None:
    called = NOW - timedelta(minutes=8)
    assert remaining_minutes(20, called, NOW) == pytest.approx(12)
    assert remaining_minutes(5, called, NOW) == 0  # затянулось — не уходим в минус
    assert remaining_minutes(20, None, NOW) == 20


@pytest.mark.parametrize("bad_k", [0, -0.5])
def test_k_must_be_positive(bad_k: float) -> None:
    with pytest.raises(ValueError):
        order_queue([item(1, 10)], NOW, bad_k)
