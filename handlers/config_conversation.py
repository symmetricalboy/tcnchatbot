import logging
from telegram import Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    MessageHandler,
    ConversationHandler,
    CallbackContext,
    CallbackQueryHandler,
    filters,
)

from database import db

logger = logging.getLogger(__name__)

# Define conversation states
TOPIC_GROUP, PUBLIC_CHANNEL, ADMIN_CHANNEL = range(3)


async def _resolve_chat_id(input_str: str, context: CallbackContext) -> int | None:
    """Try to resolve a numeric string or a Telegram username to a chat ID."""
    if not input_str:
        return None

    try:
        # If it's pure numbers or negative numbers, it's already an ID
        return int(input_str)
    except ValueError:
        pass

    # If it's a username, ensure it has @ and try to fetch it
    username = input_str if input_str.startswith("@") else f"@{input_str}"

    try:
        chat = await context.bot.get_chat(username)
        return chat.id
    except Exception as e:
        logger.error(f"Failed to resolve username {username}: {e}")
        return None


async def config_start(update: Update, context: CallbackContext) -> int:
    """Start the configuration conversation from an inline button."""
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "⚙️ **Owner Configuration Menu**\n\n"
        "Let's set up the required group and channels. First, please send me the ID "
        "or username (e.g., `@mygroup`) of your **1 public topic group**.\n\n"
        "Note: You must add me to this group and give me ALL permissions (except 'Remain Anonymous').\n\n"
        "Please send the Group ID or username now (or type /cancel to abort):",
        parse_mode="Markdown",
    )
    return TOPIC_GROUP


async def get_topic_group(update: Update, context: CallbackContext) -> int:
    """Handle topic group input and ask for public channel."""
    group_input = update.message.text.strip()
    group_id = await _resolve_chat_id(group_input, context)

    if group_id is None:
        await update.message.reply_text(
            "Could not resolve the group. Please provide a valid integer ID or a public @username."
        )
        return TOPIC_GROUP

    context.user_data["topic_group"] = group_id

    await update.message.reply_text(
        f"Saved Public Topic Group ID: {group_id}\n\n"
        "Next, please send me the ID or username of your **1 public channel**.\n\n"
        "Note: You must also add me to this channel as an admin with ALL permissions (except 'Remain Anonymous').\n\n"
        "Please send the Channel ID now:",
    )
    return PUBLIC_CHANNEL


async def get_public_channel(update: Update, context: CallbackContext) -> int:
    """Handle public channel input and ask for admin channel."""
    channel_input = update.message.text.strip()
    channel_id = await _resolve_chat_id(channel_input, context)

    if channel_id is None:
        await update.message.reply_text(
            "Could not resolve the channel. Please provide a valid integer ID or a public @username."
        )
        return PUBLIC_CHANNEL

    context.user_data["public_channel"] = channel_id

    await update.message.reply_text(
        f"Saved Public Channel ID: {channel_id}\n\n"
        "Finally, please send me the ID of your **1 private admin channel**.\n\n"
        "Note: I need ALL admin permissions here as well, except 'Remain Anonymous'.\n\n"
        "Please send the Admin Channel ID now:",
    )
    return ADMIN_CHANNEL


async def get_admin_channel(update: Update, context: CallbackContext) -> int:
    """Handle admin channel input, save to database, and finish."""
    admin_channel_input = update.message.text.strip()
    admin_channel_id = await _resolve_chat_id(admin_channel_input, context)

    if admin_channel_id is None:
        await update.message.reply_text(
            "Could not resolve the admin channel. Please provide a valid integer ID or a public @username."
        )
        return ADMIN_CHANNEL

    # Retrieve all inputs from context
    topic_group_id = context.user_data.get("topic_group")
    public_channel_id = context.user_data.get("public_channel")

    try:
        await db.update_config(
            public_topic_group_id=topic_group_id,
            public_channel_id=public_channel_id,
            admin_private_channel_id=admin_channel_id,
        )

        await update.message.reply_text(
            "Configuration Complete!\n\n"
            "I have updated the database with the following IDs:\n"
            f"- Public Topic Group: {topic_group_id}\n"
            f"- Public Channel: {public_channel_id}\n"
            f"- Admin Private Channel: {admin_channel_id}\n\n"
            "Please ensure I have been added to all of these with ALL permissions (except anonymous).\n"
            "Have a great day!"
        )
    except Exception as e:
        logger.error(f"Failed to update database configuraton: {e}")
        await update.message.reply_text(
            "An error occurred while saving the configuration to the database. "
            "Please check the logs and try again."
        )

    # Clear user data
    context.user_data.clear()

    return ConversationHandler.END


async def cancel(update: Update, context: CallbackContext) -> int:
    """Cancel the configuration completely."""
    await update.message.reply_text("Configuration canceled.")
    context.user_data.clear()
    return ConversationHandler.END


def get_config_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(config_start, pattern="^start_config$")],
        states={
            TOPIC_GROUP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_topic_group)
            ],
            PUBLIC_CHANNEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_public_channel)
            ],
            ADMIN_CHANNEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_admin_channel)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )
