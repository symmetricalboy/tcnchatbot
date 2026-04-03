import logging
import re
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, Message
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackContext,
    CallbackQueryHandler,
    filters,
)

from database import db
import os

logger = logging.getLogger(__name__)

BOT_OWNER_ID = os.getenv("BOT_OWNER_ID")
if BOT_OWNER_ID:
    try:
        BOT_OWNER_ID = int(BOT_OWNER_ID)
    except ValueError:
        BOT_OWNER_ID = None

# States for the drafting conversation
WAITING_FOR_POST, WAITING_FOR_BUTTONS = range(2)

async def is_user_channel_admin(user_id: int) -> bool:
    if BOT_OWNER_ID and user_id == BOT_OWNER_ID:
        return True
    user = await db.get_user(user_id)
    return user and user.get("is_channel_admin", False)

async def start_drafting(update: Update, context: CallbackContext) -> int:
    """Triggered by the 'Draft a post' button from owner/admin menu."""
    query = update.callback_query
    if query:
        await query.answer()
        message = query.message
    else:
        message = update.message

    user_id = update.effective_user.id
    if not await is_user_channel_admin(user_id):
        await message.reply_text("You do not have permission to draft channel posts.")
        return ConversationHandler.END

    text = (
        "📝 **Draft a Post for the Channel**\n\n"
        "Please send me the content of your post. This can be text, a photo, a video, or any other supported media.\n\n"
        "*(Type /cancel to abort)*"
    )
    if query:
        # Edit if it's a text message without media, but safely we just reply new to avoid media edit errors
        await message.reply_text(text, parse_mode="Markdown")
    else:
        await message.reply_text(text, parse_mode="Markdown")
        
    return WAITING_FOR_POST

