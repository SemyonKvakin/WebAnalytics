from database import engine, Base, SessionLocal, User
from auth import hash_password
from datetime import datetime

Base.metadata.create_all(bind=engine)
print("Таблицы созданы.")

db = SessionLocal()
try:
    existing = db.query(User).filter(User.login == "admin").first()
    if not existing:
        admin = User(
            login="admin",
            password_hash=hash_password("Admin123!"),
            first_name="Администратор",
            role="admin",
            created_at=datetime.utcnow(),
        )
        db.add(admin)
        db.commit()
        print("Администратор создан: login=admin, password=Admin123!")
    else:
        print("Администратор уже существует.")
finally:
    db.close()

print("База данных готова.")
