import logging
import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ChatAction
from telegram.ext import CallbackContext
from google import genai
from database import db

logger = logging.getLogger(__name__)

# Initialize the Gemini Client
# It automatically picks up the GEMINI_API_KEY environment variable if it's set.
api_key = os.getenv("GEMINI_API_KEY")

try:
    gemini_client = genai.Client() if api_key else None
except Exception as e:
    logger.error(f"Failed to initialize Gemini client: {e}")
    gemini_client = None


async def _typing_indicator_job(context: CallbackContext):
    """Job to continually send typing indicator."""
    chat_id = context.job.data.get("chat_id")
    message_thread_id = context.job.data.get("message_thread_id")

    try:
        await context.bot.send_chat_action(
            chat_id=chat_id,
            action=ChatAction.TYPING,
            message_thread_id=message_thread_id,
        )
    except Exception as e:
        logger.warning(f"Failed to send typing action: {e}")


async def _translate_message(
    update: Update, context: CallbackContext, target_language: str, command_name: str
):
    """Generic function to handle translating a message to a target language."""
    if not update.effective_user or not update.message:
        return

    if (
        getattr(update.effective_user, "is_bot", True)
        and not update.message.sender_chat
    ):
        return

    # To translate, the user can either reply to a message with the command
    # or pass the text as arguments: /en Hello world
    text_to_translate = ""

    if context.args:
        text_to_translate = " ".join(context.args)
    elif update.message.reply_to_message:
        reply = update.message.reply_to_message

        # Determine if it's a topic root message
        # In forum topics, the first message (root) is often treated as a reply target if no specific message is selected
        is_topic_root = False
        if update.effective_chat and update.effective_chat.is_forum:
            # If thread_id is None, it's the General topic (root is usually msg id 1)
            # If thread_id is set, it's a specific topic (root is the thread_id)
            thread_id = update.message.message_thread_id
            if (thread_id is None and reply.message_id == 1) or (
                reply.message_id == thread_id
            ):
                is_topic_root = True

        if not is_topic_root and not getattr(
            update.message, "is_automatic_forward", False
        ):
            text_to_translate = reply.text or reply.caption or ""

    if not text_to_translate:
        await update.message.reply_text(
            f"Please reply to a message with `/{command_name}` or type `/{command_name} <text>` to translate.",
            parse_mode="Markdown",
        )
        return

    if not gemini_client:
        await update.message.reply_text(
            "Translation is currently unavailable (API key not configured)."
        )
        return

    # Figure out the correct topic/thread ID.
    # In Telegram, the "General" topic (the first one) often lacks a message_thread_id
    # but needs to be explicitly targeted with ID 1 to avoid showing the indicator globally.
    thread_id = update.message.message_thread_id
    if update.effective_chat and update.effective_chat.is_forum and thread_id is None:
        thread_id = 1

    # Setup repeating typing indicator job
    typing_job = None
    if update.effective_chat:
        # Start immediately
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING,
            message_thread_id=thread_id,
        )

        # Then, schedule every 4 seconds (Telegram timeout is 5 seconds)
        typing_job = context.job_queue.run_repeating(
            _typing_indicator_job,
            interval=4,
            first=4,
            data={
                "chat_id": update.effective_chat.id,
                "message_thread_id": thread_id,
            },
        )

    try:
        # Prompt the Gemini model
        prompt = f"Translate this message into {target_language}. Respond ONLY with the translated text, no additional commentary:\n\n{text_to_translate}"

        response = gemini_client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=prompt,
        )

        translated_text = response.text.strip()

        if translated_text:
            await update.message.reply_text(
                translated_text, reply_to_message_id=update.message.message_id
            )
        else:
            await update.message.reply_text("Failed to generate translation.")

    except Exception as e:
        logger.error(f"Error during translation to {target_language}: {e}")
        await update.message.reply_text(
            "An error occurred while trying to translate the message."
        )
    finally:
        if typing_job:
            typing_job.schedule_removal()


# Feature wrappers
async def translate_en_cmd(update: Update, context: CallbackContext):
    await _translate_message(update, context, "English", "en")


async def translate_pt_cmd(update: Update, context: CallbackContext):
    await _translate_message(update, context, "Portuguese", "pt")


async def translate_id_cmd(update: Update, context: CallbackContext):
    await _translate_message(update, context, "Indonesian", "id")


async def translate_ru_cmd(update: Update, context: CallbackContext):
    await _translate_message(update, context, "Russian", "ru")


async def translate_es_cmd(update: Update, context: CallbackContext):
    await _translate_message(update, context, "Spanish", "es")


async def translate_fa_cmd(update: Update, context: CallbackContext):
    await _translate_message(update, context, "Persian", "fa")


async def translate_tr_cmd(update: Update, context: CallbackContext):
    await _translate_message(update, context, "Turkish", "tr")


