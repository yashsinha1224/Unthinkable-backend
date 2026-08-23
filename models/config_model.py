from sqlalchemy import Column, Integer

from database.database import Base


class AppConfig(Base):
    __tablename__ = "app_config"

    id = Column(Integer, primary_key=True)
    overdue_threshold_days = Column(Integer, nullable=False, server_default="7")