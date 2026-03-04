import logging
from telegram import Update, ChatMember
from telegram.ext import CallbackContext
from database import db

logger = logging.getLogger(__name__)


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


async def is_user_admin(user_id: int, chat_id: int, context: CallbackContext) -> bool:
    """
    Robustly check if a user or channel is an admin.
    Checks:
    1. Database 'is_admin' flag.
    2. Telegram API for 'administrator' or 'creator' status.
    """
    # 1. Check Database
    user_data = await db.get_user(user_id)
    if user_data and user_data.get("is_admin", False):
        return True

    # 2. Check Telegram API
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        if member.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER):
            return True
    except Exception as e:
        logger.warning(f"Failed to check admin status for {user_id} in {chat_id}: {e}")

    return False


async def get_target(
    update: Update, context: CallbackContext
) -> tuple[int | None, str | None]:
    """Helper to resolve target from reply or mention."""
    target_id = None
    target_name = None

    # Try reply
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
                    update.message.reply_to_message.sender_chat.title or "Channel"
                )
            elif update.message.reply_to_message.from_user:
                target_id = update.message.reply_to_message.from_user.id
                target_name = update.message.reply_to_message.from_user.first_name

    # Try mention
    if not target_id and context.args:
        arg_str = context.args[0]
        res_id, res_name = await resolve_username(arg_str, update, context)
        if res_id:
            target_id = res_id
            target_name = res_name

    return target_id, target_name
