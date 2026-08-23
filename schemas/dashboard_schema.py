from typing import Dict
from pydantic import BaseModel

from models.complaint_model import ComplaintStatus, ComplaintCategory


class DashboardResponse(BaseModel):
    total_complaints: int
    by_status: Dict[ComplaintStatus, int]
    by_category: Dict[ComplaintCategory, int]
    overdue_count: int