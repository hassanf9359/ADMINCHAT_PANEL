from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class PluginInfo(BaseModel):
    """Public representation of an installed plugin."""

    plugin_id: str
    name: str
    version: str
    previous_version: Optional[str] = None
    status: str  # installed|active|disabled|error|updating
    manifest: dict[str, Any]
    config: dict[str, Any] = {}
    error_count: int = 0
    last_error: Optional[str] = None
    license_key_set: bool = False  # True if license_key is not null (don't expose actual key)
    installed_at: datetime
    activated_at: Optional[datetime] = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class PluginInstallRequest(BaseModel):
    """Request body for installing a plugin."""

    plugin_id: str = Field(..., pattern=r"^[a-z][a-z0-9-]{2,49}$")
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    market_url: Optional[str] = None  # If provided, download from this URL
    license_key: Optional[str] = None


class PluginActionRequest(BaseModel):
    """Request body for plugin lifecycle actions."""

    action: str = Field(..., pattern=r"^(activate|deactivate|uninstall|rollback)$")
    drop_tables: bool = False  # Only for uninstall


class PluginUpdateRequest(BaseModel):
    """Request body for updating a plugin to a new version."""

    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    market_url: Optional[str] = None


class PluginConfigUpdate(BaseModel):
    """Request body for updating plugin configuration."""

    config: dict[str, Any]


class MarketProxyRequest(BaseModel):
    """Request body for marketplace API proxy calls."""

    market_api_key: Optional[str] = None


class InstalledPluginList(BaseModel):
    """Response wrapper for listing installed plugins."""

    plugins: list[PluginInfo] = []
    total: int = 0
