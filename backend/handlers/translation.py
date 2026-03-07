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
except Exception as e:  # pylint: disable=broad-except
    logger.error("Failed to initialize Gemini client: %s", e)
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
    except Exception as e:  # pylint: disable=broad-except
        logger.warning("Failed to send typing action: %s", e)


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

    command_user = update.effective_user
    command_user_name = command_user.first_name + (
        f" {command_user.last_name}" if getattr(command_user, "last_name", None) else ""
    )
    command_user_id = command_user.id

    text_to_translate = ""
    reply_target_msg = update.message.reply_to_message

    # Determine if it's a topic root message
    is_topic_root = False
    if reply_target_msg and update.effective_chat and update.effective_chat.is_forum:
        thread_id = update.message.message_thread_id
        if thread_id is None:
            thread_id = reply_target_msg.message_thread_id

        if (thread_id is None and reply_target_msg.message_id == 1) or (
            thread_id is not None and reply_target_msg.message_id == thread_id
        ):
            is_topic_root = True

    if is_topic_root:
        reply_target_msg = None

    author_name = command_user_name
    author_id = command_user_id
    should_reply_to_target = False
    target_msg_id = None

    if context.args:
        base_html = (
            getattr(update.message, "text_html", update.message.text)
            or getattr(update.message, "caption_html", update.message.caption)
            or ""
        )

        # Split off the command (e.g. "/es") and take the rest of the HTML payload
        parts = base_html.split(maxsplit=1)
        text_to_translate = parts[1] if len(parts) > 1 else ""

        if reply_target_msg:
            should_reply_to_target = True
            target_msg_id = reply_target_msg.message_id
    elif reply_target_msg:
        text_to_translate = (
            getattr(reply_target_msg, "text_html", reply_target_msg.text)
            or getattr(reply_target_msg, "caption_html", reply_target_msg.caption)
            or ""
        )
        should_reply_to_target = True
        target_msg_id = reply_target_msg.message_id

        is_chained = False
        # Check if the target message was actually sent by the bot (a previous translation)
        if getattr(reply_target_msg.from_user, "id", None) == context.bot.id:
            link = await db.get_translation_link(
                update.effective_chat.id, reply_target_msg.message_id
            )
            if link:
                is_chained = True
                target_msg_id = link["original_message_id"]
                author_id = link["author_id"]
                author_name = link["author_name"]

                # Retrieve the true original text to translate again
                original_text = await db.get_translation_original_text(
                    update.effective_chat.id, target_msg_id
                )
                if original_text:
                    text_to_translate = original_text

        if not is_chained and (
            not target_msg_id or target_msg_id == reply_target_msg.message_id
        ):
            # Normal extraction if it wasn't a bot translation chained message
            if reply_target_msg.sender_chat:
                author_id = reply_target_msg.sender_chat.id
                author_name = (
                    reply_target_msg.sender_chat.title
                    or reply_target_msg.sender_chat.username
                    or f"Channel {author_id}"
                )
            elif reply_target_msg.from_user:
                target_user = reply_target_msg.from_user
                author_name = target_user.first_name + (
                    f" {target_user.last_name}"
                    if getattr(target_user, "last_name", None)
                    else ""
                )
                author_id = target_user.id

    if not text_to_translate:
        await update.message.reply_text(
            f"Please reply to a message with `/{command_name}` or type `/{command_name} <text>` to translate.",
            parse_mode="Markdown",
        )
        return

    try:
        await update.message.delete()
    except Exception as e:  # pylint: disable=broad-except
        logger.warning("Failed to delete translation command message: %s", e)

    if not gemini_client:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            message_thread_id=update.message.message_thread_id,
            text="Translation is currently unavailable (API key not configured).",
        )
        return

    thread_id = update.message.message_thread_id
    if thread_id is None and reply_target_msg:
        thread_id = reply_target_msg.message_thread_id

    typing_job = None
    if update.effective_chat:
        action_thread_id = thread_id
        if update.effective_chat.is_forum and thread_id is None:
            action_thread_id = 1

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING,
            message_thread_id=action_thread_id,
        )
        typing_job = context.job_queue.run_repeating(
            _typing_indicator_job,
            interval=4,
            first=4,
            data={
                "chat_id": update.effective_chat.id,
                "message_thread_id": action_thread_id,
            },
        )

    try:
        prompt = f"Translate this message into {target_language}. Respond ONLY with the translated text, no additional commentary. Preserve any existing formatting and adapt it to Telegram HTML (use <b>, <i>, <a>, <code>, <pre>). Do not wrap the response in markdown code blocks:\n\n{text_to_translate}"

        response = gemini_client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=prompt,
        )

        translated_text = response.text.strip()
        # Remove markdown html formatting wrapping if gemini still adds it
        if translated_text.startswith("```html"):
            translated_text = translated_text.replace("```html", "", 1)
            if translated_text.endswith("```"):
                translated_text = translated_text[:-3]
        translated_text = translated_text.strip()

        if translated_text:
            import html

            # In Telegram HTML, < and > must be escaped if they aren't part of tags.
            # We assume Gemini outputs valid HTML tags as requested.
            safe_name = html.escape(author_name)

            # Map languages to flags for the header
            flag_map = {
                "English": "🇺🇸 [EN]",
                "Spanish": "🇲🇽 [ES]",
                "French": "🇫🇷 [FR]",
                "Portuguese": "🇵🇹 [PT]",
                "Indonesian": "🇮🇩 [ID]",
                "Persian": "🇮🇷 [FA]",
                "Russian": "🇷🇺 [RU]",
                "Ukrainian": "🇺🇦 [UK]",
                "Turkish": "🇹🇷 [TR]",
            }
            lang_header = flag_map.get(target_language, f"[{target_language}]")

            if author_id < 0:
                chat_id_str = str(author_id)
                if chat_id_str.startswith("-100"):
                    chat_id_str = chat_id_str[4:]
                mention_link = f'<b><a href="https://t.me/c/{chat_id_str}/999999999">{safe_name}</a></b>'
            else:
                mention_link = (
                    f'<b><a href="tg://user?id={author_id}">{safe_name}</a></b>'
                )

            final_message = f"<b>{lang_header}</b>\n<blockquote>{mention_link}\n{translated_text}</blockquote>"

            send_kwargs = {
                "chat_id": update.effective_chat.id,
                "message_thread_id": thread_id,
                "text": final_message,
                "parse_mode": "HTML",
            }
            if should_reply_to_target and target_msg_id:
                send_kwargs["reply_to_message_id"] = target_msg_id

            sent_msg = await context.bot.send_message(**send_kwargs)

            # Record message for CXP attribution and translation linkage
            if author_id:
                await db.record_message(
                    update.effective_chat.id, sent_msg.message_id, author_id
                )

            # If there's no target message (e.g., inline command), the bot's sent message BECOMES the root
            root_msg_id = (
                target_msg_id
                if (should_reply_to_target and target_msg_id)
                else sent_msg.message_id
            )

            if author_id and author_name:
                await db.link_translation(
                    update.effective_chat.id,
                    sent_msg.message_id,
                    root_msg_id,
                    author_id,
                    author_name,
                )

            # Unconditionally save the original text under the root ID
            # so that future recursive translations can access it.
            await db.save_original_translation_text(
                update.effective_chat.id, root_msg_id, text_to_translate
            )

            # Auto-delete the newly generated translation message after 60 seconds
            # ONLY if it was generated as a reply (not a permanent inline stand-alone).
            if should_reply_to_target:
                context.job_queue.run_once(
                    _delete_message_job,
                    60,
                    data={
                        "chat_id": sent_msg.chat_id,
                        "message_id": sent_msg.message_id,
                    },
                )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                message_thread_id=thread_id,
                text="Failed to generate translation.",
            )

    except Exception as e:  # pylint: disable=broad-except
        logger.error("Error during translation to %s: %s", target_language, e)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            message_thread_id=thread_id,
            text="An error occurred while trying to translate the message.",
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


