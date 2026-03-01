"""
Telegram bot that alerts group admins when '@admin' is mentioned.
"""

import logging
import os
import warnings

# Suppress Python 3.14 SyntaxWarning from anyio dependency
warnings.filterwarnings("ignore", category=SyntaxWarning, message=".*'return' in a 'finally' block.*")

from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    TypeHandler,
    filters,
    filters,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    MessageReactionHandler,
)
from telegram.constants import ParseMode
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

from database import db
from handlers.init_config import get_config_conversation_handler
from handlers.verification import welcome_new_member, verify_user
from handlers.service_cleaner import clean_service_messages
from handlers.cxp import track_message_activity, evaluate_reaction, user_stats_cmd, leaderboard_cmd

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

        main_group_id = config.get("main_group_id")

        # If no public main group is configured, or if the current chat doesn't match, ignore the mention
        if not main_group_id or chat.id != main_group_id:
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
    application.add_handler(MessageHandler(filters.Regex(r"@admin"), admin_mention))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    application.add_handler(MessageHandler(filters.StatusUpdate.ALL, clean_service_messages))
    application.add_handler(CallbackQueryHandler(verify_user, pattern=r"^verify_"))
    
    # CXP Handlers
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, track_message_activity), group=1)
    application.add_handler(MessageReactionHandler(evaluate_reaction))
    application.add_handler(CommandHandler(["me", "level", "cxp", "rank"], user_stats_cmd))
    application.add_handler(CommandHandler(["leaderboard", "leaderboards", "top"], leaderboard_cmd))

    # Start the Bot
    PORT = int(os.environ.get("PORT", "443"))
    RAILWAY_PUBLIC_DOMAIN = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    PUBLIC_DOMAIN = RAILWAY_PUBLIC_DOMAIN if RAILWAY_PUBLIC_DOMAIN else os.environ.get("PUBLIC_DOMAIN")

    # Check and manage existing webhook
    import urllib.request
    import json
    
    webhook_info_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"
    expected_webhook_url = f"https://{PUBLIC_DOMAIN}" if PUBLIC_DOMAIN else None
    
    try:
        with urllib.request.urlopen(webhook_info_url) as response:
            data = json.loads(response.read().decode())
            if data.get("ok") and data.get("result", {}).get("url"):
                current_webhook_url = data["result"]["url"]
                
                if expected_webhook_url and current_webhook_url == expected_webhook_url:
                    logger.info(f"Existing webhook already matches expected domain: {expected_webhook_url}")
                else:
                    logger.info(f"Existing webhook {current_webhook_url} does not match expected (or polling requested). Attempting to delete...")
                    
                    delete_webhook_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook"
                    with urllib.request.urlopen(delete_webhook_url) as del_response:
                        del_data = json.loads(del_response.read().decode())
                        if del_data.get("ok"):
                            logger.info("Webhook deleted successfully.")
                        else:
                            logger.warning(f"Failed to delete webhook: {del_data}")
    except Exception as e:
        logger.warning(f"Error checking/deleting webhook: {e}")

    if PUBLIC_DOMAIN:
        logger.info(
            f"Starting webhook on port {PORT} for domain {PUBLIC_DOMAIN}"
        )
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=expected_webhook_url,
            allowed_updates=Update.ALL_TYPES,
        )
    else:
        logger.info("No public domain provided. Proceeding with long polling (getUpdates).")
        application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
