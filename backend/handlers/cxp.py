import logging
import os
import math
import random
import asyncio
import calendar
from datetime import datetime, timedelta, timezone
from telegram import Update, ChatPermissions, error
from telegram.ext import CallbackContext
import httpx
from telegram.helpers import escape_markdown

from database import db
from handlers.common import resolve_username, is_user_admin

logger = logging.getLogger(__name__)

# Emoji constants
POSITIVE_EMOJIS = {
    "👍",
    "👍🏻",
    "👍🏼",
    "👍🏽",
    "👍🏾",
    "👍🏿",
    "❤️",
    "🧡",
    "💛",
    "💚",
    "💙",
    "💜",
    "🖤",
    "🤍",
    "🤎",
    "❤️‍🔥",
    "💖",
    "💝",
    "💕",
    "💞",
    "💓",
    "💗",
    "💘",
    "💟",
    "🫶",
    "🫶🏻",
    "🫶🏼",
    "🫶🏽",
    "🫶🏾",
    "🫶🏿",
    "🔥",
    "💯",
    "👏",
    "👏🏻",
    "👏🏼",
    "👏🏽",
    "👏🏾",
    "👏🏿",
    "🎉",
    "🎊",
    "🤩",
    "😍",
    "🥰",
    "😘",
    "🤯",
    "🥳",
    "😎",
    "😇",
    "🥹",
    "🤤",
    "👑",
    "⭐",
    "🌟",
    "✨",
    "💫",
    "🌠",
    "🏆",
    "🥇",
    "🏅",
    "💎",
    "🚀",
    "📈",
    "🧠",
    "🥂",
    "🍻",
    "🤝",
    "🤝🏻",
    "🤝🏼",
    "🤝🏽",
    "🤝🏾",
    "🤝🏿",
    "🙌",
    "🙌🏻",
    "🙌🏼",
    "🙌🏽",
    "🙌🏾",
    "🙌🏿",
    "🪄",
    "🎯",
    "👌",
    "👌🏻",
    "👌🏼",
    "👌🏽",
    "👌🏾",
    "👌🏿",
    "✌️",
    "✌🏻",
    "✌🏼",
    "✌🏽",
    "✌🏾",
    "✌🏿",
    "🤌",
    "🤌🏻",
    "🤌🏼",
    "🤌🏽",
    "🤌🏾",
    "🤌🏿",
    "💪",
    "💪🏻",
    "💪🏼",
    "💪🏽",
    "💪🏾",
    "💪🏿",
    "💸",
    "💰",
    "💹",
}
NEGATIVE_EMOJIS = {
    "👎",
    "👎🏻",
    "👎🏼",
    "👎🏽",
    "👎🏾",
    "👎🏿",
    "😡",
    "🤬",
    "😠",
    "👿",
    "😾",
    "😤",
    "💢",
    "🤡",
    "🤮",
    "🤢",
    "💩",
    "🗑️",
    "🚮",
    "🚽",
    "📉",
    "🛑",
    "🚫",
    "❌",
    "✖️",
    "🤦",
    "🤦‍♂️",
    "🤦‍♀️",
    "🙄",
    "😒",
    "😑",
    "😐",
    "🤨",
    "🥱",
    "😴",
    "🖕",
    "🖕🏻",
    "🖕🏼",
    "🖕🏽",
    "🖕🏾",
    "🖕🏿",
    "🙅",
    "🙅‍♂️",
    "🙅‍♀️",
}

NORMALIZED_POSITIVE = {e.replace("\ufe0f", "") for e in POSITIVE_EMOJIS}
NORMALIZED_NEGATIVE = {e.replace("\ufe0f", "") for e in NEGATIVE_EMOJIS}

from collections import OrderedDict


class MemoryCache:
    """In-memory cache to skip DB reads for rate limiting and message history."""

    def __init__(self, capacity: int):
        self.cache = OrderedDict()
        self.capacity = capacity

    def get(self, key):
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key, value):
        self.cache[key] = value
        self.cache.move_to_end(key)
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)


MESSAGE_AUTHOR_CACHE = MemoryCache(5000)
RATE_LIMIT_CACHE = MemoryCache(5000)
UNLINKED_WARNING_CACHE = MemoryCache(5000)

MESSAGE_CXP = 50
POSITIVE_REACTION_BASE = 50
NEGATIVE_REACTION_BASE = -50
RATE_LIMIT_SECONDS = 60


def calculate_level(cxp: int) -> int:
    """Calculate user level from total CXP based on inverse quadratic formula."""
    safe_cxp = max(0, cxp)
    return math.floor((1 + math.sqrt(1 + 4 * safe_cxp / 250)) / 2)


async def apply_level_permissions(bot, chat_id: int, user_id: int, level: int):
    """Apply specific Telegram chat permissions to a user based on their CXP level."""
    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_audios=level >= 5,
        can_send_documents=level >= 5,
        can_send_photos=level >= 2,
        can_send_videos=level >= 5,
        can_send_video_notes=False, # Group default is off
        can_send_voice_notes=False, # Group default is off
        can_send_polls=False,       # Group default is off
        can_send_other_messages=level >= 2,
        can_add_web_page_previews=level >= 5,
        can_change_info=False,
        can_invite_users=True,
        can_pin_messages=False,
        can_manage_topics=False,
    )
    try:
        await bot.restrict_chat_member(chat_id, user_id, permissions, use_independent_chat_permissions=True)
    except error.RetryAfter:
        raise
    except Exception as e:
        logger.error("Failed to apply permissions for level %s to user %s: %s", level, user_id, e)


def _get_member_tag_string(level: int) -> str:
    if level >= 60:
        return "Zero-Day Broker"
    elif level >= 50:
        return "Whale Hunter"
    elif level >= 40:
        return "Clean Splicer"
    elif level >= 30:
        return "Ledger Forger"
    elif level >= 20:
        return "Dirty Phreak"
    elif level >= 10:
        return "True Operator"
    elif level >= 5:
        return "Hash Cracker"
    elif level >= 1:
        return "Script Kiddie"
    return ""


