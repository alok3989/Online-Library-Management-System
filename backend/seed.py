import sys
import os
from datetime import datetime, timedelta

# Add the parent directory to the path so we can import the backend package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, engine, Base
import models
from security import get_password_hash

print("Dropping existing tables (if any)...")
Base.metadata.drop_all(bind=engine)
print("Creating tables based on models.py...")
Base.metadata.create_all(bind=engine)

db = SessionLocal()

# --- Seed Users ---
print("Seeding Users...")
admin_user = models.User(
    user_id="u-admin-001",
    name="admin",
    password_hash=get_password_hash("password123"),
    role=models.RoleEnum.admin,
    trust_score=100
)
student_user = models.User(
    user_id="u-student-001",
    name="student",
    password_hash=get_password_hash("student123"),
    role=models.RoleEnum.student,
    trust_score=85
)
db.add_all([admin_user, student_user])
db.flush()

# --- Seed Books ---
print("Seeding Books...")
books = [
    models.Book(isbn="978-0-262-03384-8", title="Introduction to Algorithms", category="Computer Science", format=models.FormatEnum.physical, status=models.StatusEnum.issued),
    models.Book(isbn="978-0-13-110362-7", title="The C Programming Language", category="Computer Science", format=models.FormatEnum.digital, status=models.StatusEnum.available),
    models.Book(isbn="978-0-201-63361-0", title="Design Patterns", category="Computer Science", format=models.FormatEnum.physical, status=models.StatusEnum.available),
    models.Book(isbn="978-0-13-468599-1", title="Clean Code", category="Software Engineering", format=models.FormatEnum.physical, status=models.StatusEnum.issued),
    models.Book(isbn="978-0-13-235088-4", title="Computer Networks", category="Computer Science", format=models.FormatEnum.physical, status=models.StatusEnum.available),
    models.Book(isbn="978-0-07-352330-7", title="Calculus Early Transcendentals", category="Mathematics", format=models.FormatEnum.physical, status=models.StatusEnum.available),
    models.Book(isbn="978-0-321-12521-7", title="Domain-Driven Design", category="Software Engineering", format=models.FormatEnum.digital, status=models.StatusEnum.available),
    models.Book(isbn="978-1-49-195017-1", title="Hands-On Machine Learning", category="AI & ML", format=models.FormatEnum.digital, status=models.StatusEnum.available),
    models.Book(isbn="978-0-59-651798-4", title="JavaScript: The Good Parts", category="Web Development", format=models.FormatEnum.physical, status=models.StatusEnum.reserved),
    models.Book(isbn="978-1-44-937365-8", title="Learning Python", category="Computer Science", format=models.FormatEnum.physical, status=models.StatusEnum.available),
]
db.add_all(books)
db.flush()

# --- Seed Transactions for the student user ---
print("Seeding Transactions...")
today = datetime.utcnow()

txn1 = models.Transaction(
    transaction_id="txn-001",
    user_id="u-student-001",
    isbn="978-0-262-03384-8",   # Intro to Algorithms
    issue_date=today - timedelta(days=10),
    due_date=today + timedelta(days=4),
    status=models.TransactionStatusEnum.active
)
txn2 = models.Transaction(
    transaction_id="txn-002",
    user_id="u-student-001",
    isbn="978-0-13-468599-1",   # Clean Code
    issue_date=today - timedelta(days=20),
    due_date=today - timedelta(days=6),
    status=models.TransactionStatusEnum.overdue
)
txn3 = models.Transaction(
    transaction_id="txn-003",
    user_id="u-student-001",
    isbn="978-0-13-110362-7",   # The C Programming Language (returned)
    issue_date=today - timedelta(days=30),
    due_date=today - timedelta(days=16),
    status=models.TransactionStatusEnum.returned
)
db.add_all([txn1, txn2, txn3])

# --- Seed Smart Lockers (empty, ready for Phase 4) ---
print("Seeding Smart Lockers...")
lockers = [
    models.SmartLocker(locker_id="A1", is_empty=True),
    models.SmartLocker(locker_id="A2", is_empty=True),
    models.SmartLocker(locker_id="B1", is_empty=True),
]
db.add_all(lockers)

db.commit()
print("\n✅ Database seeded successfully!")
print("   Users:        admin / password123   |   student / student123")
print("   Books:        10 titles across 5 categories")
print("   Transactions: 2 active/overdue + 1 returned (for student)")
print("   Lockers:      3 empty lockers (A1, A2, B1)")
db.close()
