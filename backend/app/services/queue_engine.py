"""Алгоритм очереди — ядро LabFlow (см. CLAUDE.md, раздел 7).

Это чистые функции: никаких обращений к БД, только входные данные и текущее время.

    D   — длительность записи (сумма expected_minutes выбранных лаб), мин
    W   — сколько студент уже ждёт: now − created_at, мин
    key — эффективный ключ: D − k·W (k > 0)

Очередь сортируется по key по возрастанию: короткие сдачи раньше, а пока студент ждёт,
его key уменьшается (aging). Через D/k минут ожидания key < 0, а у любой новой записи
key = D_new ≥ 0, поэтому долго ждущий гарантированно обгоняет новичков —
бесконечного ожидания нет. Поэтому k обязан быть строго больше нуля.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

DEFAULT_K = 0.5


@dataclass(frozen=True)
class QueueItem:
    """Запись в статусе waiting — то, что нужно алгоритму."""

    id: int
    created_at: datetime
    duration_min: float
    pinned_position: int | None = None  # 1-based место, закреплённое преподавателем


@dataclass(frozen=True)
class RankedItem:
    item: QueueItem
    position: int  # 1-based место в очереди
    key: float
    wait_minutes: float  # примерное время до начала сдачи


def waited_minutes(created_at: datetime, now: datetime) -> float:
    """W — сколько минут запись уже ждёт (не меньше нуля)."""
    return max(0.0, (now - created_at).total_seconds() / 60)


def effective_key(item: QueueItem, now: datetime, k: float = DEFAULT_K) -> float:
    """key = D − k·W."""
    return item.duration_min - k * waited_minutes(item.created_at, now)


def _check_k(k: float) -> None:
    if k <= 0:
        raise ValueError("Коэффициент aging k должен быть больше 0, иначе возможно вечное ожидание")


def order_queue(items: Sequence[QueueItem], now: datetime, k: float = DEFAULT_K) -> list[QueueItem]:
    """Возвращает записи в порядке очереди.

    1. Незакреплённые сортируются по (key, created_at, id): при равном key раньше тот,
       кто записался раньше.
    2. Закреплённые ставятся на свои места. Если место больше длины очереди — в конец.
       Если место уже занято другим закреплённым — на ближайшее свободное ниже
       (а если ниже всё занято — на ближайшее свободное выше).
    3. Свободные места заполняются незакреплёнными по порядку.
    """
    _check_k(k)
    n = len(items)
    unpinned = sorted(
        (i for i in items if i.pinned_position is None),
        key=lambda i: (effective_key(i, now, k), i.created_at, i.id),
    )
    pinned = sorted(
        (i for i in items if i.pinned_position is not None),
        key=lambda i: (i.pinned_position or 0, i.created_at, i.id),
    )

    slots: list[QueueItem | None] = [None] * n
    for item in pinned:
        idx = max(1, min(item.pinned_position or 1, n)) - 1
        while idx < n and slots[idx] is not None:
            idx += 1
        if idx == n:
            idx = max(j for j in range(n) if slots[j] is None)
        slots[idx] = item

    rest = iter(unpinned)
    return [slot if slot is not None else next(rest) for slot in slots]


def remaining_minutes(duration_min: float, called_at: datetime | None, now: datetime) -> float:
    """Сколько ещё примерно займёт сдача у того, кого уже вызвали."""
    if called_at is None:
        return duration_min
    return max(0.0, duration_min - waited_minutes(called_at, now))


def rank_queue(
    items: Sequence[QueueItem],
    now: datetime,
    k: float = DEFAULT_K,
    current_remaining_min: float = 0.0,
) -> list[RankedItem]:
    """Порядок очереди с местом и временем ожидания.

    Время ожидания для позиции i = остаток у текущего сдающего + сумма D всех записей
    перед i.
    """
    result: list[RankedItem] = []
    acc = max(0.0, current_remaining_min)
    for position, item in enumerate(order_queue(items, now, k), start=1):
        result.append(RankedItem(item, position, effective_key(item, now, k), acc))
        acc += item.duration_min
    return result
