import os
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("init_db")

def init_db():
    # Ensure data directory exists if using SQLite
    from app.core.config import get_settings
    settings = get_settings()
    if settings.database_url.startswith("sqlite"):
        # Extract path if sqlite:///...
        sqlite_path = settings.database_url.replace("sqlite:///", "")
        db_file = Path(sqlite_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"SQLite database directory created/verified at: {db_file.parent}")

    # Run Alembic migrations
    logger.info("Running database migrations...")
    try:
        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations applied successfully.")
    except Exception as e:
        import traceback
        logger.error(f"Migration error: {e}")
        traceback.print_exc()

    # Seed default admin user and company if empty
    from app.database.database import SessionLocal
    from app.models.user import User
    from app.models.company import Company
    from app.core.security import hash_password

    db = SessionLocal()
    try:
        user_count = db.query(User).count()
        if user_count == 0:
            logger.info("No existing users found. Seeding initial accounts...")

            # 1. Default Company
            company = db.query(Company).first()
            if not company:
                company = Company(name="Default Company")
                db.add(company)
                db.commit()
                db.refresh(company)

            # 2. SaaS Admin User
            admin_user = os.getenv("INITIAL_ADMIN_USER", "admin")
            admin_pass = os.getenv("INITIAL_ADMIN_PASSWORD", "Admin123!")
            admin_email = os.getenv("INITIAL_ADMIN_EMAIL", "admin@example.com")

            admin = User(
                username=admin_user,
                email=admin_email,
                password_hash=hash_password(admin_pass),
                is_active=True,
                role="admin",
                company_id=None,
            )
            db.add(admin)

            # 3. Tool User (Checker)
            checker_user = User(
                username="checker_user",
                email="checker@example.com",
                password_hash=hash_password("securepass123"),
                is_active=True,
                role="checker",
                company_id=company.id,
            )
            db.add(checker_user)

            db.commit()
            logger.info("=======================================================")
            logger.info("INITIAL DATABASE SETUP COMPLETE!")
            logger.info(f" SaaS Admin  : username='{admin_user}' | password='{admin_pass}'")
            logger.info(f" Tool User   : username='checker_user' | password='securepass123'")
            logger.info("=======================================================")
        else:
            logger.info(f"Database already initialized with {user_count} user(s).")
    except Exception as e:
        logger.error(f"Error seeding initial user data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