async def _update_member_tag(bot, user_id: int, new_level: int):
    """Automatically assign a group member tag based on new CXP level."""
    config = await db.get_config()
    if not config:
        return

    main_group_id = config.get("main_group_id")
    if not main_group_id:
        return

    tag = _get_member_tag_string(new_level)

    if not tag:
        return

    url = f"{bot.base_url}/setChatMemberTag"

    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url, data={"chat_id": main_group_id, "user_id": user_id, "tag": tag}
                )
                data = resp.json()

                if data.get("ok"):
                    logger.info("Successfully set member tag '%s' for %s", tag, user_id)
                    break

                # Handle Telegram Errors
                error_code = data.get("error_code")
                desc = data.get("description", "").lower()

                if error_code == 429:
                    retry_after = data.get("parameters", {}).get("retry_after", 5)
                    logger.warning(
                        "Rate limited parsing tag for %s. Sleeping %s seconds...",
                        user_id,
                        retry_after,
                    )
                    await asyncio.sleep(retry_after)
                    continue

                # Benign skips (people who left, deleted their account, invalid IDs, or group creators)
                skip_descs = [
                    "user_not_participant",
                    "user is deactivated",
                    "chat_creator_required",
                    "invalid user_id",
                ]
                if error_code in [400, 403] and any(s in desc for s in skip_descs):
                    logger.debug("Skipping tag for %s: %s", user_id, desc)
                    break

                logger.warning("Failed to set member tag for %s: %s", user_id, data)
                break

        except Exception as e:
            logger.error("Error setting member tag for %s: %s", user_id, e)
            break


# async def backfill_member_tags(bot):
#     """Temporary function to backfill member tags for all existing users on startup."""
#     logger.info("Starting CXP member tag backfill...")
#     if not db.pool:
#         logger.warning("DB pool not initialized, skipping backfill.")
#         return

#     async with db.pool.acquire() as conn:
#         users = await conn.fetch("SELECT user_id, cxp FROM users")

#     count = 0
#     for row in users:
#         user_id = row["user_id"]
#         cxp = row.get("cxp", 0)
#         level = calculate_level(cxp)
#         if level >= 1:
#             await _update_member_tag(bot, user_id, level)
#             count += 1
#             await asyncio.sleep(0.1)  # Add slight delay to prevent massive 429 waves

#     logger.info("Finished CXP member tag backfill for %s users.", count)


async def _announce_level_up(context: CallbackContext, user, new_level: int):
    """Announce level up in the dedicated CXP topic if configured."""
    # Update the member tag asynchronously to prevent blocking the announcement
    context.application.create_task(_update_member_tag(context.bot, user.id, new_level))

    config = await db.get_config()
    if not config:
        return

    cxp_topic_id = config.get("cxp_topic_id")
    main_group_id = config.get("main_group_id")

    if cxp_topic_id and main_group_id:
        try:
            full_name = user.first_name + (
                f" {user.last_name}" if getattr(user, "last_name", None) else ""
            )
            mention = f'<a href="tg://user?id={user.id}">{full_name}</a>'
            msg = f"🎉 {mention} has reached <b>Level {new_level}</b>!"
            await context.bot.send_message(
                chat_id=main_group_id,
                message_thread_id=cxp_topic_id,
                text=msg,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Failed to send level up announcement: %s", e)


async def _process_db_message_and_cxp(
    context: CallbackContext, chat_id: int, msg_id: int, user, current_cxp: int
):
    """Background task to save the message and award CXP without blocking the chat."""
    await db.record_message(chat_id, msg_id, user.id)
    first_name = getattr(user, "first_name", None)
    if first_name:
        last_name = getattr(user, "last_name", None)
        display_name = first_name + (f" {last_name}" if last_name else "")
    else:
        display_name = getattr(
            user, "title", getattr(user, "username", f"User {user.id}")
        )
    await db.update_user_display_name(
        user.id, display_name, getattr(user, "username", None)
    )

    old_level = calculate_level(current_cxp)
    success = await db.update_user_cxp(user.id, MESSAGE_CXP, update_timestamp=True)
    if success:
        new_level = calculate_level(current_cxp + MESSAGE_CXP)
        if new_level > old_level:
            await _announce_level_up(context, user, new_level)
        if new_level != old_level:
            context.application.create_task(
                apply_level_permissions(context.bot, chat_id, user.id, new_level)
            )


async def track_message_activity(update: Update, context: CallbackContext):
    """Track messaging activity using an in-memory cache to prevent DB bottlenecking."""
    if not update.effective_user or not update.message:
        return

    # If the user is a bot, it could be an anonymous admin or channel
    if getattr(update.effective_user, "is_bot", True):
        # We allow messages sent on behalf of a channel or anonymous admin group
        if not update.message.sender_chat:
            return

        chat_source = update.message.sender_chat
        channel_id = chat_source.id

        if getattr(chat_source, "type", "") == "channel":
            owner_id = await db.get_channel_owner(channel_id)
            if owner_id:
                user_id = owner_id
                db_user = await db.get_user(owner_id)
                
                class MockUser:
                    def __init__(self):
                        self.id = owner_id
                        self.username = db_user.get("username") if db_user else None
                        self.first_name = db_user.get("display_name") if db_user else f"Owner {owner_id}"
                        self.last_name = None
                        self.is_bot = False
                        
                user_obj = MockUser()
            else:
                user_id = channel_id
                class MockUser:
                    def __init__(self, chat):
                        self.id = chat.id
                        self.username = chat.username
                        self.first_name = chat.title or chat.username or f"Channel {chat.id}"
                        self.last_name = None
                        self.is_bot = False
                user_obj = MockUser(chat_source)
                
                # Setup warning for unlinked channels
                now = datetime.now()
                last_warn = UNLINKED_WARNING_CACHE.get(channel_id)
                if not last_warn or (now - last_warn).total_seconds() > 3600:
                    UNLINKED_WARNING_CACHE.put(channel_id, now)
                    try:
                        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
                        bot_username = context.bot.username
                        keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔗 Link Channel", url=f"https://t.me/{bot_username}?start=setchannel")]
                        ])
                        msg = await update.message.reply_text(
                            f"⚠️ *Unlinked Channel Warning*\n\n"
                            f"You are posting as a channel that is not linked to your user account. This means you will not earn CXP and your user-level permissions will not apply.\n\n"
                            f"Please click the button below to link it.",
                            reply_markup=keyboard,
                            parse_mode="Markdown"
                        )
                        context.job_queue.run_once(
                            _delete_message_job,
                            60,
                            data={"chat_id": msg.chat_id, "message_id": msg.message_id}
                        )
                    except Exception as e:
                        logger.error(f"Failed to send unlinked channel warning: {e}")
        else:
            # Anonymous admin group
            user_id = channel_id
            class MockUser:
                def __init__(self, chat):
                    self.id = chat.id
                    self.username = chat.username
                    self.first_name = chat.title or chat.username or f"Channel {chat.id}"
                    self.last_name = None
                    self.is_bot = False
            user_obj = MockUser(chat_source)
    else:
        user_id = update.effective_user.id
        user_obj = update.effective_user

    chat_id = update.effective_chat.id

    config = await db.get_config()
    main_group_id = config.get("main_group_id") if config else None

    # Only track activity in the main group
    if chat_id != main_group_id:
        return

    # We need user data early for link moderation
    user_data = await db.get_user(user_id)
    current_cxp = user_data.get("cxp", 0) if user_data else 0
    level = calculate_level(current_cxp)

    # Link moderation for users below level 5
    if level < 5:
        has_link = False
        if update.message.entities:
            has_link = any(ent.type in ("url", "text_link") for ent in update.message.entities)
        elif update.message.caption_entities:
            has_link = any(ent.type in ("url", "text_link") for ent in update.message.caption_entities)

        if has_link:
            try:
                await update.message.delete()
                import html
                first_name_esc = html.escape(getattr(user_obj, "first_name", f"User {user_id}"))
                mention = f'<a href="tg://user?id={user_id}">{first_name_esc}</a>'
                
                thread_id = update.message.message_thread_id
                if update.effective_chat and update.effective_chat.is_forum and thread_id is None:
                    thread_id = 1
                    
                msg = await context.bot.send_message(
                    chat_id=chat_id,
                    message_thread_id=thread_id,
                    text=f"🚫 {mention}, you cannot send links until you reach level 5.",
                    parse_mode="HTML"
                )
                context.job_queue.run_once(
                    _delete_message_job,
                    60,
                    data={"chat_id": chat_id, "message_id": msg.message_id}
                )
            except Exception as e:
                logger.error("Failed to delete link message or send warning: %s", e)
            return

    # Fast in-memory cache update for reactions
    MESSAGE_AUTHOR_CACHE.put((chat_id, update.message.message_id), user_id)

    # Fast in-memory rate limiting check
    now = datetime.now()
    last_msg_time = RATE_LIMIT_CACHE.get(user_id)

    if last_msg_time and (now - last_msg_time).total_seconds() < RATE_LIMIT_SECONDS:
        # Rate limited. Just log the message in the background, skip CXP.
        context.application.create_task(
            db.record_message(chat_id, update.message.message_id, user_id)
        )
        return

    # User is eligible for CXP! Update memory cache immediately.
    RATE_LIMIT_CACHE.put(user_id, now)

    if not user_data:
        # Fallback to backgrounding the insert if user vanished
        context.application.create_task(
            db.record_message(chat_id, update.message.message_id, user_id)
        )
        return

    # Dispatch to background task to keep the handler lightning fast
    context.application.create_task(
        _process_db_message_and_cxp(
            context,
            chat_id,
            update.message.message_id,
            user_obj,
            current_cxp,
        )
    )


