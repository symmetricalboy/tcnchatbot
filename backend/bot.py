"""
Telegram bot that alerts group admins when '@admin' is mentioned.
"""

import logging
import os
import warnings
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    TypeHandler,
    filters,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    MessageReactionHandler,
)
from telegram.constants import ParseMode

from database import db
from handlers.init_config import get_config_conversation_handler
from handlers.verification import welcome_new_member, verify_user
from handlers.service_cleaner import clean_service_messages
from handlers.cxp import (
    track_message_activity,
    evaluate_reaction,
    user_stats_cmd,
    leaderboard_cmd,
    cxp_help_cmd,
    give_cxp_cmd,
    get_id_cmd,
)
from handlers.translation import (
    translate_en_cmd,
    translate_pt_cmd,
    translate_id_cmd,
    translate_ru_cmd,
    translate_es_cmd,
    translate_fa_cmd,
    translate_tr_cmd,
)

# Suppress Python 3.14 SyntaxWarning from anyio dependency
warnings.filterwarnings(
    "ignore", category=SyntaxWarning, message=".*'return' in a 'finally' block.*"
)
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
    application.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member)
    )
    application.add_handler(
        MessageHandler(filters.StatusUpdate.ALL, clean_service_messages)
    )
    application.add_handler(CallbackQueryHandler(verify_user, pattern=r"^verify_"))

    # CXP Handlers
    application.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND & ~filters.StatusUpdate.ALL,
            track_message_activity,
        ),
        group=1,
    )
    application.add_handler(MessageReactionHandler(evaluate_reaction))
    application.add_handler(CommandHandler("level", user_stats_cmd))
    application.add_handler(CommandHandler("leaderboard", leaderboard_cmd))
    application.add_handler(CommandHandler("help", cxp_help_cmd))
    application.add_handler(CommandHandler("give", give_cxp_cmd))
    application.add_handler(CommandHandler("checkid", get_id_cmd))

    # Translation Handlers
    application.add_handler(CommandHandler("en", translate_en_cmd))
    application.add_handler(CommandHandler("pt", translate_pt_cmd))
    application.add_handler(CommandHandler("id", translate_id_cmd))
    application.add_handler(CommandHandler("ru", translate_ru_cmd))
    application.add_handler(CommandHandler("es", translate_es_cmd))
    application.add_handler(CommandHandler("fa", translate_fa_cmd))
    application.add_handler(CommandHandler("tr", translate_tr_cmd))

    # Start the Bot
    PORT = int(os.environ.get("PORT", "443"))
    RAILWAY_PUBLIC_DOMAIN = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    raw_public_domain = (
        RAILWAY_PUBLIC_DOMAIN
        if RAILWAY_PUBLIC_DOMAIN
        else os.environ.get("PUBLIC_DOMAIN")
    )

    PUBLIC_DOMAIN = None
    if raw_public_domain:
        # Strip scheme if user provided one manually
        PUBLIC_DOMAIN = (
            raw_public_domain.replace("https://", "").replace("http://", "").strip("/")
        )

    # We need a FastAPI application to serve the bot webhooks and our Mini App API
    from fastapi import FastAPI, Request, Response
    from fastapi.middleware.cors import CORSMiddleware
    import urllib.request
    import json
    import uvicorn
    from telegram.ext import ExtBot

    fastapi_app = FastAPI()

    # Enable CORS so the React app can call this API
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: restrict this to the frontend domain in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---------------------------------------------------------
    # API endpoints for the React Mini App
    # ---------------------------------------------------------
    @fastapi_app.get("/api/health")
    async def health_check():
        return {"status": "ok"}

    @fastapi_app.get("/api/user/{user_id}")
    async def get_user_stats(user_id: int):
        user_data = await db.get_user(user_id)
        if user_data:
            return {
                "user_id": user_data["user_id"],
                "level": user_data.get("level", 0),
                "cxp": user_data.get("cxp", 0),
            }
        return {"error": "User not found"}

    # ---------------------------------------------------------
    # Webhook and FastAPI Startup
    # ---------------------------------------------------------
    webhook_info_url = (
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"
    )
    expected_webhook_url = (
        f"https://{PUBLIC_DOMAIN}/telegram" if PUBLIC_DOMAIN else None
    )

    # We only set up the webhook route if a public domain is configured
    if PUBLIC_DOMAIN:

        @fastapi_app.post("/telegram")
        async def telegram_webhook(request: Request):
            # Process the update synchronously in the background task using process_update
            # or update_queue.put. We'll use update_queue.put as recommended.
            await application.update_queue.put(
                Update.de_json(data=await request.json(), bot=application.bot)
            )
            return Response()

    async def run_fastapi_and_bot():
        # Initialize telegram-related dependencies
        await application.initialize()
        await application.start()

        if PUBLIC_DOMAIN:
            logger.info(
                f"Starting webhook via FastAPI on port {PORT} for domain {PUBLIC_DOMAIN}"
            )
            # Ensure any existing webhook is either correct or overridden
            await application.bot.set_webhook(
                url=expected_webhook_url,
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
            )
        else:
            logger.info(
                "No public domain provided. Starting FastAPI and proceeding with long polling (getUpdates)."
            )
            # Clear webhook to ensure polling works
            await application.bot.delete_webhook(drop_pending_updates=True)
            await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

        # Run the FastAPI server concurrently
        config = uvicorn.Config(
            app=fastapi_app, host="0.0.0.0", port=PORT, log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()

        # Shutdown
        if not PUBLIC_DOMAIN:
            await application.updater.stop()
        await application.stop()
        await application.shutdown()

    import asyncio

    asyncio.run(run_fastapi_and_bot())


if __name__ == "__main__":
    main()
