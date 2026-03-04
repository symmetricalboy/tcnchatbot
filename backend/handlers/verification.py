import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from database import db

logger = logging.getLogger(__name__)


async def welcome_new_member(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle new members: delete the service message, send welcome, restrict them."""
    config = await db.get_config()
    group_id = config.get("main_group_id") if config else None

    if (
        not group_id
        or not update.effective_chat
        or update.effective_chat.id != group_id
    ):
        return

    if update.message and update.message.new_chat_members:
        # Delete the service message
        try:
            await update.message.delete()
        except:
            pass

        for new_member in update.message.new_chat_members:
            if new_member.is_bot:
                continue

            # Track username
            if new_member.username:
                await db.update_user_username(new_member.id, new_member.username)

            # Restrict user
            try:
                await context.bot.restrict_chat_member(
                    chat_id=group_id,
                    user_id=new_member.id,
                    permissions=ChatPermissions(can_send_messages=False),
                )
            except Exception as e:
                logger.error(f"Failed to restrict user: {e}")
                continue

            # Send welcome message
            keyboard = [
                [
                    InlineKeyboardButton(
                        "✅ I have read the rules!",
                        callback_data=f"verify_{new_member.id}",
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if new_member.username:
                mention = f"@{new_member.username}"
            else:
                import html

                escaped_name = html.escape(new_member.first_name)
                mention = f'<a href="tg://user?id={new_member.id}">{escaped_name}</a>'

            welcome_text = config.get("welcome_message") if config else None
            # fallback generic if blank
            if not welcome_text:
                welcome_text = (
                    "Welcome {mention}! Please read the rules and click verification."
                )

            try:
                text = welcome_text.format(mention=mention)
            except KeyError:
                # In case the welcome message has invalid format keys
                text = welcome_text + f" {mention}"

            msg = await context.bot.send_message(
                chat_id=group_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
            )

            # Schedule kick and message deletion
            context.job_queue.run_once(
                kick_unverified_user,
                300,  # 5 minutes
                data={
                    "user_id": new_member.id,
                    "message_id": msg.message_id,
                    "chat_id": group_id,
                },
                name=f"kick_{new_member.id}_{msg.message_id}",
            )


async def kick_unverified_user(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kick a user who hasn't verified in 5 minutes and delete the welcome message."""
    job = context.job
    data = job.data
    user_id = data["user_id"]
    message_id = data["message_id"]
    chat_id = data["chat_id"]

    try:
        # Kick (ban then immediately unban to accomplish a kick)
        await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
        await context.bot.unban_chat_member(chat_id=chat_id, user_id=user_id)
    except Exception as e:
        logger.error(f"Failed to kick user {user_id}: {e}")

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.error(f"Failed to delete welcome message {message_id}: {e}")


async def verify_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle verification button click."""
    query = update.callback_query

    if not query.data.startswith("verify_"):
        return

    target_user_id = int(query.data.split("_")[1])

    if query.from_user.id != target_user_id:
        await query.answer("This button is not for you.", show_alert=True)
        return

    chat_id = query.message.chat_id

    config = await db.get_config()
    group_id = config.get("main_group_id") if config else None

    # Check if we should ignore
    if group_id and chat_id != group_id:
        await query.answer()
        return

    # Unrestrict user to defaults
    try:
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target_user_id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_change_info=False,
                can_invite_users=True,
                can_pin_messages=False,
                can_manage_topics=False,
            ),
        )
    except Exception as e:
        logger.error(f"Failed to unrestrict user: {e}")

    # Remove the pending kick job
    current_jobs = context.job_queue.get_jobs_by_name(
        f"kick_{target_user_id}_{query.message.message_id}"
    )
    for job in current_jobs:
        job.schedule_removal()

    # Answer the query
    await query.answer("You have been verified!")

    # Delete the welcome message
    try:
        await context.bot.delete_message(
            chat_id=query.message.chat_id, message_id=query.message.message_id
        )
    except Exception as e:
        logger.error(f"Failed to delete welcome message: {e}")
