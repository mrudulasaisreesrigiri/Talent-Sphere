import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import engine, Base, SessionLocal
from app.models.models import User, UserRole
from app.core.security import get_password_hash

def init_database():
    print("Initializing normalized MySQL tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

    db = SessionLocal()
    existing_admin = db.query(User).filter(User.email == "admin@talentsphere.com").first()
    if not existing_admin:
        admin = User(
            email="admin@talentsphere.com",
            full_name="System Super Administrator",
            password_hash=get_password_hash("Admin@123456"),
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(admin)
        db.commit()
        print("Default Super Admin created: admin@talentsphere.com / Admin@123456")
    else:
        print("Admin account already exists.")
    db.close()

if __name__ == "__main__":
    init_database()
