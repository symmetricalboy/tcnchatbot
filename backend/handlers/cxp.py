import logging
import math
import random
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import CallbackContext
import httpx

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

MESSAGE_CXP = 50
POSITIVE_REACTION_BASE = 50
NEGATIVE_REACTION_BASE = -50
RATE_LIMIT_SECONDS = 60


def calculate_level(cxp: int) -> int:
    """Calculate user level from total CXP based on inverse quadratic formula."""
    safe_cxp = max(0, cxp)
    return math.floor((1 + math.sqrt(1 + 4 * safe_cxp / 250)) / 2)


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


async def backfill_member_tags(bot):
    """Temporary function to backfill member tags for all existing users on startup."""
    logger.info("Starting CXP member tag backfill...")
    if not db.pool:
        logger.warning("DB pool not initialized, skipping backfill.")
        return

    async with db.pool.acquire() as conn:
        users = await conn.fetch("SELECT user_id, cxp FROM users")

    count = 0
    for row in users:
        user_id = row["user_id"]
        cxp = row.get("cxp", 0)
        level = calculate_level(cxp)
        if level >= 1:
            await _update_member_tag(bot, user_id, level)
            count += 1
            await asyncio.sleep(0.1)  # Add slight delay to prevent massive 429 waves

    logger.info("Finished CXP member tag backfill for %s users.", count)


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


