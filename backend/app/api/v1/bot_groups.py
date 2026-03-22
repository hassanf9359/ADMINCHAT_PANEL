"""
Bot Group management API endpoints.

GET    /bot-groups               - list all bot groups
POST   /bot-groups               - create bot group
PATCH  /bot-groups/:id           - update bot group
DELETE /bot-groups/:id           - delete bot group
PUT    /bot-groups/:id/members   - set member bots
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, require_admin
from app.models.admin import Admin
from app.models.bot import Bot
from app.models.bot_group import BotGroup, BotGroupMember
from app.schemas.bot_group import (
    BotGroupCreate,
    BotGroupMemberResponse,
    BotGroupMembersUpdate,
    BotGroupResponse,
    BotGroupUpdate,
)
from app.schemas.common import APIResponse
from app.services.audit import log_action

logger = logging.getLogger(__name__)

router = APIRouter()


def _build_response(group: BotGroup) -> dict:
    members = []
    for m in (group.members or []):
        bot = m.bot
        members.append(BotGroupMemberResponse(
            bot_id=m.bot_id,
            bot_username=bot.bot_username if bot else None,
            display_name=bot.display_name if bot else None,
        ))
    resp = BotGroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        is_active=group.is_active,
        members=members,
        created_at=group.created_at,
        updated_at=group.updated_at,
    )
    return resp.model_dump(mode="json")


@router.get("", response_model=APIResponse)
async def list_bot_groups(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Admin, Depends(require_admin)],
):
    """List all bot groups with their members."""
    result = await db.execute(
        select(BotGroup)
        .options(selectinload(BotGroup.members).selectinload(BotGroupMember.bot))
        .order_by(BotGroup.id.desc())
    )
    groups = result.scalars().unique().all()
    return APIResponse(data=[_build_response(g) for g in groups])


@router.post("", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def create_bot_group(
    body: BotGroupCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Admin, Depends(require_admin)],
):
    group = BotGroup(
        name=body.name,
        description=body.description,
        is_active=body.is_active,
    )
    db.add(group)
    await db.flush()
    await db.refresh(group)

    await log_action(
        db, _current_user.id, "create_bot_group", "bot_group", group.id,
        {"name": group.name},
        request.client.host if request.client else None,
    )

    # Reload with relationships
    result = await db.execute(
        select(BotGroup).where(BotGroup.id == group.id)
        .options(selectinload(BotGroup.members).selectinload(BotGroupMember.bot))
    )
    group = result.scalar_one()
    return APIResponse(code=201, message="Bot group created", data=_build_response(group))


@router.patch("/{group_id}", response_model=APIResponse)
async def update_bot_group(
    group_id: int,
    body: BotGroupUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Admin, Depends(require_admin)],
):
    result = await db.execute(select(BotGroup).where(BotGroup.id == group_id))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="Bot group not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(group, field, value)

    await db.flush()

    # Reload
    result = await db.execute(
        select(BotGroup).where(BotGroup.id == group_id)
        .options(selectinload(BotGroup.members).selectinload(BotGroupMember.bot))
    )
    group = result.scalar_one()

    await log_action(
        db, _current_user.id, "update_bot_group", "bot_group", group_id,
        {"name": group.name},
        request.client.host if request.client else None,
    )

    return APIResponse(data=_build_response(group))


@router.delete("/{group_id}", response_model=APIResponse)
async def delete_bot_group(
    group_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Admin, Depends(require_admin)],
):
    result = await db.execute(select(BotGroup).where(BotGroup.id == group_id))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="Bot group not found")

    await log_action(
        db, _current_user.id, "delete_bot_group", "bot_group", group_id,
        {"name": group.name},
        request.client.host if request.client else None,
    )
    await db.delete(group)
    return APIResponse(message="Bot group deleted")


@router.put("/{group_id}/members", response_model=APIResponse)
async def set_bot_group_members(
    group_id: int,
    body: BotGroupMembersUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Admin, Depends(require_admin)],
):
    """Replace all members of a bot group with the given bot_ids."""
    result = await db.execute(select(BotGroup).where(BotGroup.id == group_id))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="Bot group not found")

    # Validate all bot_ids exist
    for bot_id in body.bot_ids:
        bot_result = await db.execute(select(Bot).where(Bot.id == bot_id))
        if bot_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=400, detail=f"Bot id={bot_id} not found")

    # Check for bots already in other groups
    if body.bot_ids:
        existing = await db.execute(
            select(BotGroupMember).where(
                BotGroupMember.bot_id.in_(body.bot_ids),
                BotGroupMember.bot_group_id != group_id,
            )
        )
        conflicts = existing.scalars().all()
        if conflicts:
            conflict_ids = [c.bot_id for c in conflicts]
            raise HTTPException(
                status_code=400,
                detail=f"Bot(s) {conflict_ids} already belong to another group",
            )

    # Remove old members
    await db.execute(
        delete(BotGroupMember).where(BotGroupMember.bot_group_id == group_id)
    )

    # Add new members
    for bot_id in body.bot_ids:
        db.add(BotGroupMember(bot_group_id=group_id, bot_id=bot_id))

    await db.flush()

    # Reload
    result = await db.execute(
        select(BotGroup).where(BotGroup.id == group_id)
        .options(selectinload(BotGroup.members).selectinload(BotGroupMember.bot))
    )
    group = result.scalar_one()
    return APIResponse(data=_build_response(group))
