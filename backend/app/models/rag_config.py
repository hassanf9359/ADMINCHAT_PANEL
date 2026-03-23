from typing import Optional

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class RagConfig(Base, TimestampMixin):
    """RAG provider configuration (e.g. Dify knowledge base)."""
    __tablename__ = "rag_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # 'dify'
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_key: Mapped[str] = mapped_column(String(500), nullable=False)
    dataset_id: Mapped[str] = mapped_column(String(200), nullable=False)
    top_k: Mapped[int] = mapped_column(Integer, server_default="3")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
