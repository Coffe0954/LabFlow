from dataclasses import dataclass
from typing import Any

from app.services.grading import grade, is_correct


@dataclass
class Q:
    id: int
    kind: str
    correct: Any


def test_single() -> None:
    assert is_correct("single", 1, 1)
    assert is_correct("single", 1, "1")
    assert not is_correct("single", 1, 0)
    assert not is_correct("single", 1, None)


def test_multi_order_does_not_matter() -> None:
    assert is_correct("multi", [0, 2], [2, 0])
    assert not is_correct("multi", [0, 2], [0])
    assert not is_correct("multi", [0, 2], "мусор")


def test_text_case_and_spaces_ignored() -> None:
    assert is_correct("text", ["O(n log n)"], "  o(n   LOG n) ")
    assert is_correct("text", ["стек", "stack"], "Stack")
    assert not is_correct("text", ["стек"], "очередь")


def test_grade_percent() -> None:
    questions = [Q(1, "single", 0), Q(2, "multi", [1, 2]), Q(3, "text", ["да"])]
    assert grade(questions, {1: 0, 2: [2, 1], 3: "нет"}) == 66.7
    assert grade(questions, {}) == 0
    assert grade([], {}) == 0
