"""
Pydantic schemas for FAQ Group / Category API endpoints.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ---- FAQ Group (level 1) ----

class FAQGroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    bot_group_id: Optional[int] = None
    is_active: bool = True


class FAQGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    bot_group_id: Optional[int] = None
    is_active: Optional[bool] = None


class FAQCategoryResponse(BaseModel):
    id: int
    name: str
    faq_group_id: int
    bot_group_id: Optional[int] = None
    bot_group_name: Optional[str] = None
    is_active: bool
    rule_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FAQGroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    bot_group_id: Optional[int] = None
    bot_group_name: Optional[str] = None
    is_active: bool
    categories: List[FAQCategoryResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---- FAQ Category (level 2) ----

class FAQCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    faq_group_id: int
    bot_group_id: Optional[int] = None
    is_active: bool = True


class FAQCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    bot_group_id: Optional[int] = None
    is_active: Optional[bool] = None