async def _resolve_reaction_emoji(reaction, context: CallbackContext) -> str | None:
    if reaction.type == "emoji":
        return reaction.emoji
    elif reaction.type == "custom_emoji":
        try:
            stickers = await context.bot.get_custom_emoji_stickers(
                [reaction.custom_emoji_id]
            )
            if stickers and stickers[0].emoji:
                return stickers[0].emoji
        except Exception as e:
            logger.warning(
                "Failed to resolve custom emoji %s: %s", reaction.custom_emoji_id, e
            )
    return None


async def evaluate_reaction(update: Update, context: CallbackContext):
    """Parse reactions and apply Karma scaled by reactor level."""
    if not update.message_reaction:
        return

    reaction_update = update.message_reaction

    # If the user is missing or is a bot, try getting the actor_chat (for channels)
    reactor_id = None
    if reaction_update.user and not reaction_update.user.is_bot:
        reactor_id = reaction_update.user.id
    elif reaction_update.actor_chat:
        reactor_id = reaction_update.actor_chat.id
        
        # Check if the reactor chat is a linked channel
        if getattr(reaction_update.actor_chat, "type", "") == "channel":
            owner_id = await db.get_channel_owner(reactor_id)
            if owner_id:
                reactor_id = owner_id

    if not reactor_id:
        return

    # Message author caching
    author_id = MESSAGE_AUTHOR_CACHE.get(
        (reaction_update.chat.id, reaction_update.message_id)
    )
    if not author_id:
        author_id = await db.get_message_author(
            reaction_update.chat.id, reaction_update.message_id
        )
        if not author_id:
            return
        # Reseed cache
        MESSAGE_AUTHOR_CACHE.put(
            (reaction_update.chat.id, reaction_update.message_id), author_id
        )

    # Don't let users farm karma on their own messages
    if author_id == reactor_id:
        return

    reactor_data = await db.get_user(reactor_id)
    if not reactor_data:
        return

    reactor_level = calculate_level(reactor_data.get("cxp", 0))
    multiplier = 1.0 + ((reactor_level - 1) * 0.05)

    # Calculate difference in emojis
    old_emojis = []
    for r in reaction_update.old_reaction:
        resolved = await _resolve_reaction_emoji(r, context)
        if resolved:
            old_emojis.append(resolved.replace("\ufe0f", ""))

    new_emojis = []
    for r in reaction_update.new_reaction:
        resolved = await _resolve_reaction_emoji(r, context)
        if resolved:
            new_emojis.append(resolved.replace("\ufe0f", ""))

    added = [e for e in new_emojis if e not in old_emojis]
    removed = [e for e in old_emojis if e not in new_emojis]

    total_delta = 0
    for e in added:
        if e in NORMALIZED_POSITIVE:
            total_delta += POSITIVE_REACTION_BASE * multiplier
        elif e in NORMALIZED_NEGATIVE:
            total_delta += NEGATIVE_REACTION_BASE * multiplier

    for e in removed:
        if e in NORMALIZED_POSITIVE:
            total_delta -= POSITIVE_REACTION_BASE * multiplier
        elif e in NORMALIZED_NEGATIVE:
            total_delta -= NEGATIVE_REACTION_BASE * multiplier

    if total_delta != 0:
        total_delta = int(round(total_delta))
        author_data = await db.get_user(author_id)
        if not author_data:
            return

        old_level = calculate_level(author_data.get("cxp", 0))
        await db.update_user_cxp(author_id, total_delta)
        new_data = await db.get_user(author_id)
        new_cxp = new_data.get("cxp", 0)
        new_level = calculate_level(new_cxp)

        if new_level != old_level:
            context.application.create_task(
                apply_level_permissions(context.bot, reaction_update.chat.id, author_id, new_level)
            )

        if new_level > old_level:
            try:
                author_user = await context.bot.get_chat(author_id)
                await _announce_level_up(context, author_user, new_level)
            except Exception as e:
                logger.warning(
                    "Could not fetch author %s for level up announcement: %s",
                    author_id,
                    e,
                )


