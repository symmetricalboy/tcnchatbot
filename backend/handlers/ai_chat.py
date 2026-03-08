import logging
import os
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import CallbackContext
from google import genai
import html
from database import db
from handlers.cxp import enforce_cxp_topic

# Import our knowledge base and prompts
from ai_library import TOPIC_ROUTER_PROMPT, ANSWER_GENERATION_PROMPT, get_topics_content

logger = logging.getLogger(__name__)

# Initialize the Gemini Client exactly like in translation.py
api_key = os.getenv("GEMINI_API_KEY")

try:
    gemini_client = genai.Client() if api_key else None
except Exception as e:
    logger.error("Failed to initialize Gemini client in ai_chat: %s", e)
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
        logger.warning("Failed to send typing action: %s", e)


async def ask_cmd(update: Update, context: CallbackContext):
    """
    Handle the /ask command.
    Uses a two-pass Gemini approach:
    1. Identify the topic based on the user's question.
    2. Answer the user's question using the relevant injected context.
    """
    if not update.effective_user or not update.message:
        return

    # Extract the user's question
    question = " ".join(context.args) if context.args else ""

    # If there's no question, but they reply to a message, try to use that text.
    if not question and update.message.reply_to_message:
        reply = update.message.reply_to_message
        question = getattr(reply, "text", reply.caption) or ""

    if not question:
        await update.message.reply_text(
            "Please provide a question after the command, e.g., `/ask Who is the architect?`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if not gemini_client:
        await update.message.reply_text(
            "The AI agent is currently offline. (API key not configured).",
        )
        return

    config = await db.get_config()
    cxp_topic_id = config.get("cxp_topic_id") if config else None
    main_group_id = config.get("main_group_id") if config else None

    if not await enforce_cxp_topic(update, context, main_group_id, cxp_topic_id):
        return

    thread_id = update.message.message_thread_id
    chat_id = update.effective_chat.id

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

    typing_job = context.job_queue.run_repeating(
        _typing_indicator_job,
        interval=4,
        first=4,
        data={
            "chat_id": chat_id,
            "message_thread_id": action_thread_id,
        },
    )

    try:
        # Step 1: Topic Routing
        router_prompt = TOPIC_ROUTER_PROMPT.format(question=question)

        route_response = gemini_client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=router_prompt,
        )

        topic_keys = route_response.text.strip()
        logger.info(f"AI Router selected topics: {topic_keys}")

        # Pull the specialized context
        context_data = get_topics_content(topic_keys)

        # Step 2: Answer Generation
        generation_prompt = ANSWER_GENERATION_PROMPT.format(
            context=context_data, question=question
        )

        final_response = gemini_client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=generation_prompt,
        )

        answer_text = final_response.text.strip()

        # Enforce max length of 3900 characters for the AI's portion
        if len(answer_text) > 3900:
            answer_text = answer_text[:3897] + "..."

        final_message = answer_text

        await context.bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text=final_message,
            parse_mode=ParseMode.HTML,
            reply_to_message_id=update.message.message_id,
        )

    except Exception as e:
        logger.error(f"Error handling /ask command: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text="Sorry Sugar, my neural link is experiencing interference right now. Try again later.",
            reply_to_message_id=update.message.message_id,
        )
    finally:
        if typing_job:
            typing_job.schedule_removal()
