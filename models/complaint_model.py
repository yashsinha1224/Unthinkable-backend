from datetime import datetime
import enum

from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.database import Base


class ComplaintCategory(enum.Enum):
    plumbing = "plumbing"
    electrical = "electrical"
    elevator = "elevator"
    security = "security"
    housekeeping = "housekeeping"
    parking = "parking"
    common_area = "common_area"
    other = "other"


class ComplaintPriority(enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ComplaintStatus(enum.Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, nullable=False)

    resident_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    category = Column(Enum(ComplaintCategory), nullable=False, index=True)
    description = Column(Text, nullable=False)
    photo_url = Column(String, nullable=True)

    priority = Column(Enum(ComplaintPriority), nullable=False, default=ComplaintPriority.medium, server_default="medium", index=True)
    status = Column(Enum(ComplaintStatus), nullable=False, default=ComplaintStatus.open, server_default="open", index=True)

    # AI triage fields — advisory only, populated by the LangGraph pipeline (v3)
    ai_suggested_category = Column(Enum(ComplaintCategory), nullable=True)
    ai_suggested_priority = Column(Enum(ComplaintPriority), nullable=True)
    ai_duplicate_of = Column(Integer, ForeignKey("complaints.id"), nullable=True)
    ai_draft_note = Column(Text, nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False, index=True)
    resolved_at = Column(TIMESTAMP(timezone=True), nullable=True)

    resident = relationship("User", back_populates="complaints", foreign_keys=[resident_id])
    history = relationship(
        "ComplaintStatusHistory",
        back_populates="complaint",
        order_by="ComplaintStatusHistory.created_at",
        cascade="all, delete-orphan",
        foreign_keys="ComplaintStatusHistory.complaint_id",
    )


class ComplaintStatusHistory(Base):
    __tablename__ = "complaint_status_history"

    id = Column(Integer, primary_key=True, nullable=False)

    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    from_status = Column(Enum(ComplaintStatus), nullable=True)   # null on initial creation event
    to_status = Column(Enum(ComplaintStatus), nullable=False)

    note = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False, index=True)

    complaint = relationship("Complaint", back_populates="history", foreign_keys=[complaint_id])
    actor = relationship("User")