import uuid
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum
from database import Base

class RoleEnum(enum.Enum):
    admin = 'admin'
    student = 'student'

class FormatEnum(enum.Enum):
    physical = 'physical'
    digital = 'digital'

class StatusEnum(enum.Enum):
    available = 'available'
    issued = 'issued'
    reserved = 'reserved'
    in_locker = 'in_locker'

class TransactionStatusEnum(str, enum.Enum):
    active = "active"
    returned = "returned"
    overdue = "overdue"
    pending_issue = "pending_issue"
    pending_return = "pending_return"

class User(Base):
    __tablename__ = 'users'
    user_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    role = Column(SQLEnum(RoleEnum), nullable=False)
    name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False) # Adding for Phase 1 Authentication
    trust_score = Column(Integer, default=100)

class Book(Base):
    __tablename__ = 'books'
    isbn = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    category = Column(String)
    format = Column(SQLEnum(FormatEnum), nullable=False)
    status = Column(SQLEnum(StatusEnum), nullable=False, default=StatusEnum.available)

class Transaction(Base):
    __tablename__ = 'transactions'
    transaction_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey('users.user_id'))
    isbn = Column(String, ForeignKey('books.isbn'))
    issue_date = Column(DateTime)
    due_date = Column(DateTime)
    status = Column(SQLEnum(TransactionStatusEnum), nullable=False)

class SmartLocker(Base):
    __tablename__ = 'smart_lockers'
    locker_id = Column(String, primary_key=True)
    transaction_id = Column(String, ForeignKey('transactions.transaction_id'))
    otp_code = Column(String)
    is_empty = Column(Boolean, default=True)