async def _delete_message_job(context: CallbackContext):
    """Job to automatically delete a message."""
    chat_id = context.job.data.get("chat_id")
    message_id = context.job.data.get("message_id")
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass


async def enforce_cxp_topic(
    update: Update, context: CallbackContext, main_group_id, cxp_topic_id
) -> bool:
    """Check if the command was used in the correct CXP topic, and if not, warn and delete."""
    if not update.message:
        return True

    thread_id = update.message.message_thread_id
    if update.effective_chat and update.effective_chat.is_forum and thread_id is None:
        thread_id = 1

    if thread_id != cxp_topic_id:
        if main_group_id and cxp_topic_id and update.effective_chat.id == main_group_id:
            try:
                await update.message.delete()
            except Exception:
                pass

            chat_id_str = str(main_group_id)
            if chat_id_str.startswith("-100"):
                chat_id_str = chat_id_str[4:]
            topic_link = f"https://t.me/c/{chat_id_str}/{cxp_topic_id}"

            msg = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                message_thread_id=update.message.message_thread_id,
                text=f"This command only works in the [Bot Command Center]({topic_link}) topic.",
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
            context.job_queue.run_once(
                _delete_message_job,
                60,
                data={"chat_id": msg.chat_id, "message_id": msg.message_id},
            )
        return False
    return True


async def user_stats_cmd(update: Update, context: CallbackContext):
    """Handler for /level."""
    if not update.effective_user or not update.message:
        return

    if (
        getattr(update.effective_user, "is_bot", True)
        and not update.message.sender_chat
    ):
        return

    config = await db.get_config()
    cxp_topic_id = config.get("cxp_topic_id") if config else None
    main_group_id = config.get("main_group_id") if config else None

    if not await enforce_cxp_topic(update, context, main_group_id, cxp_topic_id):
        return

    try:
        await update.message.delete()
    except Exception as e:
        logger.warning(f"Failed to delete /level message: {e}")

    if getattr(update.effective_user, "is_bot", True) and update.message.sender_chat:
        target_id = update.message.sender_chat.id
        target_name = (
            update.message.sender_chat.title
            or update.message.sender_chat.username
            or f"Channel {target_id}"
        )
        if getattr(update.message.sender_chat, "type", "") == "channel":
            owner_id = await db.get_channel_owner(target_id)
            if owner_id:
                target_id = owner_id
                db_user = await db.get_user(owner_id)
                owner_name = db_user.get("display_name") if db_user else f"Owner {owner_id}"
                target_name = f"{owner_name} (via {update.message.sender_chat.title})"
    else:
        target_id = update.effective_user.id
        target_name = update.effective_user.first_name + (
            f" {update.effective_user.last_name}"
            if update.effective_user.last_name
            else ""
        )

    # Check for reply targeting another user.
    # Channels automatically "reply" to the root channel post when posting in the discussion group.
    # Topics also automatically "reply" to the thread creation message.
    # We must explicitly exclude `is_automatic_forward` and topic root messages.
    target_chat = None
    target_user = None

    if update.message.reply_to_message and not getattr(
        update.message, "is_automatic_forward", False
    ):
        # If it's a forum topic, ignore the implicit reply to the topic starter message
        if (
            update.message.is_topic_message
            and update.message.reply_to_message.message_id
            == update.message.message_thread_id
        ):
            pass  # Ignore implicit topic reply
        else:
            target_chat = update.message.reply_to_message.sender_chat
            target_user = update.message.reply_to_message.from_user

    if target_chat:
        target_id = target_chat.id
        target_name = (
            target_chat.title or target_chat.username or f"Channel {target_id}"
        )
        if getattr(target_chat, "type", "") == "channel":
            owner_id = await db.get_channel_owner(target_id)
            if owner_id:
                target_id = owner_id
                db_user = await db.get_user(owner_id)
                owner_name = db_user.get("display_name") if db_user else f"Owner {owner_id}"
                target_name = f"{owner_name} (via {target_chat.title})"
    elif target_user and not getattr(target_user, "is_bot", False):
        target_id = target_user.id
        target_name = target_user.first_name

    # Check for arguments targeting another user
    if context.args:
        # We are seeking a different user. Nullify the default target_id.
        arg_str = " ".join(context.args)
        resolved_id, resolved_name = await resolve_username(arg_str, update, context)

        if resolved_id:
            target_id = resolved_id
            target_name = resolved_name
        else:
            if main_group_id and cxp_topic_id:
                await context.bot.send_message(
                    chat_id=main_group_id,
                    message_thread_id=cxp_topic_id,
                    text="Could not resolve a target user from the arguments provided via Telegram. Please ensure the @username is correct.",
                )
            return

    user_data = await db.get_user(target_id)
    if not user_data:
        if main_group_id and cxp_topic_id:
            await context.bot.send_message(
                chat_id=main_group_id,
                message_thread_id=cxp_topic_id,
                text="No stats found for that user.",
            )
        return

    cxp = user_data.get("cxp", 0)
    level = calculate_level(cxp)
    is_admin = user_data.get("is_admin", False)

    # If not manually set as admin in DB, fallback to Telegram Group check
    if not is_admin and config:
        if main_group_id:
            try:
                member = await context.bot.get_chat_member(main_group_id, target_id)
                if member.status in ("administrator", "creator"):
                    is_admin = True
                    await db.update_user_admin_status(target_id, True)
            except Exception:
                pass

    if is_admin:
        rank_display = "Admin"
    else:
        rank = await db.get_user_rank(cxp)
        rank_display = f"#{rank}"

    next_level_cxp = 250 * (level + 1) * level

    # Try our best to get a name if target_name is missing, which happens for channels
    if not target_name:
        try:
            chat = await context.bot.get_chat(target_id)
            target_name = chat.title or chat.first_name or f"Channel {target_id}"
        except Exception:
            target_name = f"User/Channel {target_id}"

    level_title = _get_member_tag_string(level)
    level_display = f"{level} ({level_title})" if level_title else str(level)

    safe_target_name = escape_markdown(target_name, version=1)

    msg = (
        f"📊 **Statistics for {safe_target_name}**\n\n"
        f"🏆 **Rank:** {rank_display}\n"
        f"🔰 **Level:** {level_display}\n"
        f"✨ **CXP:** {cxp:,} / {next_level_cxp:,}"
    )

    if main_group_id and cxp_topic_id:
        await context.bot.send_message(
            chat_id=main_group_id,
            message_thread_id=cxp_topic_id,
            text=msg,
            parse_mode="Markdown",
        )


