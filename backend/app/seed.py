"""Демо-данные для локальной разработки: python -m app.seed

Создаёт администратора, преподавателя, студента, дисциплину с лабами, тест и
открытую очередь на сегодня. Пароли можно задать переменными окружения.
Повторный запуск ничего не дублирует.
"""

import asyncio
import os
from datetime import date, time

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Discipline, Lab, LabTest, Question, Queue, User, UserRole

# Демо-аккаунты с простыми логинами — ТОЛЬКО для локальной разработки.
# (логин, ФИО, роль, переменная окружения с паролем, старый email для переименования)
DEMO_PASSWORD = "1234"
USERS = [
    ("admin", "Администратор", UserRole.admin, "SEED_ADMIN_PASSWORD", "admin@labflow.local"),
    (
        "teacher",
        "Петров Пётр Петрович",
        UserRole.teacher,
        "SEED_TEACHER_PASSWORD",
        "teacher@labflow.local",
    ),
    ("student", "Иванов Иван", UserRole.student, "SEED_STUDENT_PASSWORD", "student@labflow.local"),
]


async def seed() -> None:
    async with SessionLocal() as db:
        users: dict[UserRole, User] = {}
        for login, name, role, env, old_email in USERS:
            # В production простых паролей по умолчанию нет: пароль только из окружения.
            password = os.environ.get(env) or (
                "" if settings.environment == "production" else DEMO_PASSWORD
            )
            if not password:
                print(f"Пропускаю «{login}»: не задана переменная {env}")
                continue
            password_hash = hash_password(password)
            user = await db.scalar(select(User).where(User.email.in_([login, old_email])))
            if user is not None:
                # Аккаунт из прошлых версий сида — переводим на короткий логин и пароль.
                user.email = login
                user.password_hash = password_hash
            else:
                user = User(
                    email=login,
                    password_hash=password_hash,
                    full_name=name,
                    group="М8О-312БВ-24" if role == UserRole.student else None,
                    role=role,
                )
                db.add(user)
            users[role] = user

        if await db.scalar(select(Discipline.id).limit(1)) is None:
            labs = [
                Lab(number=1, title="Классы и объекты", expected_minutes=10),
                Lab(number=2, title="Наследование", expected_minutes=15),
                Lab(number=3, title="Шаблоны проектирования", expected_minutes=25),
            ]
            discipline = Discipline(title="Объектно-ориентированное программирование", labs=labs)
            db.add(discipline)
            db.add(
                LabTest(
                    lab=labs[1],
                    title="Наследование: проверка понимания",
                    time_limit_min=5,
                    questions=[
                        Question(
                            text="Что делает super() в Python?",
                            kind="single",
                            options=["Вызывает метод родителя", "Создаёт объект", "Удаляет класс"],
                            correct=0,
                        ),
                        Question(
                            text="Какие из принципов относятся к ООП?",
                            kind="multi",
                            options=["Инкапсуляция", "Рекурсия", "Полиморфизм", "Наследование"],
                            correct=[0, 2, 3],
                        ),
                        Question(
                            text="Как называется метод-конструктор в Python?",
                            kind="text",
                            options=[],
                            correct=["__init__", "init"],
                        ),
                    ],
                )
            )
        await db.flush()

        # Демо-очередь на сегодня — если есть преподаватель и очередей ещё нет.
        if UserRole.teacher in users and await db.scalar(select(Queue.id).limit(1)) is None:
            discipline_id = await db.scalar(select(Discipline.id).order_by(Discipline.id))
            if discipline_id is not None:
                db.add(
                    Queue(
                        discipline_id=discipline_id,
                        teacher=users[UserRole.teacher],
                        date=date.today(),
                        starts_at=time(9, 0),
                        ends_at=time(18, 0),
                    )
                )
        await db.commit()
        created = ", ".join(u.email for u in users.values()) or "нет"
    print(f"Готово. Пользователи: {created}.")


if __name__ == "__main__":
    asyncio.run(seed())
