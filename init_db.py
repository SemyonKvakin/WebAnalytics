from database import engine, Base, SessionLocal, User
from auth import hash_password
from datetime import datetime, timezone


def seed_admin():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.login == "admin").first()
        if not existing:
            admin = User(
                login="admin",
                password_hash=hash_password("Admin123!"),
                first_name="Администратор",
                role="admin",
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            db.add(admin)
            db.commit()
            print("Администратор создан: login=admin, password=Admin123!")
        else:
            print("Администратор уже существует.")
    finally:
        db.close()


if __name__ == "__main__":
    print("Таблицы созданы.")
    seed_admin()
    print("База данных готова.")