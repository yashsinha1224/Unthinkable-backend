from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class NoticeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)
    is_important: bool = False


class NoticeResponse(BaseModel):
    id: int
    title: str
    body: str
    is_important: bool
    posted_by_id: int
    posted_by_name: Optional[str] = None  
    created_at: datetime

    class Config:
        from_attributes = True


class NoticeListResponse(BaseModel):
    total: int
    items: List[NoticeResponse]