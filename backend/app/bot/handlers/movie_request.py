"""
Bot handler for TMDB movie/TV request URLs.

Trigger rules:
  Private chat:
    /req <TMDB_URL>   → recognised
    req <TMDB_URL>    → recognised
    bare TMDB URL     → ignored
  Group chat:
    @bot req <TMDB_URL>  → recognised (mention + req)
    /req <TMDB_URL>      → ignored (avoids duplicate triggers from bot pool)
    bare TMDB URL        → ignored
"""
from __future__ import annotations

import logging
import re

from aiogram import Router
from aiogram.filters import Filter
from aiogram.types import Message as TgMessage
from sqlalchemy import select

from app.database import async_session_factory
from app.models.movie_request import MovieRequest, MovieRequestUser
from app.models.user import TgUser
from app.services.tmdb import get_tmdb_client, parse_tmdb_url, TMDB_IMAGE_BASE
from app.services.media_library import check_in_library

logger = logging.getLogger(__name__)

router = Router(name="movie_request")

# ──────────────────────────────────────────────
#  Custom filter
# ──────────────────────────────────────────────

class MovieRequestTrigger(Filter):
    """
    Returns True only when the message is a valid movie request.

    Private:  /req URL  or  req URL
    Group:    @bot_username req URL
    """

    async def __call__(
        self,
        message: TgMessage,
        bot_username: str = "",
    ) -> bool:
        text = message.text or ""
        if not text:
            return False

        # Must contain a TMDB URL
        if not re.search(r"themoviedb\.org/(movie|tv)/(\d+)", text):
            return False

        chat_type = message.chat.type

        if chat_type == "private":
            # /req URL  or  req URL  (case-insensitive)
            return bool(re.match(r"^/?req\s", text, re.IGNORECASE))

        if chat_type in ("group", "supergroup"):
            # @bot_username req URL  (case-insensitive)
            if not bot_username:
                return False
            pattern = rf"@{re.escape(bot_username)}\s+req\b"
            return bool(re.search(pattern, text, re.IGNORECASE))

        return False


# ──────────────────────────────────────────────
#  Handler
# ──────────────────────────────────────────────

@router.message(MovieRequestTrigger())
async def handle_movie_request(message: TgMessage, bot_db_id: int) -> None:
    """Handle validated movie request messages."""
    tg_user = message.from_user
    if tg_user is None or tg_user.is_bot:
        return

    text = message.text or ""
    parsed = parse_tmdb_url(text)
    if not parsed:
        return

    media_type, tmdb_id = parsed

    async with async_session_factory() as session:
        try:
            # ---- Upsert TgUser ----
            result = await session.execute(
                select(TgUser).where(TgUser.tg_uid == tg_user.id)
            )
            db_user = result.scalar_one_or_none()
            if db_user is None:
                db_user = TgUser(
                    tg_uid=tg_user.id,
                    username=tg_user.username,
                    first_name=tg_user.first_name,
                    last_name=tg_user.last_name,
                    language_code=tg_user.language_code,
                    is_premium=tg_user.is_premium or False,
                    is_bot=tg_user.is_bot,
                )
                session.add(db_user)
                await session.flush()

            # ---- Dedup check (tmdb_id + media_type) ----
            result = await session.execute(
                select(MovieRequest).where(
                    MovieRequest.tmdb_id == tmdb_id,
                    MovieRequest.media_type == media_type,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Check if this user already requested
                user_result = await session.execute(
                    select(MovieRequestUser).where(
                        MovieRequestUser.movie_request_id == existing.id,
                        MovieRequestUser.tg_user_id == db_user.id,
                    )
                )
                user_exists = user_result.scalar_one_or_none()

                if not user_exists:
                    existing.request_count += 1
                    session.add(MovieRequestUser(
                        movie_request_id=existing.id,
                        tg_user_id=db_user.id,
                    ))

                await session.commit()
                await _send_reply_card(message, existing, is_duplicate=True)
                return

            # ---- First request — fetch from TMDB ----
            client = get_tmdb_client()
            tmdb_data = await client.get_media(session, media_type, tmdb_id)

            if not tmdb_data:
                await message.reply(
                    "\u26a0\ufe0f TMDB API error, please try again later.",
                    parse_mode="HTML",
                )
                await session.commit()
                return

            # Extract fields
            title = tmdb_data.get("title") or tmdb_data.get("name") or "Unknown"
            original_title = tmdb_data.get("original_title") or tmdb_data.get("original_name")
            release_date = tmdb_data.get("release_date") or tmdb_data.get("first_air_date")
            genres_list = tmdb_data.get("genres", [])
            genres_str = ", ".join(g["name"] for g in genres_list) if genres_list else None

            # Check remote media library (returns False if not configured)
            in_library = await check_in_library(session, tmdb_id, media_type)

            movie_req = MovieRequest(
                tmdb_id=tmdb_id,
                media_type=media_type,
                title=title,
                original_title=original_title,
                poster_path=tmdb_data.get("poster_path"),
                backdrop_path=tmdb_data.get("backdrop_path"),
                release_date=release_date,
                overview=tmdb_data.get("overview"),
                vote_average=tmdb_data.get("vote_average"),
                genres=genres_str,
                tmdb_raw=tmdb_data,
                in_library=in_library,
                request_count=1,
            )
            session.add(movie_req)
            await session.flush()

            # Record requesting user
            session.add(MovieRequestUser(
                movie_request_id=movie_req.id,
                tg_user_id=db_user.id,
            ))

            await session.commit()
            await _send_reply_card(message, movie_req, is_duplicate=False)

        except Exception:
            await session.rollback()
            logger.exception("Error handling movie request from tg_uid=%s", tg_user.id)
            try:
                await message.reply("An error occurred processing your request.")
            except Exception:
                pass


# ──────────────────────────────────────────────
#  Reply card
# ──────────────────────────────────────────────

async def _send_reply_card(
    message: TgMessage,
    req: MovieRequest,
    is_duplicate: bool,
) -> None:
    """Send a poster card reply to the user."""
    year = req.release_date[:4] if req.release_date else "N/A"
    media_label = "Movie" if req.media_type == "movie" else "TV"
    rating = f"{float(req.vote_average):.1f}" if req.vote_average else "N/A"

    # Status line
    if req.in_library:
        status_line = "\u2705 Already in library"
    elif is_duplicate:
        status_line = f"\U0001f504 {req.request_count} users requested"
    else:
        status_line = "\u23f3 Request submitted"

    caption = (
        f"\U0001f4fd <b>{req.title}</b>\n"
        f"TMDB: {req.tmdb_id} | {media_label} | {year}\n"
        f"\u2b50 {rating}"
    )
    if req.genres:
        caption += f" | {req.genres}"
    caption += f"\n\n{status_line}"

    poster_url = f"{TMDB_IMAGE_BASE}/w500{req.poster_path}" if req.poster_path else None

    try:
        if poster_url:
            await message.answer_photo(
                photo=poster_url,
                caption=caption,
                parse_mode="HTML",
            )
        else:
            await message.reply(caption, parse_mode="HTML")
    except Exception:
        # Fallback to text-only if photo fails
        logger.warning("Failed to send poster photo, falling back to text")
        await message.reply(caption, parse_mode="HTML")