def parse_leaderboard_args(args, config):
    """Returns (start_date, end_date, title_string) or (None, None, 'Global Leaderboard (All-Time)') for all-time"""
    if not args:
        return None, None, "Global Leaderboard (All-Time)"
        
    arg_str = " ".join(args).lower().strip()
    now_utc = datetime.now(timezone.utc).date()
    
    if arg_str == "contest":
        if config and config.get("contest_start") and config.get("contest_end"):
            return config["contest_start"], config["contest_end"], "Contest Leaderboard"
        return None, None, "Contest Leaderboard (No Dates Set)"
        
    if arg_str in ["today", "day", "daily", "this day"]:
        return now_utc, now_utc, "Daily Leaderboard"
        
    if arg_str == "yesterday":
        yesterday = now_utc - timedelta(days=1)
        return yesterday, yesterday, "Yesterday's Leaderboard"
        
    if arg_str in ["week", "weekly", "this week"]:
        start_of_week = now_utc - timedelta(days=now_utc.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        return start_of_week, end_of_week, "Weekly Leaderboard"
        
    if arg_str == "last week":
        start_of_last_week = now_utc - timedelta(days=now_utc.weekday() + 7)
        end_of_last_week = start_of_last_week + timedelta(days=6)
        return start_of_last_week, end_of_last_week, "Last Week's Leaderboard"
        
    if arg_str in ["month", "monthly", "this month"]:
        start_of_month = now_utc.replace(day=1)
        last_day = calendar.monthrange(now_utc.year, now_utc.month)[1]
        end_of_month = now_utc.replace(day=last_day)
        return start_of_month, end_of_month, "Monthly Leaderboard"
        
    if arg_str == "last month":
        first_of_this_month = now_utc.replace(day=1)
        end_of_last_month = first_of_this_month - timedelta(days=1)
        start_of_last_month = end_of_last_month.replace(day=1)
        return start_of_last_month, end_of_last_month, "Last Month's Leaderboard"
        
    # Handle specific months
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
    }
    
    if arg_str in months:
        target_month = months[arg_str]
        target_year = now_utc.year
        if target_month > now_utc.month:
            target_year -= 1 # Assume they mean last year if the month hasn't happened yet this year
            
        start_date = datetime(target_year, target_month, 1).date()
        last_day = calendar.monthrange(target_year, target_month)[1]
        end_date = datetime(target_year, target_month, last_day).date()
        month_name = calendar.month_name[target_month]
        return start_date, end_date, f"{month_name} Leaderboard"
        
    return None, None, "Global Leaderboard (All-Time)"


async def leaderboard_cmd(update: Update, context: CallbackContext):
    """Handler for /leaderboard. Shows top 10, skipping admins."""
    config = await db.get_config()
    cxp_topic_id = config.get("cxp_topic_id") if config else None
    main_group_id = config.get("main_group_id") if config else None

    if not await enforce_cxp_topic(update, context, main_group_id, cxp_topic_id):
        return

    try:
        await update.message.delete()
    except Exception as e:
        logger.warning(f"Failed to delete /leaderboard message: {e}")

    start_date, end_date, title = parse_leaderboard_args(context.args, config)

    # Fetch a wider net in case many are admins
    top_candidates = await db.get_leaderboard(limit=50, start_date=start_date, end_date=end_date)
    if not top_candidates:
        if main_group_id and cxp_topic_id:
            await context.bot.send_message(
                chat_id=main_group_id,
                message_thread_id=cxp_topic_id,
                text=f"The {title.lower()} is currently empty!",
            )
        return

    actual_top_10 = []
    for row in top_candidates:
        if len(actual_top_10) >= 10:
            break

        u_id = row.get("user_id")

        # Check if admin
        is_admin = row.get("is_admin", False)

        # If not manually set as admin in DB, fallback to Telegram Group check
        if not is_admin and main_group_id:
            try:
                member = await context.bot.get_chat_member(main_group_id, u_id)
                if member.status in ("administrator", "creator"):
                    is_admin = True
                    await db.update_user_admin_status(u_id, True)
            except Exception:
                pass

        if not is_admin:
            actual_top_10.append(row)

    if not actual_top_10:
        if main_group_id and cxp_topic_id:
            await context.bot.send_message(
                chat_id=main_group_id,
                message_thread_id=cxp_topic_id,
                text="No non-admin users found for the leaderboard.",
            )
        return

    msg = f"🏆 **{title} (Top 10)** 🏆\n\n"

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, row in enumerate(actual_top_10):
        u_id = row.get("user_id")
        cxp = row.get("cxp", 0)
        total_cxp = row.get("total_cxp", cxp)
        level = calculate_level(total_cxp)
        medal = medals[i] if i < len(medals) else f"#{i+1}"

        name = row.get("display_name")
        if not name:
            username = row.get("username")
            if username:
                name = f"@{username}"
            else:
                try:
                    chat = await context.bot.get_chat(u_id)
                    name = chat.title or chat.first_name or f"Channel {u_id}"
                except Exception:
                    name = f"User {u_id}"

        safe_name = escape_markdown(name, version=1)
        msg += f"{medal} **{safe_name}** — Level {level} ({cxp:,} CXP)\n"

    if main_group_id and cxp_topic_id:
        await context.bot.send_message(
            chat_id=main_group_id,
            message_thread_id=cxp_topic_id,
            text=msg,
            parse_mode="Markdown",
        )


