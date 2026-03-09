import logging
import os
from telegram import Update
from telegram.constants import ParseMode, ChatAction
from telegram.ext import CallbackContext
from google import genai
from datetime import datetime, timezone

from database import db

logger = logging.getLogger(__name__)

api_key = os.getenv("GEMINI_API_KEY")

try:
    gemini_client = genai.Client() if api_key else None
except Exception as e:
    logger.error("Failed to initialize Gemini client in time.py: %s", e)
    gemini_client = None


async def settime_cmd(update: Update, context: CallbackContext):
    """
    Handle the /settime <location> command.
    """
    if not update.effective_user or not update.message:
        return

    location = " ".join(context.args) if context.args else ""
    if not location:
        await update.message.reply_text(
            "Please provide a location. Usage: `/settime <location>`\nExample: `/settime Tokyo`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    user_id = update.effective_user.id

    # Store in DB
    try:
        await db.update_user_location(user_id, location)
        await update.message.reply_text(
            f"✅ Success! Your location has been securely set to: <b>{location}</b>",
            parse_mode=ParseMode.HTML,
            reply_to_message_id=update.message.message_id,
        )
    except Exception as e:
        logger.error(f"Error saving location for user {user_id}: {e}")
        await update.message.reply_text(
            "An error occurred while trying to save your location. Please try again later.",
        )


async def time_cmd(update: Update, context: CallbackContext):
    """
    Handle the /time <location | @username> command.
    """
    if not update.effective_user or not update.message:
        return

    chat_id = update.effective_chat.id
    thread_id = update.message.message_thread_id
    original_message_id = update.message.message_id

    target = " ".join(context.args) if context.args else ""
    if not target:
        await update.message.reply_text(
            "Please provide a location or a username. Usage: `/time <location>` or `/time @username`\nExample: `/time Tokyo` or `/time @M8AZnn`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    target_location = target

    # Check if target is a username
    if target.startswith("@"):
        username = target.lstrip("@")
        user = await db.get_user_by_username(username)
        if user and user.get("location"):
            target_location = user["location"]
        else:
            await update.message.reply_text(
                f"User @{username} has not set a location or doesn't exist.\n"
                "You can set your own location using `/settime <location>`.\n"
                "Example: `/settime Tokyo`",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

    if not gemini_client:
        await update.message.reply_text(
            "The AI agent is currently offline. (API key not configured).",
        )
        return

    # Start typing indicator
    action_thread_id = thread_id
    if update.effective_chat.is_forum and thread_id is None:
        action_thread_id = 1

    try:
        await context.bot.send_chat_action(
            chat_id=chat_id,
            action=ChatAction.TYPING,
            message_thread_id=action_thread_id,
        )
    except Exception:
        pass

    try:
        current_iso_time = datetime.now(timezone.utc).isoformat()

        prompt = f"""
        The user wants to know the current time and date in a specific location.
        The system's current UTC time is: {current_iso_time}
        The user's requested location or time zone string is: '{target_location}'
        
        Please figure out the location or time zone they are referring to to the best of your ability, calculate the current time there, and respond with a brief and friendly message stating the current local time and date for that location. You can be concise.
        Format your response beautifully using standard text or safe characters. Do not use markdown that isn't supported by Telegram (use simple html tags like <b> <i> if needed). Do not include a title or generic greeting, just state the location, time, and date directly.
        """

        response = gemini_client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=prompt,
        )

        answer_text = response.text.strip()

        # We need to delete the user's message and send the response in the same topic thread.
        try:
            await context.bot.delete_message(
                chat_id=chat_id, message_id=original_message_id
            )
        except Exception as e:
            logger.warning("Failed to delete the original /time command message: %s", e)

        # Ensure answer length is reasonable
        if len(answer_text) > 3900:
            answer_text = answer_text[:3897] + "..."

        await context.bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text=answer_text,
            parse_mode=ParseMode.HTML,
        )

    except Exception as e:
        logger.error(f"Error handling /time command: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text="I couldn't calculate the time for that location right now. Please try again later.",
        )