async def translate_fr_cmd(update: Update, context: CallbackContext):
    await _translate_message(update, context, "French", "fr")


async def translate_fa_cmd(update: Update, context: CallbackContext):
    await _translate_message(update, context, "Persian", "fa")


async def translate_tr_cmd(update: Update, context: CallbackContext):
    await _translate_message(update, context, "Turkish", "tr")


async def translate_uk_cmd(update: Update, context: CallbackContext):
    await _translate_message(update, context, "Ukrainian", "uk")


async def _delete_message_job(context: CallbackContext):
    """Job to automatically delete a message."""
    chat_id = context.job.data.get("chat_id")
    message_id = context.job.data.get("message_id")
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:  # pylint: disable=broad-except
        pass


async def translate_interactive_cmd(update: Update, context: CallbackContext):
    """Handler for the /translate command providing an interactive inline keyboard."""
    if not update.effective_user or not update.message:
        return

    reply = update.message.reply_to_message

    # Determine if it's a topic root message
    is_topic_root = False
    if reply and update.effective_chat and update.effective_chat.is_forum:
        thread_id = update.message.message_thread_id
        if thread_id is None:
            thread_id = reply.message_thread_id

        if (thread_id is None and reply.message_id == 1) or (
            thread_id is not None and reply.message_id == thread_id
        ):
            is_topic_root = True

    if is_topic_root:
        reply = None

    if not reply or context.args:
        try:
            await update.message.delete()
        except Exception:  # pylint: disable=broad-except
            pass

        thread_id = update.message.message_thread_id
        if thread_id is None and update.message.reply_to_message:
            thread_id = update.message.reply_to_message.message_thread_id

        send_thread_id = thread_id
        if (
            update.effective_chat
            and update.effective_chat.is_forum
            and thread_id is None
        ):
            send_thread_id = 1

        msg = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            message_thread_id=send_thread_id,
            text=(
                "The `/translate` command only works as a reply with no extra text. "
                "Please reply to a message with `/translate` to choose a language."
            ),
            parse_mode="Markdown",
        )
        context.job_queue.run_once(
            _delete_message_job,
            60,
            data={"chat_id": msg.chat_id, "message_id": msg.message_id},
        )
        return

    # Delete command message
    try:
        await update.message.delete()
    except Exception:
        pass

    thread_id = update.message.message_thread_id
    if thread_id is None and reply:
        thread_id = reply.message_thread_id

    send_thread_id = thread_id
    if update.effective_chat and update.effective_chat.is_forum and thread_id is None:
        send_thread_id = 1

    text_to_translate = (
        getattr(reply, "text_html", reply.text)
        or getattr(reply, "caption_html", reply.caption)
        or ""
    )
    if not text_to_translate:
        msg = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            message_thread_id=send_thread_id,
            text="The replied message does not contain text.",
        )
        context.job_queue.run_once(
            _delete_message_job,
            60,
            data={"chat_id": msg.chat_id, "message_id": msg.message_id},
        )
        return

    target_msg_id = reply.message_id
    if getattr(reply.from_user, "id", None) == context.bot.id:
        link = await db.get_translation_link(update.effective_chat.id, reply.message_id)
        if link:
            target_msg_id = link["original_message_id"]

            original_text = await db.get_translation_original_text(
                update.effective_chat.id, target_msg_id
            )
            if original_text:
                text_to_translate = original_text

    # Store the original text in DB to retrieve it during callback
    chat_id = update.effective_chat.id
    message_id = target_msg_id
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

    msg = await context.bot.send_message(
        chat_id=chat_id,
        message_thread_id=thread_id,
        text="Select a language to translate to:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        reply_to_message_id=reply.message_id,
    )

    # Auto delete the menu after 1 minute
    context.job_queue.run_once(
        _delete_message_job,
        60,
        data={"chat_id": msg.chat_id, "message_id": msg.message_id},
    )


