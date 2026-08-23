from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from models.complaint_model import ComplaintCategory, ComplaintPriority, ComplaintStatus



class ComplaintStatusHistoryResponse(BaseModel):
    id: int
    from_status: Optional[ComplaintStatus]
    to_status: ComplaintStatus
    note: Optional[str]
    actor_id: int
    actor_name: Optional[str] = None  
    created_at: datetime

    class Config:
        from_attributes = True




class ComplaintCreate(BaseModel):
    category: ComplaintCategory
    description: str = Field(min_length=10, max_length=2000)
    photo_url: Optional[str] = None  

class ComplaintStatusUpdate(BaseModel):
    to_status: ComplaintStatus
    note: Optional[str] = Field(default=None, max_length=1000)


class ComplaintPriorityUpdate(BaseModel):
    priority: ComplaintPriority


class ComplaintFilter(BaseModel):
    category: Optional[ComplaintCategory] = None
    status: Optional[ComplaintStatus] = None
    priority: Optional[ComplaintPriority] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    overdue_only: bool = False




class ComplaintResponse(BaseModel):
    id: int
    resident_id: int
    category: ComplaintCategory
    description: str
    photo_url: Optional[str]
    priority: ComplaintPriority
    status: ComplaintStatus

    ai_suggested_category: Optional[ComplaintCategory]
    ai_suggested_priority: Optional[ComplaintPriority]
    ai_duplicate_of: Optional[int]
    ai_draft_note: Optional[str]

    created_at: datetime
    resolved_at: Optional[datetime]

    is_overdue: bool = False
    days_open: int = 0

    class Config:
        from_attributes = True


class ComplaintDetailResponse(ComplaintResponse):
    history: List[ComplaintStatusHistoryResponse] = []


class ComplaintListResponse(BaseModel):
    total: int
    items: List[ComplaintResponse]