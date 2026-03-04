from telegram import Update, ChatPermissions
from telegram.ext import CallbackContext
from handlers.common import resolve_username, is_user_admin, get_target


async def mute_cmd(update: Update, context: CallbackContext):
    """Admin only: /mute [@username/reply]. Mutes the user indefinitely."""
    if not update.effective_user or not update.message:
        return

    chat_id = update.effective_chat.id
    actor_id = update.effective_user.id
    if update.message.sender_chat:
        actor_id = update.message.sender_chat.id

    if not await is_user_admin(actor_id, chat_id, context):
        return

    target_id, target_name = await get_target(update, context)
    if not target_id:
        await update.message.reply_text(
            "Please provide a @username or reply to a message to mute."
        )
        return

    try:
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target_id,
            permissions=ChatPermissions(
                can_send_messages=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False,
            ),
        )
        await update.message.reply_text(
            f"🔇 **{target_name}** has been muted.", parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to mute: {e}")


async def kick_cmd(update: Update, context: CallbackContext):
    """Admin only: /kick [@username/reply]. Removes the user (they can rejoin)."""
    if not update.effective_user or not update.message:
        return

    chat_id = update.effective_chat.id
    actor_id = update.effective_user.id
    if update.message.sender_chat:
        actor_id = update.message.sender_chat.id

    if not await is_user_admin(actor_id, chat_id, context):
        return

    target_id, target_name = await get_target(update, context)
    if not target_id:
        await update.message.reply_text(
            "Please provide a @username or reply to a message to kick."
        )
        return

    try:
        # Standard Telegram kick: ban and then immediately unban
        await context.bot.ban_chat_member(chat_id=chat_id, user_id=target_id)
        await context.bot.unban_chat_member(chat_id=chat_id, user_id=target_id)
        await update.message.reply_text(
            f"👢 **{target_name}** has been kicked.", parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to kick: {e}")


async def ban_cmd(update: Update, context: CallbackContext):
    """Admin only: /ban [@username/reply]. Permanently bans the user."""
    if not update.effective_user or not update.message:
        return

    chat_id = update.effective_chat.id
    actor_id = update.effective_user.id
    if update.message.sender_chat:
        actor_id = update.message.sender_chat.id

    if not await is_user_admin(actor_id, chat_id, context):
        return

    target_id, target_name = await get_target(update, context)
    if not target_id:
        await update.message.reply_text(
            "Please provide a @username or reply to a message to ban."
        )
        return

    try:
        await context.bot.ban_chat_member(chat_id=chat_id, user_id=target_id)
        await update.message.reply_text(
            f"🔨 **{target_name}** has been banned.", parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to ban: {e}")
