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

MESSAGE_CXP = 100
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
            msg = f"🎉 Congratulations {mention}, you've leveled up to **Level {new_level}**! Keep it up!"
            await context.bot.send_message(
                chat_id=main_group_id,
                message_thread_id=cxp_topic_id,
                text=msg,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Failed to send level up announcement: {e}")


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
    if (
        not update.effective_user
        or getattr(update.effective_user, "is_bot", True)
        or not update.message
    ):
        return

    user_id = update.effective_user.id
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
            update.effective_user,
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
                f"Failed to resolve custom emoji {reaction.custom_emoji_id}: {e}"
            )
    return None


async def evaluate_reaction(update: Update, context: CallbackContext):
    """Parse reactions and apply Karma scaled by reactor level."""
    if not update.message_reaction:
        return

    reaction_update = update.message_reaction

    reactor_user = reaction_update.user
    if not reactor_user or reactor_user.is_bot:
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
    if author_id == reactor_user.id:
        return

    reactor_data = await db.get_user(reactor_user.id)
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
                    f"Could not fetch author {author_id} for level up announcement: {e}"
                )


async def user_stats_cmd(update: Update, context: CallbackContext):
    """Handler for /level."""
    if not update.effective_user or getattr(update.effective_user, "is_bot", True):
        return

    config = await db.get_config()
    cxp_topic_id = config.get("cxp_topic_id") if config else None

    if (
        not update.message
        or not update.message.message_thread_id
        or update.message.message_thread_id != cxp_topic_id
    ):
        return

    target_id = update.effective_user.id
    target_name = update.effective_user.first_name

    # Check for mention or text_mention
    if context.args:
        # First check text_mentions
        entities = update.message.parse_entities(None)

        for ent, text in entities.items():
            if ent.type == "text_mention" and ent.user:
                target_id = ent.user.id
                target_name = ent.user.first_name
                break
            elif ent.type == "mention":
                # Regular @username mentions
                # Try live API resolution first
                try:
                    chat = await context.bot.get_chat(text)
                    target_id = chat.id
                    target_name = chat.first_name or text
                    break
                except Exception:
                    await update.message.reply_text(
                        "Could not resolve that @username via Telegram. Please ensure it is correct."
                    )
                    return

        # Fallback if no entities were resolved to a different user, but an arg was provided
        if target_id == update.effective_user.id and context.args:
            arg = context.args[0]
            if arg.startswith("@"):
                try:
                    chat = await context.bot.get_chat(arg)
                    target_id = chat.id
                    target_name = chat.first_name or arg
                except Exception:
                    await update.message.reply_text(
                        "Could not resolve that @username via Telegram. Please ensure it is correct."
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
        is_admin = False
        if main_group_id:
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
            name = chat.first_name
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
        "• **Messages**: Earn `100 CXP` for chatting (limit 1 per minute).\n"
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


async def give_cxp_cmd(update: Update, context: CallbackContext):
    """Admin only: /give <val> [@username/reply]. Grant or remove CXP."""
    if (
        not update.effective_user
        or getattr(update.effective_user, "is_bot", True)
        or not update.message
    ):
        return

    config = await db.get_config()
    main_group_id = config.get("main_group_id") if config else None

    # Must be in main group
    if not main_group_id or update.effective_chat.id != main_group_id:
        return

    # Check admin privileges
    try:
        member = await context.bot.get_chat_member(
            main_group_id, update.effective_user.id
        )
        if member.status not in ("administrator", "creator"):
            return
    except Exception:
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
    if update.message.reply_to_message and getattr(
        update.message.reply_to_message.from_user, "id", None
    ):
        target_id = update.message.reply_to_message.from_user.id
        target_name = update.message.reply_to_message.from_user.first_name
        if args:
            try:
                delta_cxp = int(args[0])
            except ValueError:
                pass

    # Parse args if reply didn't resolve everything
    if delta_cxp is None or target_id is None:
        for arg in args:
            try:
                delta_cxp = int(arg)
            except ValueError:
                pass

        # Parse target from entities (handles @mentions properly when text_mention is available)
        entities = update.message.parse_entities(None)

        # In telegram-python-bot, parse_entities returns Dict[MessageEntity, str]
        for ent, text in entities.items():
            if ent.type == "text_mention" and ent.user:
                target_id = ent.user.id
                target_name = ent.user.first_name
                break
            elif ent.type == "mention":
                # Regular @username mentions
                # Try live API resolution first
                try:
                    chat = await context.bot.get_chat(text)
                    target_id = chat.id
                    target_name = chat.first_name or text
                    break
                except Exception:
                    pass
        # Fallback manual arg parsing if entity didn't match
        if target_id is None:
            for arg in args:
                if arg.startswith("@"):
                    # Try live API resolution first
                    try:
                        chat = await context.bot.get_chat(arg)
                        target_id = chat.id
                        target_name = chat.first_name or arg
                    except Exception:
                        pass
                    break

    if target_id is None:
        await update.message.reply_text(
            "Could not resolve the target user. Please ensure the @username is correct or reply to their message."
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