async def translate_interactive_cmd(update: Update, context: CallbackContext):
    """Handler for the /translate command providing an interactive inline keyboard."""
    if not update.effective_user or not update.message:
        return

    # Must be a reply
    reply = update.message.reply_to_message
    if not reply:
        await update.message.reply_text(
            "Please reply to a message with `/translate` to choose a language.",
            parse_mode="Markdown",
        )
        return

    # Check for extra arguments (should be none)
    if context.args:
        await update.message.reply_text(
            "The `/translate` command only works as a reply with no extra text. For quick translation with text, use explicit language commands like `/en`.",
            parse_mode="Markdown",
        )
        return

    # Ensure valid message to translate
    is_topic_root = False
    if update.effective_chat and update.effective_chat.is_forum:
        thread_id = update.message.message_thread_id
        if (thread_id is None and reply.message_id == 1) or (
            reply.message_id == thread_id
        ):
            is_topic_root = True

    if is_topic_root or getattr(update.message, "is_automatic_forward", False):
        await update.message.reply_text("Cannot translate this type of message.")
        return

    text_to_translate = reply.text or reply.caption or ""
    if not text_to_translate:
        await update.message.reply_text("The replied message does not contain text.")
        return

    # Store the original text in DB to retrieve it during callback
    chat_id = update.effective_chat.id
    message_id = reply.message_id
    await db.save_original_translation_text(chat_id, message_id, text_to_translate)

    # Build Keyboard (3 per line)
    # Callback data format: tr_{chat_id}_{message_id}_{lang}
    keyboard = [
        [
            InlineKeyboardButton(
                "🇺🇸 [EN]", callback_data=f"tr_{chat_id}_{message_id}_en"
            ),
            InlineKeyboardButton(
                "🇲🇽 [ES]", callback_data=f"tr_{chat_id}_{message_id}_es"
            ),
            InlineKeyboardButton(
                "🇫🇷 [FR]", callback_data=f"tr_{chat_id}_{message_id}_fr"
            ),
        ],
        [
            InlineKeyboardButton(
                "🇵🇹 [PT]", callback_data=f"tr_{chat_id}_{message_id}_pt"
            ),
            InlineKeyboardButton(
                "🇮🇩 [ID]", callback_data=f"tr_{chat_id}_{message_id}_id"
            ),
            InlineKeyboardButton(
                "🇮🇷 [FA]", callback_data=f"tr_{chat_id}_{message_id}_fa"
            ),
        ],
        [
            InlineKeyboardButton(
                "🇷🇺 [RU]", callback_data=f"tr_{chat_id}_{message_id}_ru"
            ),
            InlineKeyboardButton(
                "🇺🇦 [UK]", callback_data=f"tr_{chat_id}_{message_id}_uk"
            ),
            InlineKeyboardButton(
                "🇹🇷 [TR]", callback_data=f"tr_{chat_id}_{message_id}_tr"
            ),
        ],
    ]

    await update.message.reply_text(
        "Select a language to translate to:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        reply_to_message_id=reply.message_id,
    )


async def translate_callback(update: Update, context: CallbackContext):
    """Handle callback button presses from the interactive /translate keyboard."""
    query = update.callback_query

    if not query.data.startswith("tr_"):
        return

    # Parse tr_{chat_id}_{message_id}_{lang}
    parts = query.data.split("_")
    if len(parts) != 4:
        await query.answer("Invalid callback data.", show_alert=True)
        return

    chat_id = int(parts[1])
    message_id = int(parts[2])
    lang_code = parts[3]

    # Map lang_code to full name for Gemini prompt
    lang_map = {
        "en": "English",
        "es": "Spanish",
        "fr": "French",
        "pt": "Portuguese",
        "id": "Indonesian",
        "fa": "Persian",
        "ru": "Russian",
        "uk": "Ukrainian",
        "tr": "Turkish",
    }

    target_language = lang_map.get(lang_code)
    if not target_language:
        await query.answer("Unsupported language.", show_alert=True)
        return

    # Check cache first
    cached_text = await db.get_translation(chat_id, message_id, lang_code)
    if cached_text:
        # Show alert. Telegram cuts it at ~200 chars.
        display_text = cached_text
        if len(display_text) > 200:
            display_text = display_text[:197] + "..."
        await query.answer(display_text, show_alert=True)
        return

    # Load original text to translate
    original_text = await db.get_translation_original_text(chat_id, message_id)
    if not original_text:
        await query.answer(
            "Could not find the original message to translate. It may have expired.",
            show_alert=True,
        )
        return

    if not gemini_client:
        await query.answer(
            "Translation is currently unavailable (API key not configured).",
            show_alert=True,
        )
        return

    # We do NOT answer the query yet! Let the loading spinner spin.
    try:
        prompt = f"Translate this message into {target_language}. Respond ONLY with the translated text, no additional commentary:\n\n{original_text}"

        response = gemini_client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=prompt,
        )

        translated_text = response.text.strip()

        if translated_text:
            # Cache the result
            await db.save_translation(chat_id, message_id, lang_code, translated_text)

            # Show alert
            display_text = translated_text
            if len(display_text) > 200:
                display_text = display_text[:197] + "..."

            await query.answer(display_text, show_alert=True)
        else:
            await query.answer("Failed to generate translation.", show_alert=True)

    except Exception as e:
        logger.error(
            f"Error during interactive translation callback to {target_language}: {e}"
        )
        await query.answer(
            "An error occurred while generating the translation.", show_alert=True
        )
