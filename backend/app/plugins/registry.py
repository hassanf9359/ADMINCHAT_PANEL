from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class InstalledPlugin(TimestampMixin, Base):
    """Registry of installed plugins and their current state."""

    __tablename__ = "installed_plugins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    previous_version: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="installed"
    )
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    license_key: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True
    )
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    installed_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    activated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    __table_args__ = (
        Index("ix_installed_plugins_status", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<InstalledPlugin(plugin_id={self.plugin_id!r}, "
            f"version={self.version!r}, status={self.status!r})>"
        )


class PluginSecret(Base):
    """Encrypted key-value secrets scoped to individual plugins."""

    __tablename__ = "plugin_secrets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("plugin_id", "key", name="uq_plugin_secret_plugin_key"),
    )

    def __repr__(self) -> str:
        return (
            f"<PluginSecret(plugin_id={self.plugin_id!r}, key={self.key!r})>"
        )
