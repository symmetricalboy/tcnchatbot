"""
Telegram bot that alerts group admins when '@admin' is mentioned.
"""

import logging
import os
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    TypeHandler,
    filters,
    TypeHandler,
    filters,
    ApplicationHandlerStop,
    CallbackQueryHandler,
)
from telegram.constants import ParseMode
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

from database import db
from handlers.config_conversation import get_config_conversation_handler

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.WARNING
)
logger = logging.getLogger(__name__)

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BOT_OWNER_ID = os.getenv("BOT_OWNER_ID")
if BOT_OWNER_ID:
    try:
        BOT_OWNER_ID = int(BOT_OWNER_ID)
    except ValueError:
        logger.error("BOT_OWNER_ID must be an integer.")
        BOT_OWNER_ID = None


async def auth_middleware(update: Update, context) -> None:
    """Global middleware to enforce owner-only access and initialization state."""
    if not update.effective_chat:
        return

    chat_type = update.effective_chat.type

    if not BOT_OWNER_ID:
        if chat_type == "private":
            if update.message:
                await update.message.reply_text(
                    "Owner ID is not configured in the bot's environment."
                )
        raise ApplicationHandlerStop()

    if (
        chat_type == "private"
        and update.effective_user
        and update.effective_user.id != BOT_OWNER_ID
    ):
        if update.message:
            await update.message.reply_text(
                "This bot does not provide any user facing functionality via direct message."
            )
        raise ApplicationHandlerStop()


async def admin_mention(update: Update, context) -> None:
    """Handle @admin mentions to notify all admins, restricted to the public topic group."""
    message_text = update.message.text.lower()
    if "@admin" in message_text:
        chat = update.effective_chat

        # Check if the bot is configured and if the current chat matches the public topic group
        config = await db.get_config()
        if not config:
            return

        topic_group_id = config.get("topic_group_id")

        # If no public topic group is configured, or if the current chat doesn't match, ignore the mention
        if not topic_group_id or chat.id != topic_group_id:
            return

        admins = await chat.get_administrators()
        admin_mentions = [
            f'<a href="tg://user?id={admin.user.id}">&#8205;</a>'
            for admin in admins
            if not admin.user.is_bot
        ]

        await update.message.reply_text(
            "<code>All group admins have been alerted!</code>\n"
            + "".join(admin_mentions),
            parse_mode=ParseMode.HTML,
            reply_to_message_id=update.message.message_id,
        )


async def start(update: Update, context) -> None:
    """Send README content and owner menu when standard start command is issued."""
    if update.effective_chat.type != "private":
        return

    keyboard = [
        [InlineKeyboardButton("⚙️ Setup Configuration", callback_data="start_config")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        "👋 Welcome to the Mod Mention Bot Owner Menu!\n\n"
        "Use the buttons below to configure the bot for your groups."
    )

    await update.message.reply_text(welcome_text, reply_markup=reply_markup)


async def post_init(application: Application) -> None:
    """Initialize resources after the bot starts."""
    await db.connect()


async def post_shutdown(application: Application) -> None:
    """Clean up resources when the bot stops."""
    await db.disconnect()


def main() -> None:
    """Start the bot."""
    # Create the Application
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Add handlers
    application.add_handler(TypeHandler(Update, auth_middleware), group=-1)

    application.add_handler(get_config_conversation_handler())
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex(r"@admin"), admin_mention))

    # Start the Bot
    PORT = int(os.environ.get("PORT", "443"))
    RAILWAY_PUBLIC_DOMAIN = os.environ.get("RAILWAY_PUBLIC_DOMAIN")

    if RAILWAY_PUBLIC_DOMAIN:
        logger.info(
            f"Starting webhook on port {PORT} for domain {RAILWAY_PUBLIC_DOMAIN}"
        )
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=f"https://{RAILWAY_PUBLIC_DOMAIN}",
            allowed_updates=Update.ALL_TYPES,
        )
    else:
        logger.info("Local environment detected. Starting long polling.")
        application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