async def get_id_cmd(update: Update, context: CallbackContext):
    """Test command to explicitly check API/DB username resolution and reply parsing. (was /id, now /checkid)"""
    if not update.effective_user or not update.message:
        return

    if (
        getattr(update.effective_user, "is_bot", True)
        and not update.message.sender_chat
    ):
        return

    config = await db.get_config()
    main_group_id = config.get("main_group_id") if config else None

    # Determine actor identity
    actor_id = update.effective_user.id
    if getattr(update.effective_user, "is_bot", True) and update.message.sender_chat:
        actor_id = update.message.sender_chat.id

    if not await is_user_admin(actor_id, main_group_id, context):
        return

    # 1. Check for replied-to message
    if (
        update.message.reply_to_message
        and not getattr(update.message, "is_automatic_forward", False)
        and getattr(update.message.reply_to_message.from_user, "id", None)
    ):
        # Ignore implicit replies to the topic starter message
        if not (
            update.message.is_topic_message
            and update.message.reply_to_message.message_id
            == update.message.message_thread_id
        ):
            target_user = update.message.reply_to_message.from_user
            full_name = target_user.first_name + (
                f" {target_user.last_name}" if target_user.last_name else ""
            )
            safe_full_name = escape_markdown(full_name, version=1)
            await update.message.reply_text(
                f"Reply Resolution Success!\nName: {safe_full_name}\nID: `{target_user.id}`",
                parse_mode="Markdown",
            )
            return

    # 2. Check for @username arguments
    args = context.args
    if not args:
        await update.message.reply_text(
            "Please provide a @username or reply to their message."
        )
        return

    arg_str = args[0]
    resolved_id, resolved_name = await resolve_username(arg_str, update, context)

    if resolved_id:
        safe_resolved_name = escape_markdown(resolved_name, version=1)
        await update.message.reply_text(
            f"Resolution Success!\nName: {safe_resolved_name}\nID: `{resolved_id}`",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "Failed to resolve that handle via Telegram API or DB Tracker."
        )


async def give_cxp_cmd(update: Update, context: CallbackContext):
    """Admin only: /give <val> [@username/reply]. Grant or remove CXP."""
    if not update.effective_user or not update.message:
        return

    if (
        getattr(update.effective_user, "is_bot", True)
        and not update.message.sender_chat
    ):
        return

    config = await db.get_config()
    main_group_id = config.get("main_group_id") if config else None

    # Must be in main group
    if not main_group_id or update.effective_chat.id != main_group_id:
        return

    # Determine actor identity (User or Channel)
    actor_id = update.effective_user.id
    if getattr(update.effective_user, "is_bot", True) and update.message.sender_chat:
        actor_id = update.message.sender_chat.id

    if not await is_user_admin(actor_id, main_group_id, context):
        return

    # Parse args (could be /give 100 @user or /give @user 100)
    args = context.args
    if not args and not update.message.reply_to_message:
        await update.message.reply_text(
            "Usage: `/give <amount> [@username]` or reply to a message with `/give <amount>`",
            parse_mode="Markdown",
        )
        return

    target_id = None
    target_name = None
    delta_cxp = None

    # Try reply target
    # Channels automatically "reply" to the root channel post when posting in the discussion group.
    # We must explicitly exclude `is_automatic_forward` logic and topic roots.
    target_chat = None
    target_user = None

    if update.message.reply_to_message and not getattr(
        update.message, "is_automatic_forward", False
    ):
        # If it's a forum topic, ignore the implicit reply to the topic starter message
        if (
            update.message.is_topic_message
            and update.message.reply_to_message.message_id
            == update.message.message_thread_id
        ):
            pass
        else:
            target_chat = update.message.reply_to_message.sender_chat
            target_user = update.message.reply_to_message.from_user

    if target_chat:
        target_id = target_chat.id
        target_name = (
            target_chat.title or target_chat.username or f"Channel {target_id}"
        )
    elif target_user and not getattr(target_user, "is_bot", False):
        target_id = target_user.id
        target_name = target_user.first_name

    # Parse args to support varying formats: `/give 1000 @usr`, `/give John Doe 1000`
    arg_str = None
    target_args = []

    for arg in args:
        if delta_cxp is None:
            try:
                delta_cxp = int(arg)
                continue
            except ValueError:
                pass
        target_args.append(arg)

    if target_args:
        arg_str = " ".join(target_args)

    # Attempt resolution to allow explicit usernames to override a reply target
    # If no explicit @ string was found, still pass it through for text_mentions
    resolved_id, resolved_name = await resolve_username(arg_str, update, context)
    if resolved_id:
        target_id = resolved_id
        target_name = resolved_name

    if target_id is None:
        await update.message.reply_text(
            "Could not resolve the target user via Telegram. Please ensure the @username is correct or reply to their message."
        )
        return

    if delta_cxp is None:
        await update.message.reply_text("Invalid amount provided.")
        return

    # Safely fetch target and update
    target_data = await db.get_user(target_id)
    if not target_data:
        await update.message.reply_text("Could not fetch target user data.")
        return

    old_level = calculate_level(target_data.get("cxp", 0))
    await db.update_user_cxp(target_id, delta_cxp)
    new_data = await db.get_user(target_id)
    new_cxp = new_data.get("cxp", 0)
    new_level = calculate_level(new_cxp)

    if new_level != old_level:
        context.application.create_task(
            _update_member_tag(context.bot, target_id, new_level)
        )
        context.application.create_task(
            apply_level_permissions(context.bot, main_group_id, target_id, new_level)
        )

    action = "granted" if delta_cxp > 0 else "removed"
    msg = f"✅ Successfully {action} {abs(delta_cxp):,} CXP to {target_name}. Their new total is {new_cxp:,} CXP (Level {new_level})."
    await update.message.reply_text(msg)


async def set_admin_cmd(update: Update, context: CallbackContext):
    """Bot Owner only: /setadmin <true/false> [@username/reply]. Grant or remove DB admin status."""
    from bot import BOT_OWNER_ID  # Ensure only the ultimate absolute owner can run this

    if not BOT_OWNER_ID or update.effective_user.id != BOT_OWNER_ID:
        return

    if not update.effective_user or not update.message:
        return

    # Parse args (can be `/setadmin true @user` or `/setadmin @user true`)
    args = context.args
    if not args and not update.message.reply_to_message:
        await update.message.reply_text(
            "Usage: `/setadmin [true/false] [@username]` or reply to a message with `/setadmin [true/false]`",
            parse_mode="Markdown",
        )
        return

    target_id = None
    target_name = None
    target_chat = None
    target_user = None
    is_admin_flag = None

    # Try reply target
    if update.message.reply_to_message and not getattr(
        update.message, "is_automatic_forward", False
    ):
        if (
            update.message.is_topic_message
            and update.message.reply_to_message.message_id
            == update.message.message_thread_id
        ):
            pass
        else:
            target_chat = update.message.reply_to_message.sender_chat
            target_user = update.message.reply_to_message.from_user

    if target_chat:
        target_id = target_chat.id
        target_name = (
            target_chat.title or target_chat.username or f"Channel {target_id}"
        )
    elif target_user and not getattr(target_user, "is_bot", False):
        target_id = target_user.id
        target_name = target_user.first_name

    arg_str = None
    target_args = []

    for arg in args:
        lower_arg = arg.lower()
        if is_admin_flag is None and lower_arg in ["true", "1", "yes", "t"]:
            is_admin_flag = True
            continue
        elif is_admin_flag is None and lower_arg in ["false", "0", "no", "f", "remove"]:
            is_admin_flag = False
            continue

        target_args.append(arg)

    if target_args:
        arg_str = " ".join(target_args)

    resolved_id, resolved_name = await resolve_username(arg_str, update, context)
    if resolved_id:
        target_id = resolved_id
        target_name = resolved_name

    if target_id is None:
        await update.message.reply_text(
            "Could not resolve the target user via Telegram. Please ensure the @username is correct or reply to their message."
        )
        return

    if is_admin_flag is None:
        await update.message.reply_text("Please provide true or false.")
        return

    # Safely fetch target and update
    target_data = await db.get_user(target_id)
    if not target_data:
        # User doesn't exist, we should seed them
        await db.record_message(
            update.effective_chat.id, update.message.message_id, target_id
        )

    await db.update_user_admin_status(target_id, is_admin_flag)

    action = (
        "granted DB Admin powers to" if is_admin_flag else "revoked DB Admin powers for"
    )
    await update.message.reply_text(f"✅ Successfully {action} {target_name}.")


async def steal_cxp_cmd(update: Update, context: CallbackContext):
    """Member command: /steal. Steal 25-100 CXP from a random user with 1-hour cooldown."""
    if not update.effective_user or not update.message:
        return

    # Check if we are in the main group and cxp topic
    config = await db.get_config()
    main_group_id = config.get("main_group_id") if config else None
    cxp_topic_id = config.get("cxp_topic_id") if config else None

    if not main_group_id or update.effective_chat.id != main_group_id:
        return

    if not await enforce_cxp_topic(update, context, main_group_id, cxp_topic_id):
        return

    user_id = update.effective_user.id
    user_name = update.effective_user.first_name + (
        f" {update.effective_user.last_name}" if update.effective_user.last_name else ""
    )

    try:
        await update.message.delete()
    except Exception as e:
        logger.warning(f"Failed to delete /steal message: {e}")

    # 1. Check Cooldown
    user_data = await db.get_user(user_id)
    last_steal = user_data.get("last_steal_time")
    if last_steal:
        now = datetime.now()
        # last_steal is likely a datetime object from asyncpg
        time_diff = now - last_steal
        remaining_seconds = 3600 - time_diff.total_seconds()
        if remaining_seconds > 0:
            minutes = int(remaining_seconds // 60)
            seconds = int(remaining_seconds % 60)
            safe_user_name = escape_markdown(user_name, version=1)
            await context.bot.send_message(
                chat_id=main_group_id,
                message_thread_id=cxp_topic_id,
                text=f"⏳ {safe_user_name}, you are on cooldown! Please wait `{minutes}m {seconds}s` before trying again.",
                parse_mode="Markdown",
            )
            return

    # 2. Resolve random target
    target_data = await db.get_random_user(user_id)
    if not target_data:
        await context.bot.send_message(
            chat_id=main_group_id,
            message_thread_id=cxp_topic_id,
            text="There is no one available to steal from!",
        )
        return

    target_id = target_data.get("user_id")
    target_name = target_data.get("display_name")

    if not target_name:
        username = target_data.get("username")
        if username:
            target_name = f"@{username}"
        else:
            try:
                chat = await context.bot.get_chat(target_id)
                target_name = (
                    chat.first_name
                    + (f" {chat.last_name}" if getattr(chat, "last_name", None) else "")
                    if chat.first_name
                    else chat.title or f"User {target_id}"
                )
            except Exception:
                target_name = f"User {target_id}"

    # 3. Perform Steal
    if random.random() < 0.10:
        if random.random() < 0.50:
            msg = f"📡 Jammer detected! {user_name} failed to steal!"
        else:
            msg = f"🛡️ Shield detected! {user_name} failed to steal!"

        await db.update_user_steal_time(user_id)

        await context.bot.send_message(
            chat_id=main_group_id,
            message_thread_id=cxp_topic_id,
            text=msg,
        )
        return

    STEAL_AMOUNT = random.randint(25, 100)

    target_old_level = calculate_level(target_data.get("cxp", 0))
    user_old_level = calculate_level(user_data.get("cxp", 0))

    # Deduct from target
    await db.update_user_cxp(target_id, -STEAL_AMOUNT)
    target_new_data = await db.get_user(target_id)
    target_new_level = calculate_level(target_new_data.get("cxp", 0))
    if target_new_level != target_old_level:
        context.application.create_task(
            _update_member_tag(context.bot, target_id, target_new_level)
        )
        context.application.create_task(
            apply_level_permissions(context.bot, main_group_id, target_id, target_new_level)
        )

    # Add to sender
    await db.update_user_cxp(user_id, STEAL_AMOUNT)
    user_new_data = await db.get_user(user_id)
    user_new_level = calculate_level(user_new_data.get("cxp", 0))
    if user_new_level != user_old_level:
        context.application.create_task(
            _update_member_tag(context.bot, user_id, user_new_level)
        )
        context.application.create_task(
            apply_level_permissions(context.bot, main_group_id, user_id, user_new_level)
        )

    # Update cooldown
    await db.update_user_steal_time(user_id)

    safe_user_name = escape_markdown(user_name, version=1)
    safe_target_name = escape_markdown(target_name, version=1)
    await context.bot.send_message(
        chat_id=main_group_id,
        message_thread_id=cxp_topic_id,
        text=f"🎯 **{safe_user_name}** stole `{STEAL_AMOUNT}` CXP from **{safe_target_name}**!",
        parse_mode="Markdown",
    )


async def contest_cmd(update: Update, context: CallbackContext):
    """Alias for /leaderboard contest."""
    context.args = ["contest"]
    await leaderboard_cmd(update, context)


async def setcontest_cmd(update: Update, context: CallbackContext):
    """Admin only: /setcontest <mm/dd/yy> <mm/dd/yy> OR <mm/dd/yy> <days> OR <days>. Set contest timeframe."""
    if not update.effective_user or not update.message:
        return

    if (
        getattr(update.effective_user, "is_bot", True)
        and not update.message.sender_chat
    ):
        return

    config = await db.get_config()
    main_group_id = config.get("main_group_id") if config else None

    # Determine actor identity
    actor_id = update.effective_user.id
    if getattr(update.effective_user, "is_bot", True) and update.message.sender_chat:
        actor_id = update.message.sender_chat.id

    if not await is_user_admin(actor_id, main_group_id, context):
        return

    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage:\n`/setcontest <days>` (starts today, inclusive length)\n`/setcontest <mm/dd/yy> <days>`\n`/setcontest <mm/dd/yy> <mm/dd/yy>`",
            parse_mode="Markdown",
        )
        return

    now_utc = datetime.now(timezone.utc).date()
    start_date = None
    end_date = None

    def parse_date(date_str):
        try:
            return datetime.strptime(date_str, "%m/%d/%y").date()
        except ValueError:
            return None

    if len(args) == 1:
        try:
            days = int(args[0])
            if days <= 0:
                await update.message.reply_text("Days must be > 0.")
                return
            start_date = now_utc
            end_date = start_date + timedelta(days=days-1)
        except ValueError:
            await update.message.reply_text("Invalid length in days.")
            return
    elif len(args) >= 2:
        start_date = parse_date(args[0])
        if not start_date:
            await update.message.reply_text("Invalid start date format. Use mm/dd/yy.")
            return
            
        try:
            days = int(args[1])
            if days <= 0:
                await update.message.reply_text("Days must be > 0.")
                return
            end_date = start_date + timedelta(days=days-1)
        except ValueError:
            end_date = parse_date(args[1])
            if not end_date:
                await update.message.reply_text("Invalid end date or days format. Use mm/dd/yy or an integer.")
                return

    if start_date and end_date:
        if end_date < start_date:
            await update.message.reply_text("End date must be after or equal to the start date.")
            return

        success = await db.update_config(contest_start=start_date, contest_end=end_date)
        if success:
            await update.message.reply_text(f"✅ Contest timeframe set:\nStart: {start_date.strftime('%Y-%m-%d')}\nEnd: {end_date.strftime('%Y-%m-%d')}")
        else:
            await update.message.reply_text("❌ Failed to update the database.")
    else:
        await update.message.reply_text("Invalid arguments.")


async def syncperms_cmd(update: Update, context: CallbackContext):
    """Admin command to backfill permissions for all users in the DB based on CXP."""
    if not update.effective_user or not update.message:
        return
        
    config = await db.get_config()
    main_group_id = config.get("main_group_id") if config else None
    cxp_topic_id = config.get("cxp_topic_id") if config else None

    if not await enforce_cxp_topic(update, context, main_group_id, cxp_topic_id):
        return

    # Check for admin permission
    user_id = update.effective_user.id
    bot_owner_id_str = os.getenv("BOT_OWNER_ID")
    bot_owner_id = int(bot_owner_id_str) if bot_owner_id_str else 0
    
    if user_id != bot_owner_id:
        user_data = await db.get_user(user_id)
        if not user_data or not user_data.get("is_admin"):
            if main_group_id and cxp_topic_id:
                msg = await context.bot.send_message(
                    chat_id=main_group_id,
                    message_thread_id=cxp_topic_id,
                    text="❌ You do not have permission to use this command."
                )
            return

    if not main_group_id:
        if cxp_topic_id:
            await context.bot.send_message(chat_id=update.message.chat_id, message_thread_id=cxp_topic_id, text="❌ Main group ID not configured. Cannot sync permissions.")
        return

    await update.message.reply_text(
        "🔄 Starting permission backfill... This may take a while depending on user count. Check the console logs for progress.",
        reply_to_message_id=update.message.message_id
    )
    
    # Run the backfill in the background to avoid blocking the bot handler
    context.application.create_task(_run_syncperms_background(context.bot, main_group_id))

async def _run_syncperms_background(bot, main_group_id):
    logger.info("Starting background permission sync...")
    if not db.pool:
        logger.warning("DB pool not initialized, skipping sync.")
        return

    # Fetch all users
    try:
        async with db.pool.acquire() as conn:
            users = await conn.fetch("SELECT user_id, cxp FROM users")
    except Exception as e:
        logger.error("Database error while fetching users for sync: %s", e)
        return

    success_count = 0
    fail_count = 0
    
    for row in users:
        user_id = row["user_id"]
        cxp = row.get("cxp", 0)
        level = calculate_level(cxp)
        
        try:
            await apply_level_permissions(bot, main_group_id, user_id, level)
            success_count += 1
        except error.RetryAfter as e:
            logger.warning("Rate limit hit during permission sync for user %s. Sleeping for %s seconds", user_id, e.retry_after)
            await asyncio.sleep(e.retry_after + 1.0)
            # Try once more
            try:
                await apply_level_permissions(bot, main_group_id, user_id, level)
                success_count += 1
            except Exception as e2:
                logger.error("Failed to sync permissions for user %s after retry: %s", user_id, e2)
                fail_count += 1
        except error.BadRequest as e:
            # Common errors: User is admin, user not found, user left the chat
            logger.debug("Skipping permission sync for user %s: %s", user_id, e)
            fail_count += 1
        except Exception as e:
            logger.error("Error setting permissions for user %s: %s", user_id, e)
            fail_count += 1
            
        # Standard safety delay
        await asyncio.sleep(0.1)
        
    logger.info("Finished background permission sync. Success: %s, Failed/Skipped: %s", success_count, fail_count)
