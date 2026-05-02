import os
import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, SQLALCHEMY_DATABASE_URL
import models

# --- CONFIGURATION ---
# 1. Local SQLite Path
LOCAL_DB_PATH = "sqlite:///./libratech.db"

# 2. Remote PostgreSQL URL (You will get this from Render Dashboard)
# Example: postgresql://user:password@hostname:port/dbname
REMOTE_DB_URL = os.environ.get("REMOTE_DATABASE_URL")

def migrate_data():
    if not REMOTE_DB_URL:
        print("❌ Error: REMOTE_DATABASE_URL environment variable not set.")
        print("Please run: export REMOTE_DATABASE_URL='your_render_db_url'")
        return

    print(f"🔄 Starting migration from {LOCAL_DB_PATH} to Cloud...")

    # Engines
    local_engine = create_engine(LOCAL_DB_PATH)
    remote_engine = create_engine(REMOTE_DB_URL)

    # Sessions
    LocalSession = sessionmaker(bind=local_engine)
    RemoteSession = sessionmaker(bind=remote_engine)

    local_db = LocalSession()
    remote_db = RemoteSession()

    try:
        # 1. Create tables in remote if they don't exist
        print("🔨 Creating tables in cloud...")
        models.Base.metadata.create_all(bind=remote_engine)

        # 2. Migrate Users
        print("👥 Migrating Users...")
        users = local_db.query(models.User).all()
        for user in users:
            # Check if user already exists in remote
            exists = remote_db.query(models.User).filter(models.User.user_id == user.user_id).first()
            if not exists:
                # Merge into remote session (handles identity)
                remote_db.merge(user)
        remote_db.commit()

        # 3. Migrate Books
        print("📚 Migrating Books...")
        books = local_db.query(models.Book).all()
        for book in books:
            exists = remote_db.query(models.Book).filter(models.Book.isbn == book.isbn).first()
            if not exists:
                remote_db.merge(book)
        remote_db.commit()

        # 4. Migrate Transactions
        print("📑 Migrating Transactions...")
        txns = local_db.query(models.Transaction).all()
        for txn in txns:
            exists = remote_db.query(models.Transaction).filter(models.Transaction.transaction_id == txn.transaction_id).first()
            if not exists:
                remote_db.merge(txn)
        remote_db.commit()

        # 5. Migrate Lockers
        print("🔒 Migrating Smart Lockers...")
        lockers = local_db.query(models.SmartLocker).all()
        for locker in lockers:
            exists = remote_db.query(models.SmartLocker).filter(models.SmartLocker.locker_id == locker.locker_id).first()
            if not exists:
                remote_db.merge(locker)
        remote_db.commit()

        print("✅ Migration Successful! Your local data is now in the cloud.")

    except Exception as e:
        print(f"❌ Migration Failed: {e}")
        remote_db.rollback()
    finally:
        local_db.close()
        remote_db.close()

if __name__ == "__main__":
    migrate_data()
