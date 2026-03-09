import logging
import os
import json
from telegram import Update
from telegram.constants import ParseMode, ChatAction
from telegram.ext import CallbackContext
from google import genai
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo
import html

from database import db

logger = logging.getLogger(__name__)

api_key = os.getenv("GEMINI_API_KEY")

try:
    gemini_client = genai.Client() if api_key else None
except Exception as e:
    logger.error("Failed to initialize Gemini client in time.py: %s", e)
    gemini_client = None


def get_ordinal_suffix(day: int) -> str:
    """Return the ordinal suffix for a given day (1-31)."""
    if 11 <= (day % 100) <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def format_time_string(location_name: str, target_name: str, tz_info: ZoneInfo) -> str:
    """Format the exact output string utilizing native python time calculations."""
    now = datetime.now(tz_info)
    day = now.day
    suffix = get_ordinal_suffix(day)

    # Format: Sunday, March 8th - 10:44PM (stripping leading zeros from hour and replacing AM/PM with uppercase)
    date_str = (
        now.strftime(f"%A, %B {day}{suffix} - %I:%M%p")
        .replace("AM", "AM")
        .replace("PM", "PM")
    )
    # Strip leading zero from the 12-hour hour:
    if " - 0" in date_str:
        date_str = date_str.replace(" - 0", " - ")

    if target_name:
        return (
            f"{html.escape(target_name)}\n"
            f"<b>{html.escape(location_name)}</b>\n"
            f"{date_str}"
        )
    else:
        return f"<b>{html.escape(location_name)}</b>\n" f"{date_str}"


async def resolve_location(location_str: str) -> dict:
    """
    Given a location string, ask Gemini to parse it into an IANA timezone string
    format and a clean display name.
    Expects JSON output: {"timezone": "America/Chicago", "location_name": "Minneapolis, MN"}
    Returns None if parsing fails.
    """
    if not gemini_client or not location_str:
        return None

    prompt = f"""
    The user provided the following location or timezone string: '{location_str}'
    
    You must resolve this into a valid IANA timezone name (e.g. "America/New_York", "Europe/London", "Asia/Tokyo") 
    and a clean, beautifully formatted location display name (e.g., "Minneapolis, MN", "Tokyo, Japan", "London, UK").
    
    Return ONLY a raw JSON object with the following exact keys:
    {{
        "timezone": "<valid IANA timezone string>",
        "location_name": "<clean display name of the location>"
    }}
    
    Do not wrap the JSON in markdown blocks. Output only the JSON payload.
    If you absolutely cannot determine a valid timezone, return an empty object {{}}.
    """

    try:
        response = gemini_client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=prompt,
        )
        data = response.text.strip()
        # Clean up in case it still added markdown blocks
        if data.startswith("```json"):
            data = data[7:]
        if data.startswith("```"):
            data = data[3:]
        if data.endswith("```"):
            data = data[:-3]

        parsed = json.loads(data.strip())
        if "timezone" in parsed and "location_name" in parsed:
            return parsed
        return None
    except Exception as e:
        logger.error(f"Failed to resolve location via Gemini: {e}")
        return None


async def settime_cmd(update: Update, context: CallbackContext):
    """
    Handle the /settime <location> command.
    """
    if not update.effective_user or not update.message:
        return

    location_input = " ".join(context.args) if context.args else ""
    if not location_input:
        await update.message.reply_text(
            "Please provide a location. Usage: `/settime <location>`\nExample: `/settime Tokyo`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    chat_id = update.effective_chat.id
    thread_id = update.message.message_thread_id

    if not gemini_client:
        await update.message.reply_text(
            "The AI agent is currently offline. (API key not configured)."
        )
        return

    try:
        await context.bot.send_chat_action(
            chat_id=chat_id,
            action=ChatAction.TYPING,
            message_thread_id=thread_id if update.effective_chat.is_forum else None,
        )
    except Exception:
        pass

    resolved = await resolve_location(location_input)

    if not resolved:
        await update.message.reply_text(
            "I couldn't figure out the standard timezone for that location. Please try being more specific, "
            "like a major city near you, or a timezone name (e.g. 'Minneapolis, MN' or 'America/Chicago')."
        )
        return

    user_id = update.effective_user.id

    # Store JSON in DB
    try:
        location_json = json.dumps(resolved)
        await db.update_user_location(user_id, location_json)
        await update.message.reply_text(
            f"✅ Success! Your location has been securely set to: <b>{html.escape(resolved['location_name'])}</b> ({html.escape(resolved['timezone'])})",
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

    target_name = None
    resolved_location = None

    if target in libertad_aliases:
        resolved_location = {"timezone": "UTC", "location_name": "Libertad City (UTC)"}
    elif target.startswith("@"):
        username = target.lstrip("@")
        user = await db.get_user_by_username(username)

        if user and user.get("location"):
            try:
                # Expecting a JSON string as generated by resolve_location in settime
                resolved_location = json.loads(user["location"])
                target_name = (
                    user.get("display_name") or f"@{user.get('username') or username}"
                )
            except json.JSONDecodeError:
                # Fallback if old plain-text location is in DB. We would need to resolve it on the fly.
                raw_location = user["location"]
                target_name = (
                    user.get("display_name") or f"@{user.get('username') or username}"
                )
                resolved_location = await resolve_location(raw_location)
        else:
            await update.message.reply_text(
                f"User @{username} has not set a location or doesn't exist.\n"
                "You can set your own location using `/settime <location>`.\n"
                "Example: `/settime Tokyo`",
                parse_mode=ParseMode.MARKDOWN,
            )
            return
    else:
        # Not a user, not an alias, so resolve the raw string entered
        resolved_location = await resolve_location(target)

    if not resolved_location:
        await update.message.reply_text(
            "I couldn't calculate the standard timezone for that location. Please try being more specific.",
        )
        return

    try:
        tz_info = ZoneInfo(resolved_location["timezone"])

        # We need to delete the user's message and send the response in the same topic thread.
        try:
            await context.bot.delete_message(
                chat_id=chat_id, message_id=original_message_id
            )
        except Exception as e:
            logger.warning("Failed to delete the original /time command message: %s", e)

        # Generate output string using standard packages
        answer_text = format_time_string(
            resolved_location["location_name"], target_name, tz_info
        )

        await context.bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text=answer_text,
            parse_mode=ParseMode.HTML,
        )

    except Exception as e:
        logger.error(
            f"Error handling /time command (timezone {resolved_location.get('timezone')}): {e}"
        )
        await context.bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text="I ran into an internal error resolving the math for that specific time zone.",
        )
