from sqlalchemy import Column, Integer, String, Text, Boolean, TIMESTAMP, ForeignKey, false
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.database import Base


class Notice(Base):
    __tablename__ = "notices"

    id = Column(Integer, primary_key=True, nullable=False)

    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    is_important = Column(Boolean, default=False, server_default=false(), nullable=False, index=True)

    posted_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False, index=True)

    posted_by = relationship("User", back_populates="notices_posted")