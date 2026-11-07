"""Сценарии API, включая end-to-end сценарий из CLAUDE.md (раздел 10)."""

from typing import Any

from httpx import AsyncClient

from app.models import UserRole
from app.ws.hub import hub
from tests.conftest import Api


class FakeSocket:
    """Подменяет WebSocket: собирает всё, что разослал сервер."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def send_json(self, data: dict[str, Any]) -> None:
        self.messages.append(data)


async def setup_course(api: Api, teacher: dict[str, str]) -> dict[str, Any]:
    disc = await api.ok("POST", "/disciplines", teacher, json={"title": "ООП"})
    short = await api.ok(
        "POST",
        "/labs",
        teacher,
        json={"discipline_id": disc["id"], "number": 1, "title": "Классы", "expected_minutes": 10},
    )
    long = await api.ok(
        "POST",
        "/labs",
        teacher,
        json={
            "discipline_id": disc["id"],
            "number": 2,
            "title": "Наследование",
            "expected_minutes": 40,
        },
    )
    queue = await api.ok(
        "POST",
        "/queues",
        teacher,
        json={
            "discipline_id": disc["id"],
            "date": "2026-11-07",
            "starts_at": "09:00",
            "ends_at": "10:30",
        },
    )
    return {"disc": disc, "short": short, "long": long, "queue": queue}


async def test_register_login_me(client: AsyncClient) -> None:
    r = await client.post(
        "/auth/register",
        json={"email": "Ivan@Test.ru", "password": "secret123", "full_name": "Иван Иванов"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["role"] == "student"
    assert "password_hash" not in body["user"]

    r = await client.post(
        "/auth/register",
        json={"email": "ivan@test.ru", "password": "secret123", "full_name": "Дубль"},
    )
    assert r.status_code == 409
    assert r.json() == {"detail": "Пользователь с таким email уже есть"}

    r = await client.post("/auth/login", json={"email": "ivan@test.ru", "password": "wrong"})
    assert r.status_code == 401

    r = await client.post("/auth/login", json={"email": "ivan@test.ru", "password": "secret123"})
    token = r.json()["access_token"]
    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.json()["email"] == "ivan@test.ru"


async def test_errors_have_single_format(client: AsyncClient) -> None:
    r = await client.post("/auth/register", json={"email": "bad", "password": "1"})
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str)

    r = await client.get("/queues")
    assert r.status_code == 401
    assert r.json() == {"detail": "Требуется вход"}


async def test_permissions_are_checked_on_server(api: Api) -> None:
    teacher = await api.user(UserRole.teacher)
    student = await api.user(UserRole.student)
    other_teacher = await api.user(UserRole.teacher)
    c = await setup_course(api, teacher)
    qid = c["queue"]["id"]

    r = await api.client.post(
        "/queues",
        headers=student,
        json={
            "discipline_id": c["disc"]["id"],
            "date": "2026-11-07",
            "starts_at": "09:00",
            "ends_at": "10:00",
        },
    )
    assert r.status_code == 403
    assert (await api.client.post(f"/queues/{qid}/call-next", headers=student)).status_code == 403
    assert (
        await api.client.post(f"/queues/{qid}/call-next", headers=other_teacher)
    ).status_code == 403
    assert (await api.client.get("/users", headers=teacher)).status_code == 403
    r = await api.client.post(
        f"/queues/{qid}/entries", headers=teacher, json={"lab_ids": [c["short"]["id"]]}
    )
    assert r.status_code == 403

    # Чужую запись студент удалить не может.
    entry = await api.ok(
        "POST", f"/queues/{qid}/entries", student, json={"lab_ids": [c["short"]["id"]]}
    )
    another = await api.user(UserRole.student)
    assert (await api.client.delete(f"/entries/{entry['id']}", headers=another)).status_code == 403
    assert (await api.client.get(f"/entries/{entry['id']}", headers=another)).status_code == 403


async def test_join_rules(api: Api) -> None:
    teacher = await api.user(UserRole.teacher)
    student = await api.user(UserRole.student)
    c = await setup_course(api, teacher)
    qid = c["queue"]["id"]

    r = await api.client.post(f"/queues/{qid}/entries", headers=student, json={"lab_ids": [999]})
    assert r.status_code == 404

    await api.ok("POST", f"/queues/{qid}/entries", student, json={"lab_ids": [c["short"]["id"]]})
    r = await api.client.post(
        f"/queues/{qid}/entries", headers=student, json={"lab_ids": [c["long"]["id"]]}
    )
    assert r.status_code == 409  # одна активная запись в очереди

    await api.ok("PATCH", f"/queues/{qid}", teacher, json={"status": "closed"})
    late = await api.user(UserRole.student)
    r = await api.client.post(
        f"/queues/{qid}/entries", headers=late, json={"lab_ids": [c["short"]["id"]]}
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "Очередь закрыта"


async def test_full_scenario(api: Api) -> None:
    """Регистрация → запись → ожидание → вызов → тест → результат → пересчёт у всех."""
    teacher = await api.user(UserRole.teacher, "Петров П.П.")
    c = await setup_course(api, teacher)
    qid = c["queue"]["id"]
    test = await api.ok(
        "POST",
        "/tests",
        teacher,
        json={"lab_id": c["long"]["id"], "title": "Тест по наследованию", "time_limit_min": 5},
    )
    q1 = await api.ok(
        "POST",
        f"/tests/{test['id']}/questions",
        teacher,
        json={
            "text": "Множественное наследование в Python есть?",
            "kind": "single",
            "options": ["Да", "Нет"],
            "correct": 0,
        },
    )
    q2 = await api.ok(
        "POST",
        f"/tests/{test['id']}/questions",
        teacher,
        json={"text": "Ключевое слово для вызова родителя", "kind": "text", "correct": "super"},
    )

    # Регистрация студента через API.
    r = await api.client.post(
        "/auth/register",
        json={
            "email": "anna@test.ru",
            "password": "secret123",
            "full_name": "Анна",
            "group": "312",
        },
    )
    anna = {"Authorization": f"Bearer {r.json()['access_token']}"}
    boris = await api.user(UserRole.student, "Борис")

    # Подписчик WebSocket — проверяем, что пересчёт приходит всем.
    socket = FakeSocket()
    hub.add(qid, socket)  # type: ignore[arg-type]
    try:
        queues = await api.ok("GET", "/queues", anna)
        assert [q["id"] for q in queues] == [qid]

        await api.ok("POST", f"/queues/{qid}/entries", anna, json={"lab_ids": [c["long"]["id"]]})
        boris_entry = await api.ok(
            "POST", f"/queues/{qid}/entries", boris, json={"lab_ids": [c["short"]["id"]]}
        )
        assert socket.messages[-1]["type"] == "queue_state"

        state = await api.ok("GET", f"/queues/{qid}", anna)
        # Короткая лаба Бориса обогнала длинную лабу Анны.
        assert [e["student_name"] for e in state["waiting"]] == ["Борис", "Анна"]
        assert [e["wait_minutes"] for e in state["waiting"]] == [0, 10]
        assert "email" not in state["waiting"][0]  # минимум персональных данных

        # Преподаватель перетаскивает Анну на первое место.
        anna_entry = state["waiting"][1]
        await api.ok(
            "PATCH", f"/entries/{anna_entry['id']}/position", teacher, json={"position": 1}
        )
        state = socket.messages[-1]["data"]
        assert [e["student_name"] for e in state["waiting"]] == ["Анна", "Борис"]

        # Вызов следующего — Анна, закрепление снимается.
        called = await api.ok("POST", f"/queues/{qid}/call-next", teacher)
        assert called["id"] == anna_entry["id"]
        assert called["status"] == "called"
        assert called["pinned_position"] is None
        state = socket.messages[-1]["data"]
        assert [e["student_name"] for e in state["in_progress"]] == ["Анна"]
        assert state["waiting"][0]["wait_minutes"] == 40  # остаток у текущего сдающего

        # Запуск теста.
        attempt = await api.ok("POST", f"/entries/{anna_entry['id']}/test/start", teacher, json={})
        assert attempt["test_title"] == "Тест по наследованию"
        current = await api.ok("GET", "/attempts/current", anna)
        assert current["id"] == attempt["id"]
        assert "correct" not in current["questions"][0]  # студент не видит ответы
        assert (await api.client.get("/attempts/current", headers=boris)).json() is None
        r = await api.client.post(f"/attempts/{attempt['id']}/finish", headers=boris)
        assert r.status_code == 403

        # Студент отвечает (с перезаписью) и завершает тест.
        await api.ok(
            "POST",
            f"/attempts/{attempt['id']}/answers",
            anna,
            json={"answers": [{"question_id": q1["id"], "value": 1}]},
        )
        await api.ok(
            "POST",
            f"/attempts/{attempt['id']}/answers",
            anna,
            json={
                "answers": [
                    {"question_id": q1["id"], "value": 0},
                    {"question_id": q2["id"], "value": " Super "},
                ]
            },
        )
        result = await api.ok("POST", f"/attempts/{attempt['id']}/finish", anna)
        assert result["score"] == 100

        # Преподаватель видит карточку с результатом и фиксирует «сдал».
        card = await api.ok("GET", f"/entries/{anna_entry['id']}", teacher)
        assert card["status"] == "reviewing"
        assert card["attempts"][0]["score"] == 100
        assert all(a["is_correct"] for a in card["attempts"][0]["review"])
        await api.ok(
            "PATCH", f"/entries/{anna_entry['id']}/status", teacher, json={"status": "passed"}
        )

        state = socket.messages[-1]["data"]
        assert state["in_progress"] == []
        assert state["finished_count"] == 1
        assert state["waiting"][0]["id"] == boris_entry["id"]
        assert state["waiting"][0]["wait_minutes"] == 0

        # Борис выходит сам.
        r = await api.client.delete(f"/entries/{boris_entry['id']}", headers=boris)
        assert r.status_code == 204
        assert socket.messages[-1]["data"]["waiting"] == []
    finally:
        hub.remove(qid, socket)  # type: ignore[arg-type]

    stats = await api.ok("GET", f"/queues/{qid}/stats", teacher)
    assert stats["passed"] == 1 and stats["left"] == 1 and stats["avg_score"] == 100

    mine = await api.ok("GET", "/stats/me", anna)
    assert mine["passed_count"] == 1
    assert mine["entries"][0]["score"] == 100
    card = await api.ok("GET", f"/entries/{anna_entry['id']}", anna)
    assert card["attempts"][0]["review"] == []  # правильные ответы студенту не отдаём


async def test_status_transitions_and_pins_follow_queue(api: Api) -> None:
    teacher = await api.user(UserRole.teacher)
    c = await setup_course(api, teacher)
    qid = c["queue"]["id"]
    students = [await api.user(UserRole.student, f"S{i}") for i in range(3)]
    entries = [
        await api.ok("POST", f"/queues/{qid}/entries", s, json={"lab_ids": [c["short"]["id"]]})
        for s in students
    ]
    # Закрепляем последнего на 2-е место.
    await api.ok("PATCH", f"/entries/{entries[2]['id']}/position", teacher, json={"position": 2})
    state = await api.ok("GET", f"/queues/{qid}", teacher)
    assert [e["id"] for e in state["waiting"]] == [
        entries[0]["id"],
        entries[2]["id"],
        entries[1]["id"],
    ]

    # Первый ушёл на сдачу — закреплённый поднимается на 1-е место, а не застревает.
    await api.ok("POST", f"/queues/{qid}/call-next", teacher)
    state = await api.ok("GET", f"/queues/{qid}", teacher)
    assert state["waiting"][0]["id"] == entries[2]["id"]
    assert state["waiting"][0]["pinned_position"] == 1

    # Недопустимый переход.
    r = await api.client.patch(
        f"/entries/{entries[1]['id']}/status", headers=teacher, json={"status": "passed"}
    )
    assert r.status_code == 409

    # Вызванного можно вернуть в очередь.
    await api.ok(
        "PATCH", f"/entries/{entries[0]['id']}/status", teacher, json={"status": "waiting"}
    )
    state = await api.ok("GET", f"/queues/{qid}", teacher)
    assert len(state["waiting"]) == 3 and state["in_progress"] == []

    # Пустая очередь — вызвать некого.
    for e in entries:
        await api.ok("DELETE", f"/entries/{e['id']}", teacher)
    r = await api.client.post(f"/queues/{qid}/call-next", headers=teacher)
    assert r.status_code == 409


async def test_question_validation(api: Api) -> None:
    teacher = await api.user(UserRole.teacher)
    c = await setup_course(api, teacher)
    test = await api.ok("POST", "/tests", teacher, json={"lab_id": c["short"]["id"], "title": "T"})
    url = f"/tests/{test['id']}/questions"
    bad = [
        {"text": "?", "kind": "single", "options": ["a"], "correct": 0},
        {"text": "?", "kind": "single", "options": ["a", "b"], "correct": 5},
        {"text": "?", "kind": "multi", "options": ["a", "b"], "correct": []},
        {"text": "?", "kind": "text", "correct": ""},
    ]
    for body in bad:
        r = await api.client.post(url, headers=teacher, json=body)
        assert r.status_code == 422, body

    # Тест без вопросов запустить нельзя.
    student = await api.user(UserRole.student)
    qid = c["queue"]["id"]
    await api.ok("POST", f"/queues/{qid}/entries", student, json={"lab_ids": [c["short"]["id"]]})
    called = await api.ok("POST", f"/queues/{qid}/call-next", teacher)
    r = await api.client.post(f"/entries/{called['id']}/test/start", headers=teacher, json={})
    assert r.status_code == 409


async def test_ads_and_admin(api: Api) -> None:
    admin = await api.user(UserRole.admin)
    student = await api.user(UserRole.student)
    assert (await api.client.get("/ads/active")).json() is None
    ad = await api.ok(
        "POST",
        "/ads",
        admin,
        json={"image_url": "https://example.com/b.png", "link": "https://example.com"},
    )
    assert (await api.client.get("/ads/active")).json()["id"] == ad["id"]
    await api.ok("PATCH", f"/ads/{ad['id']}", admin, json={"active": False})
    assert (await api.client.get("/ads/active")).json() is None
    assert (await api.client.post("/ads", headers=student, json={})).status_code == 403

    users = await api.ok("GET", "/users", admin)
    student_id = next(u["id"] for u in users if u["role"] == "student")
    updated = await api.ok("PATCH", f"/users/{student_id}", admin, json={"role": "teacher"})
    assert updated["role"] == "teacher"


async def test_expired_attempt_is_closed_for_teacher(api: Api) -> None:
    """Студент не открыл тест, время вышло — преподаватель видит результат, а не «идёт тест»."""
    from datetime import timedelta

    from app.db.base import utcnow
    from app.models import Attempt

    teacher = await api.user(UserRole.teacher)
    student = await api.user(UserRole.student)
    c = await setup_course(api, teacher)
    qid = c["queue"]["id"]
    test = await api.ok(
        "POST",
        "/tests",
        teacher,
        json={"lab_id": c["short"]["id"], "title": "T", "time_limit_min": 1},
    )
    await api.ok(
        "POST",
        f"/tests/{test['id']}/questions",
        teacher,
        json={"text": "?", "kind": "single", "options": ["a", "b"], "correct": 0},
    )
    await api.ok("POST", f"/queues/{qid}/entries", student, json={"lab_ids": [c["short"]["id"]]})
    called = await api.ok("POST", f"/queues/{qid}/call-next", teacher)
    attempt = await api.ok("POST", f"/entries/{called['id']}/test/start", teacher, json={})

    async with api.factory() as db:
        row = await db.get(Attempt, attempt["id"])
        assert row is not None
        row.started_at = utcnow() - timedelta(minutes=10)
        await db.commit()

    card = await api.ok("GET", f"/entries/{called['id']}", teacher)
    assert card["status"] == "reviewing"
    assert card["attempts"][0]["finished_at"] is not None
    assert card["attempts"][0]["score"] == 0


async def test_my_entries_and_rich_stats(api: Api) -> None:
    """«Мои очереди» для студента и расширенная статистика для преподавателя."""
    teacher = await api.user(UserRole.teacher)
    anna = await api.user(UserRole.student, "Анна")
    boris = await api.user(UserRole.student, "Борис")
    c = await setup_course(api, teacher)
    qid = c["queue"]["id"]

    assert await api.ok("GET", "/entries/me", anna) == []
    await api.ok("POST", f"/queues/{qid}/entries", anna, json={"lab_ids": [c["long"]["id"]]})
    await api.ok("POST", f"/queues/{qid}/entries", boris, json={"lab_ids": [c["short"]["id"]]})
    mine = await api.ok("GET", "/entries/me", anna)
    assert len(mine) == 1
    assert mine[0]["queue"]["id"] == qid
    assert mine[0]["entry"]["position"] == 2  # короткая лаба Бориса впереди
    assert mine[0]["entry"]["wait_minutes"] == 10
    assert (await api.client.get("/entries/me", headers=teacher)).status_code == 403

    called = await api.ok("POST", f"/queues/{qid}/call-next", teacher)
    await api.ok("PATCH", f"/entries/{called['id']}/status", teacher, json={"status": "passed"})

    stats = await api.ok("GET", f"/queues/{qid}/stats", teacher)
    assert [lab["number"] for lab in stats["labs"]] == [1, 2]
    short = stats["labs"][0]
    assert short["samples"] == 1 and short["actual_avg_min"] is not None
    assert stats["labs"][1]["samples"] == 0 and stats["labs"][1]["actual_avg_min"] is None
    rows = {r["student_name"]: r for r in stats["results"]}
    assert rows["Борис"]["status"] == "passed" and rows["Борис"]["labs"] == ["ЛР 1"]
    assert rows["Анна"]["status"] == "waiting"
    assert "email" not in rows["Анна"]

    assert await api.ok("GET", "/entries/me", boris) == []
