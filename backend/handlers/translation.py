import logging
import os
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CallbackContext
from google import genai

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
    update: Update, context: CallbackContext, target_language: str
):
    """Generic function to handle translating a message to a target language."""
    if not update.effective_user or getattr(update.effective_user, "is_bot", True):
        return

    if not update.message:
        return

    # To translate, the user can either reply to a message with the command
    # or pass the text as arguments: /en Hello world
    text_to_translate = ""

    if update.message.reply_to_message and update.message.reply_to_message.text:
        text_to_translate = update.message.reply_to_message.text
    elif context.args:
        text_to_translate = " ".join(context.args)

    if not text_to_translate:
        await update.message.reply_text(
            f"Please reply to a message with `/{target_language[:2].lower()}` or type `/{target_language[:2].lower()} <text>` to translate.",
            parse_mode="Markdown",
        )
        return

    if not gemini_client:
        await update.message.reply_text(
            "Translation is currently unavailable (API key not configured)."
        )
        return

    # Setup repeating typing indicator job
    typing_job = None
    if update.effective_chat:
        # Start immediately
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING,
            message_thread_id=update.message.message_thread_id,
        )

        # Then, schedule every 4 seconds (Telegram timeout is 5 seconds)
        typing_job = context.job_queue.run_repeating(
            _typing_indicator_job,
            interval=4,
            first=4,
            data={
                "chat_id": update.effective_chat.id,
                "message_thread_id": update.message.message_thread_id,
            },
        )

    try:
        # Prompt the Gemini model
        prompt = f"Translate this message into {target_language}. Respond ONLY with the translated text, no additional commentary:\n\n{text_to_translate}"

        response = gemini_client.models.generate_content(
            model="gemini-3.1-pro-preview",
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
    await _translate_message(update, context, "English")


async def translate_pt_cmd(update: Update, context: CallbackContext):
    await _translate_message(update, context, "Portuguese")


async def translate_id_cmd(update: Update, context: CallbackContext):
    await _translate_message(update, context, "Indonesian")


async def translate_ru_cmd(update: Update, context: CallbackContext):
    await _translate_message(update, context, "Russian")


async def translate_es_cmd(update: Update, context: CallbackContext):
    await _translate_message(update, context, "Spanish")


async def translate_fa_cmd(update: Update, context: CallbackContext):
    await _translate_message(update, context, "Persian")


async def translate_tr_cmd(update: Update, context: CallbackContext):
    await _translate_message(update, context, "Turkish")