async def translate_callback(update: Update, context: CallbackContext):
    """Handle callback button presses from the interactive /translate keyboard."""
    query = update.callback_query

    if not query.data.startswith("tr_"):
        return

    # Delete the button menu message as soon as a selection is made
    try:
        await query.message.delete()
    except Exception:
        pass

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

    # Extract original author info for the header
    target_msg = query.message.reply_to_message
    if target_msg:
        if getattr(target_msg.from_user, "id", None) == context.bot.id:
            link = await db.get_translation_link(chat_id, target_msg.message_id)
            if link:
                author_id = link["author_id"]
                author_name = link["author_name"]
            else:
                author_id = context.bot.id
                author_name = context.bot.first_name
        elif target_msg.sender_chat:
            author_id = target_msg.sender_chat.id
            author_name = (
                target_msg.sender_chat.title
                or target_msg.sender_chat.username
                or f"Channel {author_id}"
            )
        elif target_msg.from_user:
            author_id = target_msg.from_user.id
            author_name = target_msg.from_user.first_name + (
                f" {target_msg.from_user.last_name}"
                if target_msg.from_user.last_name
                else ""
            )
        else:
            author_id = 0
            author_name = "User"
    else:
        author_id = 0
        author_name = "User"

    thread_id = query.message.message_thread_id
    if thread_id is None and target_msg:
        thread_id = target_msg.message_thread_id

    # Check cache first
    cached_text = await db.get_translation(chat_id, message_id, lang_code)

    import html

    safe_name = html.escape(author_name)
    if author_id < 0:
        chat_id_str = str(author_id)
        if chat_id_str.startswith("-100"):
            chat_id_str = chat_id_str[4:]
        mention_link = (
            f'<b><a href="https://t.me/c/{chat_id_str}/999999999">{safe_name}</a></b>'
        )
    else:
        mention_link = f'<b><a href="tg://user?id={author_id}">{safe_name}</a></b>'

    # Map languages to flags for the header
    flag_map = {
        "English": "🇺🇸 [EN]",
        "Spanish": "🇲🇽 [ES]",
        "French": "🇫🇷 [FR]",
        "Portuguese": "🇵🇹 [PT]",
        "Indonesian": "🇮🇩 [ID]",
        "Persian": "🇮🇷 [FA]",
        "Russian": "🇷🇺 [RU]",
        "Ukrainian": "🇺🇦 [UK]",
        "Turkish": "🇹🇷 [TR]",
    }
    lang_header = flag_map.get(target_language, f"[{target_language}]")

    if cached_text:
        final_message = f"<b>{lang_header}</b>\n<blockquote>{mention_link}\n{cached_text}</blockquote>"
        sent_msg = await context.bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text=final_message,
            parse_mode="HTML",
            reply_to_message_id=message_id,
        )
        if author_id:
            await db.record_message(chat_id, sent_msg.message_id, author_id)
        if author_name and author_id:
            await db.link_translation(
                chat_id, sent_msg.message_id, message_id, author_id, author_name
            )
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

    typing_job = None
    if update.effective_chat:
        action_thread_id = thread_id
        if update.effective_chat.is_forum and thread_id is None:
            action_thread_id = 1

        try:
            await context.bot.send_chat_action(
                chat_id=chat_id,
                action=ChatAction.TYPING,
                message_thread_id=action_thread_id,
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("Initial typing indicator failed: %s", e)

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
        prompt = f"Translate this message into {target_language}. Respond ONLY with the translated text, no additional commentary. Preserve any existing formatting and adapt it to Telegram HTML (use <b>, <i>, <a>, <code>, <pre>). Do not wrap the response in markdown code blocks:\n\n{original_text}"

        response = gemini_client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=prompt,
        )

        translated_text = response.text.strip()
        if translated_text.startswith("```html"):
            translated_text = translated_text.replace("```html", "", 1)
            if translated_text.endswith("```"):
                translated_text = translated_text[:-3]
        translated_text = translated_text.strip()

        if translated_text:
            # Cache the result
            await db.save_translation(chat_id, message_id, lang_code, translated_text)

            final_message = f"<b>{lang_header}</b>\n<blockquote>{mention_link}\n{translated_text}</blockquote>"
            sent_msg = await context.bot.send_message(
                chat_id=chat_id,
                message_thread_id=thread_id,
                text=final_message,
                parse_mode="HTML",
                reply_to_message_id=message_id,
            )

            # Target message ID is the message being replied to (message_id = target_msg.message_id)
            # Or the linked root ID if it was bot authored.
            root_msg_id = message_id
            if getattr(target_msg.from_user, "id", None) == context.bot.id:
                link = await db.get_translation_link(chat_id, message_id)
                if link:
                    root_msg_id = link["original_message_id"]

            if author_id:
                await db.record_message(chat_id, sent_msg.message_id, author_id)
            if author_name and author_id:
                await db.link_translation(
                    chat_id, sent_msg.message_id, root_msg_id, author_id, author_name
                )

            # Unconditionally save the pure original string under the root ID
            await db.save_original_translation_text(chat_id, root_msg_id, original_text)

            # Auto-delete the newly generated translation message after 60 seconds
            # since interactive callbacks are always executed as replies.
            context.job_queue.run_once(
                _delete_message_job,
                60,
                data={"chat_id": sent_msg.chat_id, "message_id": sent_msg.message_id},
            )
        else:
            await query.answer("Failed to generate translation.", show_alert=True)

    except Exception as e:  # pylint: disable=broad-except
        logger.error(
            "Error during interactive translation callback to %s: %s",
            target_language,
            e,
        )
        await query.answer(
            "An error occurred while generating the translation.", show_alert=True
        )
    finally:
        if typing_job:
            typing_job.schedule_removal()
