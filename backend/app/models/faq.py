from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class FaqGroup(Base, TimestampMixin):
    """Top-level FAQ group (e.g. '售前', '售后')."""
    __tablename__ = "faq_groups"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bot_group_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("bot_groups.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")

    # Relationships
    bot_group = relationship("BotGroup", lazy="selectin")
    categories: Mapped[list["FaqCategory"]] = relationship(
        "FaqCategory", back_populates="faq_group", cascade="all, delete-orphan",
        lazy="selectin",
    )


class FaqCategory(Base, TimestampMixin):
    """Second-level FAQ category (belongs to a FaqGroup)."""
    __tablename__ = "faq_categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    faq_group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("faq_groups.id", ondelete="CASCADE"), nullable=False
    )
    bot_group_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("bot_groups.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")

    # Relationships
    faq_group: Mapped["FaqGroup"] = relationship("FaqGroup", back_populates="categories", lazy="selectin")
    bot_group = relationship("BotGroup", lazy="selectin")


class FaqQuestion(Base, TimestampMixin):
    __tablename__ = "faq_questions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    match_mode: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'exact','prefix','contains','regex'
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")

    # Relationships
    rule_questions = relationship(
        "FaqRuleQuestion", back_populates="question", cascade="all, delete-orphan",
        lazy="selectin",
    )


class FaqAnswer(Base, TimestampMixin):
    __tablename__ = "faq_answers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(
        String(20), server_default="text"
    )  # 'text','photo','mixed'
    media_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")

    # Relationships
    rule_answers = relationship(
        "FaqRuleAnswer", back_populates="answer", cascade="all, delete-orphan",
        lazy="selectin",
    )


class FaqRule(Base, TimestampMixin):
    __tablename__ = "faq_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    response_mode: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # 'single', 'random', 'all'
    reply_mode: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="direct"
    )
    ai_config: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    priority: Mapped[int] = mapped_column(Integer, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", index=True)
    daily_ai_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("faq_categories.id", ondelete="SET NULL"), nullable=True
    )
    rag_config_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("rag_configs.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships - all use lazy="selectin" for async compatibility
    category = relationship("FaqCategory", lazy="selectin")
    rag_config = relationship("RagConfig", lazy="selectin")
    rule_questions = relationship(
        "FaqRuleQuestion", back_populates="rule", cascade="all, delete-orphan",
        lazy="selectin",
    )
    rule_answers = relationship(
        "FaqRuleAnswer", back_populates="rule", cascade="all, delete-orphan",
        lazy="selectin",
    )
    hit_stats = relationship(
        "FaqHitStat", back_populates="faq_rule", cascade="all, delete-orphan",
        lazy="selectin",
    )


class FaqRuleQuestion(Base):
    __tablename__ = "faq_rule_questions"

    rule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("faq_rules.id", ondelete="CASCADE"), primary_key=True
    )
    question_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("faq_questions.id", ondelete="CASCADE"), primary_key=True
    )

    # Relationships
    rule = relationship("FaqRule", back_populates="rule_questions", lazy="selectin")
    question = relationship("FaqQuestion", back_populates="rule_questions", lazy="selectin")


class FaqRuleAnswer(Base):
    __tablename__ = "faq_rule_answers"

    rule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("faq_rules.id", ondelete="CASCADE"), primary_key=True
    )
    answer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("faq_answers.id", ondelete="CASCADE"), primary_key=True
    )

    # Relationships
    rule = relationship("FaqRule", back_populates="rule_answers", lazy="selectin")
    answer = relationship("FaqAnswer", back_populates="rule_answers", lazy="selectin")
