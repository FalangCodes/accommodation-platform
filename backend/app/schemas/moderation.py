from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ModerationQueueItem(BaseModel):
    id: int
    resource_type: str
    resource_id: int
    reason_code: Optional[str] = None
    auto_flagged: bool
    assigned_moderator_id: Optional[int] = None
    province: str
    status: str
    created_at: datetime
    actioned_at: Optional[datetime] = None
    sla_deadline: datetime

    model_config = {"from_attributes": True}


class ModerationLogEntry(BaseModel):
    id: int
    moderator_id: int
    action: str
    resource_type: str
    resource_id: int
    reason: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AppealOut(BaseModel):
    id: int
    appellant_id: int
    appellant_role: str
    resource_type: str
    resource_id: int
    original_action_id: int
    reason: str
    status: str
    assigned_admin_id: Optional[int] = None
    resolved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RejectBody(BaseModel):
    reason: str

class RemoveReviewBody(BaseModel):
    reason: str

class AppealResolveBody(BaseModel):
    decision: str  # 'upheld' or 'dismissed'
    reason: Optional[str] = None