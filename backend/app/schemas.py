from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List

class TicketCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=5)
    category: str = Field(..., min_length=2)
    priority: str = Field("MEDIUM")
    requester_name: str = Field(..., min_length=2)
    requester_email: str = Field(..., min_length=5)

class TicketStatusUpdate(BaseModel):
    status: str
    root_cause: Optional[str] = None
    actor: str = "IT Operations"
    comment: Optional[str] = None

class TicketAssign(BaseModel):
    assigned_agent: str
    escalation_tier: Optional[str] = None
    actor: str = "IT Lead"

class CommentCreate(BaseModel):
    author: str
    author_role: str = "Support Technician"
    message: str = Field(..., min_length=1)
    is_internal: bool = False
