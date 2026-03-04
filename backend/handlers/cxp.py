import logging
import math
from datetime import datetime
from telegram import Update
from telegram.ext import CallbackContext

from database import db

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


async def _announce_level_up(context: CallbackContext, user, new_level: int):
    """Announce level up in the dedicated CXP topic if configured."""
    config = await db.get_config()
    if not config:
        return

    cxp_topic_id = config.get("cxp_topic_id")
    main_group_id = config.get("main_group_id")

    if cxp_topic_id and main_group_id:
        try:
            mention = f'<a href="tg://user?id={user.id}">{user.first_name}</a>'
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
    if user.username:
        await db.update_user_username(user.id, user.username)

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


async def resolve_username(
    input_str: str, update: Update, context: CallbackContext
) -> tuple[int | None, str | None]:
    """
    Centralized function to resolve a username or text_mention to a User ID and Name.
    Strictly relies on Telegram's API and message entities.
    Returns (user_id, user_name).
    """
    if not input_str and not update.message:
        return None, None

    # 1. Check for explicit text_mentions (links without @ usernames)
    if update.message:
        entities = update.message.parse_entities(None)
        for ent, text in entities.items():
            if ent.type == "text_mention" and ent.user:
                return ent.user.id, ent.user.first_name

    if not input_str:
        return None, None

    # 2. Extract potential pure username
    username_str = input_str
    if update.message and update.message.text:
        # If it's a mention entity, extract just the mention text
        entities = update.message.parse_entities(["mention"])
        for ent, text in entities.items():
            username_str = text
            break

    # Format to ensure @
    if not username_str.startswith("@"):
        username_str = f"@{username_str}"

    # 3. Hit the Telegram API directly
    try:
        chat = await context.bot.get_chat(username_str)
        return chat.id, chat.title or chat.first_name or username_str
    except Exception as e:
        # 4. Fallback to DB Tracker
        # Database looks up by raw string without the @
        clean_name = username_str.lstrip("@")
        user_row = await db.get_user_by_username(clean_name)
        if user_row:
            return user_row.get("user_id"), username_str

        logger.warning(
            "Failed to resolve username %s via API and DB: %s", username_str, e
        )
        return None, None


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

    if (
        not update.message
        or not update.message.message_thread_id
        or update.message.message_thread_id != cxp_topic_id
    ):
        return

    if getattr(update.effective_user, "is_bot", True) and update.message.sender_chat:
        target_id = update.message.sender_chat.id
        target_name = (
            update.message.sender_chat.title
            or update.message.sender_chat.username
            or f"Channel {target_id}"
        )
    else:
        target_id = update.effective_user.id
        target_name = update.effective_user.first_name

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
        arg_str = context.args[0]
        resolved_id, resolved_name = await resolve_username(arg_str, update, context)

        if resolved_id:
            target_id = resolved_id
            target_name = resolved_name
        else:
            await update.message.reply_text(
                "Could not resolve a target user from the arguments provided via Telegram. Please ensure the @username is correct."
            )
            return

    user_data = await db.get_user(target_id)
    if not user_data:
        await update.message.reply_text("No stats found for that user.")
        return

    cxp = user_data.get("cxp", 0)
    level = calculate_level(cxp)
    rank = await db.get_user_rank(cxp)

    next_level_cxp = 250 * (level + 1) * level

    # Try our best to get a name if target_name is missing, which happens for channels
    if not target_name:
        try:
            chat = await context.bot.get_chat(target_id)
            target_name = chat.title or chat.first_name or f"Channel {target_id}"
        except Exception:
            target_name = f"User/Channel {target_id}"

    msg = (
        f"📊 **Statistics for {target_name}**\n\n"
        f"🏆 **Rank:** #{rank}\n"
        f"🔰 **Level:** {level}\n"
        f"✨ **CXP:** {cxp:,} / {next_level_cxp:,}"
    )

    await update.message.reply_text(msg, parse_mode="Markdown")


async def leaderboard_cmd(update: Update, context: CallbackContext):
    """Handler for /leaderboard. Shows top 10, skipping admins."""
    config = await db.get_config()
    cxp_topic_id = config.get("cxp_topic_id") if config else None
    main_group_id = config.get("main_group_id") if config else None

    if (
        not update.message
        or not update.message.message_thread_id
        or update.message.message_thread_id != cxp_topic_id
    ):
        return

    # Fetch a wider net in case many are admins
    top_candidates = await db.get_leaderboard(limit=50)
    if not top_candidates:
        await update.message.reply_text("The leaderboard is currently empty!")
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
            except Exception:
                pass

        if not is_admin:
            actual_top_10.append(row)

    if not actual_top_10:
        await update.message.reply_text("No non-admin users found for the leaderboard.")
        return

    msg = "🏆 **Global Leaderboard (Top 10)** 🏆\n\n"

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, row in enumerate(actual_top_10):
        u_id = row.get("user_id")
        cxp = row.get("cxp", 0)
        level = calculate_level(cxp)
        medal = medals[i] if i < len(medals) else f"#{i+1}"

        name = f"User {u_id}"
        try:
            chat = await context.bot.get_chat(u_id)
            name = chat.title or chat.first_name or f"Channel {u_id}"
        except Exception:
            pass

        msg += f"{medal} **{name}** — Level {level} ({cxp:,} CXP)\n"

    await update.message.reply_text(msg, parse_mode="Markdown")


