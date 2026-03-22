"""
Pydantic schemas for Bot Group API endpoints.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ---- Bot Group ----

class BotGroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: bool = True


class BotGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class BotGroupMemberResponse(BaseModel):
    bot_id: int
    bot_username: Optional[str] = None
    display_name: Optional[str] = None

    model_config = {"from_attributes": True}


class BotGroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_active: bool
    members: List[BotGroupMemberResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BotGroupMembersUpdate(BaseModel):
    """Set bot_ids for a group (replaces existing members)."""
    bot_ids: List[int] = Field(default_factory=list)
