"""Pydantic schemas for movie request system."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# === TMDB API Key Schemas ===

class TmdbApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    api_key: str = Field(..., min_length=1, max_length=200)
    access_token: Optional[str] = Field(default=None, max_length=500)


class TmdbApiKeyOut(BaseModel):
    id: int
    name: str
    api_key_masked: str
    access_token_masked: Optional[str] = None
    is_active: bool
    is_rate_limited: bool
    rate_limited_until: Optional[datetime] = None
    request_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# === Movie Request Schemas ===

class MovieRequestUserOut(BaseModel):
    id: int
    tg_user_id: int
    tg_username: Optional[str] = None
    tg_first_name: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MovieRequestOut(BaseModel):
    id: int
    tmdb_id: int
    media_type: str
    title: str
    original_title: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    release_date: Optional[str] = None
    overview: Optional[str] = None
    vote_average: Optional[float] = None
    genres: Optional[str] = None
    status: str
    admin_note: Optional[str] = None
    request_count: int
    in_library: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MovieRequestDetail(MovieRequestOut):
    request_users: list[MovieRequestUserOut] = Field(default_factory=list)
    tmdb_raw: Optional[dict[str, Any]] = None


class MovieRequestUpdate(BaseModel):
    status: Optional[str] = Field(default=None, pattern=r"^(pending|fulfilled|rejected)$")
    admin_note: Optional[str] = None


class MovieRequestStats(BaseModel):
    total: int = 0
    pending: int = 0
    fulfilled: int = 0
    rejected: int = 0


# === Media Library Config Schemas ===

class MediaLibraryConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    db_type: str = Field(..., pattern=r"^(postgresql|mysql)$")
    host: str = Field(..., min_length=1, max_length=200)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    database: str = Field(..., min_length=1, max_length=100)
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)
    table_name: str = Field(..., min_length=1, max_length=100)
    tmdb_id_column: str = Field(..., min_length=1, max_length=100)
    media_type_column: Optional[str] = Field(default=None, max_length=100)


class MediaLibraryConfigOut(BaseModel):
    id: int
    name: str
    db_type: str
    host: str
    port: Optional[int] = None
    database: str
    username: str
    password_masked: str
    table_name: str
    tmdb_id_column: str
    media_type_column: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
