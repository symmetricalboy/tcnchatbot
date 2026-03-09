import logging
import os
from telegram import Update
from telegram.constants import ParseMode, ChatAction
from telegram.ext import CallbackContext
from google import genai
from datetime import datetime, timezone
import html

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

    target = " ".join(context.args).strip().lower() if context.args else ""

    # Check for empty target or game-related aliases for Libertad City
    libertad_aliases = [
        "",
        "libertad",
        "libertad city",
        "in game",
        "game",
        "tcn",
        "the clean network",
        "clean network",
        "zone 7",
        "utc",
    ]

    if target in libertad_aliases:
        target_location = "Libertad City (UTC)"
        is_libertad = True
    else:
        target_location = target
        is_libertad = False

    target_name = None
    # Check if target is a username (only if it's not a Libertad alias)
    if not is_libertad and target.startswith("@"):
        username = target.lstrip("@")
        user = await db.get_user_by_username(username)
        if user and user.get("location"):
            target_location = user["location"]
            target_name = (
                user.get("display_name") or f"@{user.get('username') or username}"
            )
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

        prompt_addition = ""
        if is_libertad:
            prompt_addition = "The requested location is Libertad City, the fictional cyberpunk setting of the game The Clean Network. It runs on UTC time."

        format_instructions = ""
        if target_name:
            format_instructions = f"""
        You MUST format your response EXACTLY as follows, using ONLY these HTML tags and NO markdown:
        {html.escape(target_name)}
        <b>[Resolved Location Name]</b>
        [Day of week], [Month] [Day][Ordinal Suffix] - [Time in 12-hour format with AM/PM]
        
        Example:
        {html.escape(target_name)}
        <b>Minneapolis, MN</b>
        Sunday, March 8th - 10:44PM
            """
        else:
            format_instructions = """
        You MUST format your response EXACTLY as follows, using ONLY these HTML tags and NO markdown:
        <b>[Resolved Location Name]</b>
        [Day of week], [Month] [Day][Ordinal Suffix] - [Time in 12-hour format with AM/PM]
        
        Example:
        <b>Minneapolis, MN</b>
        Sunday, March 8th - 10:44PM
            """

        prompt = f"""
        The user wants to know the current time and date in a specific location.
        The system's current UTC time is: {current_iso_time}
        The user's requested location or time zone string is: '{target_location}'
        
        {prompt_addition}
        
        CRITICAL INSTRUCTION: Calculate the exact current local time for their location. You MUST accurately account for Daylight Savings Time (DST) if it is currently in effect for that locaton on this specific date.

        {format_instructions}
        
        Do not include any greeting, title, or other text. Just output the formatted string.
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