async def track_message_activity(update: Update, context: CallbackContext):
    """Track messaging activity using an in-memory cache to prevent DB bottlenecking."""
    if not update.effective_user or not update.message:
        return

    # If the user is a bot, it could be an anonymous admin or channel
    if getattr(update.effective_user, "is_bot", True):
        # We allow messages sent on behalf of a channel or anonymous admin group
        if not update.message.sender_chat:
            return

        user_id = update.message.sender_chat.id

        # We need a fallback object to pass into _process_db_message_and_cxp
        # We can construct a simple mocked user object with id, username, first_name
        class MockUser:
            def __init__(self, chat):
                self.id = chat.id
                self.username = chat.username
                self.first_name = chat.title or chat.username or f"Channel {chat.id}"
                self.is_bot = False

        user_obj = MockUser(update.message.sender_chat)
    else:
        user_id = update.effective_user.id
        user_obj = update.effective_user

    chat_id = update.effective_chat.id

    config = await db.get_config()
    main_group_id = config.get("main_group_id") if config else None

    # Only track activity in the main group
    if chat_id != main_group_id:
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

    # We need current CXP for the DB call to check level up
    user_data = await db.get_user(user_id)
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
            user_data.get("cxp", 0),
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
                text=f"This command only works in the [CXP Command Center]({topic_link}) topic.",
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

    msg = (
        f"📊 **Statistics for {target_name}**\n\n"
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

    # Fetch a wider net in case many are admins
    top_candidates = await db.get_leaderboard(limit=50)
    if not top_candidates:
        if main_group_id and cxp_topic_id:
            await context.bot.send_message(
                chat_id=main_group_id,
                message_thread_id=cxp_topic_id,
                text="The leaderboard is currently empty!",
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

    msg = "🏆 **Global Leaderboard (Top 10)** 🏆\n\n"

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, row in enumerate(actual_top_10):
        u_id = row.get("user_id")
        cxp = row.get("cxp", 0)
        level = calculate_level(cxp)
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

        msg += f"{medal} **{name}** — Level {level} ({cxp:,} CXP)\n"

    if main_group_id and cxp_topic_id:
        await context.bot.send_message(
            chat_id=main_group_id,
            message_thread_id=cxp_topic_id,
            text=msg,
            parse_mode="Markdown",
        )


async def cxp_help_cmd(update: Update, context: CallbackContext):
    """Handler for /help to show general bot info."""
    msg = (
        "🤖 **Welcome to TCN's Chatbot** 🤖\n\n"
        "I am here to manage the community, handle translation, and track community engagement.\n\n"
        "**Features:**\n"
        "• **CXP System**: Earn Community Experience Points (CXP) by chatting and reacting to messages. As you level up, your reactions carry more weight!\n"
        "• **Leaderboards**: Compete with others and view the most active community members.\n"
        "• **Translations**: I can automatically translate messages between different languages so everyone can understand each other.\n\n"
        "**Earning CXP:**\n"
        "• **Messages**: Earn `50 CXP` for chatting (limit 1 per minute).\n"
        "• **Reactions**: Earn or lose CXP when others react to your messages.\n"
        "  Positive emojis give `+50 CXP`, negative emojis give `-50 CXP`.\n"
        "• **Influence**: Higher level users multiply the CXP of their reactions! Your vote carries more weight as you rank up.\n\n"
        "**Level Titles:**\n"
        "• **Lvl 1-4:** Script Kiddie\n"
        "• **Lvl 5-9:** Hash Cracker\n"
        "• **Lvl 10-19:** True Operator\n"
        "• **Lvl 20-29:** Dirty Phreak\n"
        "• **Lvl 30-39:** Ledger Forger\n"
        "• **Lvl 40-49:** Clean Splicer\n"
        "• **Lvl 50-59:** Whale Hunter\n"
        "• **Lvl 60+:** Zero-Day Broker\n\n"
        "To view the specific commands and how to use them, type `/commands`."
    )
    try:
        await update.message.delete()
    except Exception:
        pass

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        message_thread_id=update.message.message_thread_id,
        text=msg,
        parse_mode="Markdown",
    )


async def commands_cmd(update: Update, context: CallbackContext):
    """Handler for /commands to show CXP info."""
    msg = (
        "🌟 **User Commands** 🌟\n\n"
        "**CXP Commands (Use in the CXP topic):**\n"
        "• `/level` — View your own stats and rank. Use `/level @username` to check someone else.\n"
        "• `/leaderboard` — View the top 10 CXP leaders (Admins excluded).\n"
        "• `/steal` — Steal 25-100 CXP from a random user! 1-hour cooldown.\n\n"
        "**Translation Commands:**\n"
        "Start a message with or reply to a message with one of the following commands to translate it:\n"
        "`/en` (English), `/es` (Spanish), `/fr` (French),\n"
        "`/pt` (Portuguese), `/id` (Indonesian), `/fa` (Persian),\n"
        "`/ru` (Russian), `/uk` (Ukrainian), `/tr` (Turkish).\n"
        "You can also reply to a message with `/translate` for an interactive translation menu."
    )
    try:
        await update.message.delete()
    except Exception:
        pass

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        message_thread_id=update.message.message_thread_id,
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
            await update.message.reply_text(
                f"Reply Resolution Success!\nName: {full_name}\nID: `{target_user.id}`",
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
        await update.message.reply_text(
            f"Resolution Success!\nName: {resolved_name}\nID: `{resolved_id}`",
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
            await context.bot.send_message(
                chat_id=main_group_id,
                message_thread_id=cxp_topic_id,
                text=f"⏳ {user_name}, you are on cooldown! Please wait `{minutes}m {seconds}s` before trying again.",
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

    # Add to sender
    await db.update_user_cxp(user_id, STEAL_AMOUNT)
    user_new_data = await db.get_user(user_id)
    user_new_level = calculate_level(user_new_data.get("cxp", 0))
    if user_new_level != user_old_level:
        context.application.create_task(
            _update_member_tag(context.bot, user_id, user_new_level)
        )

    # Update cooldown
    await db.update_user_steal_time(user_id)

    await context.bot.send_message(
        chat_id=main_group_id,
        message_thread_id=cxp_topic_id,
        text=f"🎯 **{user_name}** stole `{STEAL_AMOUNT}` CXP from **{target_name}**!",
        parse_mode="Markdown",
    )
