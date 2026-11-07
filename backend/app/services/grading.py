"""Проверка ответов на тест. Чистые функции."""

from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class GradableQuestion(Protocol):
    id: int
    kind: str
    correct: Any


def _norm(text: object) -> str:
    return " ".join(str(text).strip().lower().split())


def is_correct(kind: str, correct: Any, value: Any) -> bool:
    """single: индекс варианта; multi: набор индексов; text: одна из допустимых строк."""
    if value is None:
        return False
    try:
        if kind == "single":
            return int(value) == int(correct)
        if kind == "multi":
            return {int(v) for v in value} == {int(c) for c in correct}
        if kind == "text":
            accepted = correct if isinstance(correct, list) else [correct]
            return _norm(value) in {_norm(c) for c in accepted}
    except (TypeError, ValueError):
        return False
    return False


def grade(questions: Sequence[GradableQuestion], answers: Mapping[int, Any]) -> float:
    """Процент правильных ответов (0..100), округлённый до десятых."""
    if not questions:
        return 0.0
    right = sum(1 for q in questions if is_correct(q.kind, q.correct, answers.get(q.id)))
    return round(100 * right / len(questions), 1)