async def receive_post(update: Update, context: CallbackContext) -> int:
    """Save the drafted message and ask for buttons."""
    message = update.message
    
    # Store message id and chat id to copy it later
    context.user_data['draft_message_id'] = message.message_id
    context.user_data['draft_chat_id'] = message.chat_id
    context.user_data['draft_message'] = message

    await message.reply_text(
        "✅ **Post content received.**\n\n"
        "Now, please send the buttons you want to attach to the bottom of the message. "
        "Use the following markdown format:\n\n"
        "`[button text 🎉](https://button.link/) | [button text 🎉](https://button.link/)`\n"
        "`[button text 🎉](https://button.link/)`\n\n"
        "- The pipe character `|` starts the next button on the same line.\n"
        "- A line break will start a new row of buttons.\n\n"
        "If you don't want any buttons, type `skip`.\n"
        "*(Type /cancel to abort)*",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    return WAITING_FOR_BUTTONS

def parse_buttons_markdown(text: str) -> InlineKeyboardMarkup | None:
    if text.strip().lower() == 'skip':
        return None
        
    lines = text.strip().split('\n')
    keyboard = []
    
    # Regex to strictly match [text](url)
    button_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    
    for line in lines:
        row = []
        buttons_raw = line.split('|')
        for btn_raw in buttons_raw:
            match = button_pattern.search(btn_raw.strip())
            if match:
                btn_text = match.group(1).strip()
                btn_url = match.group(2).strip()
                row.append(InlineKeyboardButton(text=btn_text, url=btn_url))
        if row:
            keyboard.append(row)
            
    if keyboard:
        return InlineKeyboardMarkup(keyboard)
    return None

async def receive_buttons(update: Update, context: CallbackContext) -> int:
    """Parse buttons, show preview, and ask for confirmation."""
    buttons_text = update.message.text
    
    reply_markup = parse_buttons_markdown(buttons_text)
    if buttons_text.strip().lower() != 'skip' and not reply_markup:
        await update.message.reply_text(
            "⚠️ Invalid format. Could not parse any buttons from your input.\n"
            "Please try again using this exact format:\n"
            "`[text](https://link) | [text](https://link)`\n\n"
            "Or type `skip` if you want no buttons, or /cancel to abort.",
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        return WAITING_FOR_BUTTONS

    context.user_data['draft_reply_markup'] = reply_markup

    # Show preview
    await update.message.reply_text("Here is a preview of your post:")
    
    try:
        preview_msg = await context.bot.copy_message(
            chat_id=update.effective_chat.id,
            from_chat_id=context.user_data['draft_chat_id'],
            message_id=context.user_data['draft_message_id'],
            reply_markup=reply_markup
        )
        
        # Confirmation buttons
        confirm_keyboard = [
            [
                InlineKeyboardButton("🔄 Start Over", callback_data="draft_start_over"),
                InlineKeyboardButton("✅ Post Message", callback_data="draft_post_msg")
            ]
        ]
        
        await update.message.reply_text(
            "What would you like to do?",
            reply_markup=InlineKeyboardMarkup(confirm_keyboard)
        )
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Failed to show preview: {e}")
        await update.message.reply_text(f"Failed to generate preview: {e}\nPlease start over.")
        context.user_data.clear()
        return ConversationHandler.END

async def send_message_with_entities(bot, chat_id, message: Message, reply_markup):
    """
    Manually sends a message instead of using copy_message.
    This preserves custom emojis when sending to a channel, as copy_message
    strips them out natively on Telegram's side.
    """
    kwargs = {
        'chat_id': chat_id,
        'reply_markup': reply_markup,
    }
    
    if message.text:
        return await bot.send_message(
            text=message.text,
            entities=message.entities,
            **kwargs
        )
    elif message.photo:
        return await bot.send_photo(
            photo=message.photo[-1].file_id,
            caption=message.caption,
            caption_entities=message.caption_entities,
            **kwargs
        )
    elif message.video:
        return await bot.send_video(
            video=message.video.file_id,
            caption=message.caption,
            caption_entities=message.caption_entities,
            **kwargs
        )
    elif message.animation:
        return await bot.send_animation(
            animation=message.animation.file_id,
            caption=message.caption,
            caption_entities=message.caption_entities,
            **kwargs
        )
    elif message.document:
        return await bot.send_document(
            document=message.document.file_id,
            caption=message.caption,
            caption_entities=message.caption_entities,
            **kwargs
        )
    elif message.audio:
        return await bot.send_audio(
            audio=message.audio.file_id,
            caption=message.caption,
            caption_entities=message.caption_entities,
            **kwargs
        )
    elif message.voice:
        return await bot.send_voice(
            voice=message.voice.file_id,
            caption=message.caption,
            caption_entities=message.caption_entities,
            **kwargs
        )
    else:
        # Fallback to copy_message for unsupported types
        return await bot.copy_message(
            chat_id=chat_id,
            from_chat_id=message.chat_id,
            message_id=message.message_id,
            reply_markup=reply_markup
        )

async def handle_post_action(update: Update, context: CallbackContext):
    """Handle Start Over or Post Message callbacks."""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    
    if action == "draft_start_over":
        context.user_data.clear()
        await query.edit_message_text("Draft cancelled. Let's start over.")
        # Trigger start drafting again
        return await start_drafting(update, context)
        
    elif action == "draft_post_msg":
        config = await db.get_config()
        if not config or not config.get("channel_id"):
            await query.edit_message_text("Error: Channel ID is not configured in the bot.")
            return

        channel_id = config.get("channel_id")
        reply_markup = context.user_data.get('draft_reply_markup')
        
        try:
            draft_message = context.user_data.get('draft_message')
            
            if draft_message:
                sent_msg = await send_message_with_entities(context.bot, channel_id, draft_message, reply_markup)
            else:
                sent_msg = await context.bot.copy_message(
                    chat_id=channel_id,
                    from_chat_id=context.user_data['draft_chat_id'],
                    message_id=context.user_data['draft_message_id'],
                    reply_markup=reply_markup
                )
                
            await query.edit_message_text("✅ Message successfully posted to the channel!")
            
            confirm_keyboard = [
                [
                    InlineKeyboardButton("⏩ Forward to Group Topic", callback_data=f"forward_post_{sent_msg.message_id}")
                ],
                [
                    InlineKeyboardButton("⏭️ Skip", callback_data=f"skip_forward_{sent_msg.message_id}")
                ]
            ]
            await query.message.reply_text(
                "Would you like to forward this post to the group's designated topic?",
                reply_markup=InlineKeyboardMarkup(confirm_keyboard)
            )
                    
        except Exception as e:
            logger.error(f"Failed to post to channel: {e}")
            await query.edit_message_text(f"❌ Failed to post message: {e}")
            
        context.user_data.clear()

async def cancel_draft(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Draft cancelled.")
    context.user_data.clear()
    return ConversationHandler.END

def get_channel_admin_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_drafting, pattern="^start_drafting$"),
            CommandHandler("draft", start_drafting)
        ],
        states={
            WAITING_FOR_POST: [MessageHandler(filters.ALL & ~filters.COMMAND, receive_post)],
            WAITING_FOR_BUTTONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_buttons)],
        },
        fallbacks=[CommandHandler("cancel", cancel_draft)],
        per_message=False,
    )

async def handle_forward_decision(update: Update, context: CallbackContext):
    """Handle the user's decision to forward a channel post or skip."""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    
    if action.startswith("skip_forward_"):
        await query.edit_message_text("⏭️ Skipped forwarding to the group topic.")
        return

    if action.startswith("forward_post_"):
        message_id = int(action.split("_")[-1])
        config = await db.get_config()
        if not config:
            await query.edit_message_text("❌ Configuration error: Could not fetch config.")
            return
            
        channel_id = config.get("channel_id")
        main_group_id = config.get("main_group_id")
        forward_topic_id = config.get("channel_forward_topic_id")
        
        if not channel_id or not main_group_id or not forward_topic_id:
            await query.edit_message_text("❌ Configuration error: Channel, Main Group, or Topic ID is not configured.")
            return
            
        try:
            await context.bot.forward_message(
                chat_id=main_group_id,
                from_chat_id=channel_id,
                message_id=message_id,
                message_thread_id=forward_topic_id
            )
            await query.edit_message_text("✅ Message successfully forwarded to the group topic!")
        except Exception as e:
            logger.error(f"Failed to manually forward drafted post: {e}")
            await query.edit_message_text(f"❌ Failed to forward message: {e}")
