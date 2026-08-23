from database.database import Base
from sqlalchemy import Column, Integer, String, TIMESTAMP, Boolean, Enum, true
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum


class UserRole(enum.Enum):
    admin = "admin"
    resident = "resident"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=True)   # nullable — Google-only accounts have no password
    google_id = Column(String, nullable=True)

    flat_number = Column(String, nullable=True)     # residents only
    phone = Column(String, nullable=True)

    is_active = Column(Boolean, default=True, server_default=true(), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.resident, server_default="resident")
    requested_role = Column(Enum(UserRole), nullable=True)  # pending role-change request, awaiting admin approval
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    complaints = relationship("Complaint", back_populates="resident", cascade="all, delete-orphan")
    notices_posted = relationship("Notice", back_populates="posted_by")