async def cxp_help_cmd(update: Update, context: CallbackContext):
    """Handler for /help to show CXP info."""
    config = await db.get_config()
    cxp_topic_id = config.get("cxp_topic_id") if config else None

    if (
        not update.message
        or not update.message.message_thread_id
        or update.message.message_thread_id != cxp_topic_id
    ):
        return

    msg = (
        "🌟 **CXP & Leveling System Help** 🌟\n\n"
        "**Earning CXP:**\n"
        "• **Messages**: Earn `50 CXP` for chatting (limit 1 per minute).\n"
        "• **Reactions**: Earn or lose CXP when others react to your messages.\n"
        "  Positive emojis (thumbs up, hearts, fire, etc.) give `+50 CXP`.\n"
        "  Negative emojis (thumbs down, anger, stop, etc.) give `-50 CXP`.\n"
        "• **Influence**: Higher level users multiply the CXP of their reactions! Your vote carries more weight as you rank up.\n\n"
        "**Commands:**\n"
        "• `/level` — View your own stats and rank. Use `/level @username` to check someone else.\n"
        "• `/leaderboard` — View the top 10 CXP leaders (Admins excluded).\n"
        "• `/help` — View this message."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def get_id_cmd(update: Update, context: CallbackContext):
    """Test command to explicitly check API/DB username resolution and reply parsing. (was /id, now /checkid)"""
    if not update.effective_user or not update.message:
        return

    if (
        getattr(update.effective_user, "is_bot", True)
        and not update.message.sender_chat
    ):
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
            await update.message.reply_text(
                f"Reply Resolution Success!\nName: {target_user.first_name}\nID: `{target_user.id}`",
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

    # Check admin privileges
    is_admin = False
    actor_data = await db.get_user(actor_id)
    if actor_data and actor_data.get("is_admin", False):
        is_admin = True

    if not is_admin:
        try:
            member = await context.bot.get_chat_member(main_group_id, actor_id)
            if member.status in ("administrator", "creator"):
                is_admin = True
        except Exception:
            pass

    if not is_admin:
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

    # Parse args to support varying formats: `/give 1000 @usr`, `/give @usr 1000`
    arg_str = None
    for arg in args:
        try:
            delta_cxp = int(arg)
        except ValueError:
            pass

        if arg.startswith("@") and arg_str is None:
            arg_str = arg

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
    for arg in args:
        lower_arg = arg.lower()
        if lower_arg in ["true", "1", "yes", "t"]:
            is_admin_flag = True
        elif lower_arg in ["false", "0", "no", "f", "remove"]:
            is_admin_flag = False

        if arg.startswith("@") and arg_str is None:
            arg_str = arg

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
    """Member command: /steal [@username/reply]. Steal 100 CXP with 1-hour cooldown."""
    if not update.effective_user or not update.message:
        return

    # Check if we are in the main group
    config = await db.get_config()
    main_group_id = config.get("main_group_id") if config else None
    if not main_group_id or update.effective_chat.id != main_group_id:
        return

    user_id = update.effective_user.id
    user_name = update.effective_user.first_name

    # 1. Resolve target
    target_id = None
    target_name = None

    # Try reply target
    if update.message.reply_to_message and not getattr(
        update.message, "is_automatic_forward", False
    ):
        if not (
            update.message.is_topic_message
            and update.message.reply_to_message.message_id
            == update.message.message_thread_id
        ):
            if update.message.reply_to_message.sender_chat:
                target_id = update.message.reply_to_message.sender_chat.id
                target_name = (
                    update.message.reply_to_message.sender_chat.title
                    or update.message.reply_to_message.sender_chat.username
                )
            elif (
                update.message.reply_to_message.from_user
                and not update.message.reply_to_message.from_user.is_bot
            ):
                target_id = update.message.reply_to_message.from_user.id
                target_name = update.message.reply_to_message.from_user.first_name

    # Try @username argument
    if context.args:
        arg_str = context.args[0]
        resolved_id, resolved_name = await resolve_username(arg_str, update, context)
        if resolved_id:
            target_id = resolved_id
            target_name = resolved_name

    if not target_id:
        await update.message.reply_text(
            "Please provide a @username or reply to their message to steal CXP."
        )
        return

    if target_id == user_id:
        await update.message.reply_text("You cannot steal from yourself!")
        return

    # 2. Check Cooldown
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
            await update.message.reply_text(
                f"⏳ You are on cooldown! Please wait `{minutes}m {seconds}s` before trying again.",
                parse_mode="Markdown",
            )
            return

    # 3. Perform Steal
    target_data = await db.get_user(target_id)
    if not target_data:
        await update.message.reply_text("Target user not found in the system.")
        return

    STEAL_AMOUNT = 100

    # Deduct from target
    await db.update_user_cxp(target_id, -STEAL_AMOUNT)
    # Add to sender
    await db.update_user_cxp(user_id, STEAL_AMOUNT)
    # Update cooldown
    await db.update_user_steal_time(user_id)

    await update.message.reply_text(
        f"🎯 **Success!** You stole `{STEAL_AMOUNT}` CXP from **{target_name}**!",
        parse_mode="Markdown",
    )
