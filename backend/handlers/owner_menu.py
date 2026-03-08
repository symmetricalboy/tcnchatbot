import logging
import re
from telegram import Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    MessageHandler,
    ConversationHandler,
    CallbackContext,
    CallbackQueryHandler,
    filters,
)

from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import warnings
from telegram.warnings import PTBUserWarning

from database import db

logger = logging.getLogger(__name__)

# Define conversation states
MAIN_GROUP, PUBLIC_CHANNEL, ADMIN_CHANNEL, CXP_TOPIC = range(4)
# Additional states for individual edits
EDIT_MAIN, EDIT_CHANNEL, EDIT_ADMIN, EDIT_WELCOME, EDIT_CXP = range(4, 9)


async def _extract_topic_id(message) -> int | None:
    """Extract topic ID from a forwarded message or topic link."""
    if getattr(message, "message_thread_id", None):
        return message.message_thread_id

    text = message.text.strip() if message.text else ""
    try:
        return int(text)
    except ValueError:
        pass

    match = re.search(r"t\.me/(?:c/\d+/|[\w_]+/)?(\d+)", text)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass

    return None


async def _resolve_chat_id(input_str: str, context: CallbackContext) -> int | None:
    """Try to resolve a Telegram username to a chat ID. Rejects numeric IDs."""
    if not input_str:
        return None

    # Strip URLs to allow users to paste t.me/ links
    input_str = (
        input_str.replace("https://", "").replace("http://", "").replace("t.me/", "")
    )
    input_str = input_str.rstrip("/").strip()

    # Check if the user tried to input a numeric ID
    try:
        int(input_str)
        # If it parses as an int, they didn't provide a username
        return None
    except ValueError:
        pass

    # Ensure it's formatted as a username
    username = input_str if input_str.startswith("@") else f"@{input_str}"

    try:
        chat = await context.bot.get_chat(username)
        return chat.id
    except Exception as e:
        logger.error(f"Failed to resolve username {username}: {e}")
        return None


async def start(update: Update, context: CallbackContext) -> int:
    """Entry point for the owner. Checks DB and routes to either the setup wizard or the main menu."""
    if update.effective_chat.type != "private":
        return ConversationHandler.END

    # Check database status
    config = await db.get_config()
    is_configured = False
    if config:
        if (
            config.get("main_group_id")
            and config.get("channel_id")
            and config.get("admin_group_id")
        ):
            is_configured = True

    if not is_configured:
        # Auto-start setup wizard mapping
        await update.message.reply_text(
            "⚙️ **Welcome! Let's initialize your bot configuration.**\n\n"
            "**CRITICAL REQUIREMENT:** For security and routing consistency, **ALL** groups and channels "
            "(including the admin group) **MUST HAVE A PUBLIC @USERNAME SET** to be linked "
            "linked to this bot. We strongly advise that you turn on 'Approve New Members' for the admin group "
            "so the public username does not expose it to unauthorized users.\n\n"
            "First, please send me the **@username** of your **main group**.\n\n"
            "Note: You must add me to this group and give me ALL permissions (except 'Remain Anonymous').\n\n"
            "Please send the group @username now (or type /restart to abort):",
            parse_mode="Markdown",
        )
        return MAIN_GROUP
    else:
        # Show main owner menu
        keyboard = [
            [InlineKeyboardButton("⚙️ Group & Channel", callback_data="group_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        welcome_text = (
            "👋 **Owner Menu**\n\n"
            "Your bot is currently configured and active! Use the buttons below to manage settings."
        )

        await update.message.reply_text(
            welcome_text, reply_markup=reply_markup, parse_mode="Markdown"
        )
        return ConversationHandler.END


async def group_menu(update: Update, context: CallbackContext) -> int:
    """Show the Group & Channel submenu."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("🔄 Change Main Group", callback_data="edit_main")],
        [InlineKeyboardButton("🔄 Change Channel", callback_data="edit_channel")],
        [InlineKeyboardButton("🔄 Change Admin Group", callback_data="edit_admin")],
        [InlineKeyboardButton("💬 Edit Welcome Msg", callback_data="edit_welcome")],
        [InlineKeyboardButton("🎯 Edit CXP Topic", callback_data="edit_cxp")],
        [InlineKeyboardButton("🛡️ Check Permissions", callback_data="check_perms")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_main")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "⚙️ **Group & Channel Settings**\n\n"
        "Select an option to update individual chat IDs or verify the bot's permissions.",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def back_to_main(update: Update, context: CallbackContext) -> int:
    """Return to the main owner menu from a submenu."""
    query = update.callback_query
    await query.answer()

    keyboard = [[InlineKeyboardButton("⚙️ Group & Channel", callback_data="group_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        "👋 **Owner Menu**\n\n"
        "Your bot is currently configured and active! Use the buttons below to manage settings."
    )

    await query.edit_message_text(
        welcome_text, reply_markup=reply_markup, parse_mode="Markdown"
    )
    return ConversationHandler.END


async def get_main_group(update: Update, context: CallbackContext) -> int:
    """Handle main group input and ask for public channel."""
    group_input = update.message.text.strip()
    group_id = await _resolve_chat_id(group_input, context)

    if group_id is None:
        await update.message.reply_text(
            "Could not resolve the group. Please provide a valid public @username. "
            "(Numeric IDs are no longer supported for security reasons)."
        )
        return MAIN_GROUP

    context.user_data["main_group"] = group_id

    await update.message.reply_text(
        f"✅ Validated Main Group (ID: `{group_id}`)\n\n"
        "Next, please send me the **@username** of your **channel**.\n\n"
        "Note: You must also add me to this channel as an admin with ALL permissions (except 'Remain Anonymous').\n\n"
        "Please send the channel @username now:",
        parse_mode="Markdown",
    )
    return PUBLIC_CHANNEL


async def get_public_channel(update: Update, context: CallbackContext) -> int:
    """Handle public channel input and ask for admin channel."""
    channel_input = update.message.text.strip()
    channel_id = await _resolve_chat_id(channel_input, context)

    if channel_id is None:
        await update.message.reply_text(
            "Could not resolve the channel. Please provide a valid public @username. "
            "(Numeric IDs are no longer supported for security reasons)."
        )
        return PUBLIC_CHANNEL

    context.user_data["public_channel"] = channel_id

    await update.message.reply_text(
        f"✅ Validated Channel (ID: `{channel_id}`)\n\n"
        "Finally, please send me the **@username** of your **admin group**.\n\n"
        "*(Reminder: You must set a public link/username for your admin group so the bot can link to it. "
        "Please turn on 'Approve New Members' in the admin group to keep it secure!)*\n\n"
        "Note: I need ALL admin permissions here as well, except 'Remain Anonymous'.\n\n"
        "Please send the admin group @username now:",
        parse_mode="Markdown",
    )
    return ADMIN_CHANNEL


async def get_admin_channel(update: Update, context: CallbackContext) -> int:
    """Handle admin channel input, save to context, ask for CXP topic."""
    admin_channel_input = update.message.text.strip()
    admin_group_id = await _resolve_chat_id(admin_channel_input, context)

    if admin_group_id is None:
        await update.message.reply_text(
            "Could not resolve the admin group. Please provide a valid public @username. "
            "(Numeric IDs are no longer supported for security reasons)."
        )
        return ADMIN_CHANNEL

    context.user_data["admin_channel"] = admin_group_id

    await update.message.reply_text(
        f"✅ Validated Admin Group (ID: `{admin_group_id}`)\n\n"
        "Now, please provide the link to the **CXP Dedicated Topic** inside the main group.\n"
        "You can get this by going to your main group, right clicking on the topic, and selecting 'Copy Link'.\n"
        "Alternatively, you can forward any message from that topic to me.\n\n"
        "Please send the topic link or forwarded message now:",
        parse_mode="Markdown",
    )
    return CXP_TOPIC


async def get_cxp_topic(update: Update, context: CallbackContext) -> int:
    """Handle CXP topic input, save config to database, and finish."""
    topic_id = await _extract_topic_id(update.message)

    if topic_id is None:
        await update.message.reply_text(
            "Could not extract a Topic ID. Please send a valid topic link (e.g. https://t.me/c/1234/56) "
            "or forward a message directly from the topic."
        )
        return CXP_TOPIC

    main_group_id = context.user_data.get("main_group")
    channel_id = context.user_data.get("public_channel")
    admin_group_id = context.user_data.get("admin_channel")

    try:
        success = await db.update_config(
            main_group_id=main_group_id,
            channel_id=channel_id,
            admin_group_id=admin_group_id,
            cxp_topic_id=topic_id,
        )
        if not success:
            raise Exception(f"Database returned False. Pool is None: {db.pool is None}")

        await update.message.reply_text(
            "Configuration Complete!\n\n"
            "I have updated the database with the following IDs:\n"
            f"- Main Group: {main_group_id}\n"
            f"- Channel: {channel_id}\n"
            f"- Admin Group: {admin_group_id}\n"
            f"- CXP Topic ID: {topic_id}\n\n"
            "Please ensure I have been added to all of these with ALL permissions (except anonymous).\n"
            "Have a great day!"
        )
    except Exception as e:
        logger.error(f"Failed to update database configuraton: {e}")
        await update.message.reply_text(
            f"An error occurred while saving the configuration to the database. "
            f"Error details: {e}\nPlease check the logs and try again."
        )

    context.user_data.clear()
    return await start(update, context)


async def prompt_edit_main(update: Update, context: CallbackContext) -> int:
    """Prompt the user for a new Main Group username."""
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "📝 **Change Main Group**\n\n"
        "Please send me the **@username** of your new **main group**.\n\n"
        "*(Type /restart to cancel this edit and return to the main menu)*",
        parse_mode="Markdown",
    )
    return EDIT_MAIN


async def save_edit_main(update: Update, context: CallbackContext) -> int:
    """Save the new Main Group."""
    group_input = update.message.text.strip()
    group_id = await _resolve_chat_id(group_input, context)

    if group_id is None:
        await update.message.reply_text(
            "Could not resolve the group. Please provide a valid public @username. "
            "(Numeric IDs are no longer supported for security reasons)."
        )
        return EDIT_MAIN

    try:
        success = await db.update_config(main_group_id=group_id)
        if not success:
            raise Exception(f"Database returned False. Pool is None: {db.pool is None}")
        await update.message.reply_text(
            f"✅ Main Group updated successfully (ID: `{group_id}`).",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Failed to update Main Group: {e}")
        await update.message.reply_text(f"Database update failed: {e}")

    return await start(update, context)


async def prompt_edit_channel(update: Update, context: CallbackContext) -> int:
    """Prompt the user for a new Channel username."""
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "📝 **Change Channel**\n\n"
        "Please send me the **@username** of your new **channel**.\n\n"
        "*(Type /restart to cancel this edit and return to the main menu)*",
        parse_mode="Markdown",
    )
    return EDIT_CHANNEL


async def save_edit_channel(update: Update, context: CallbackContext) -> int:
    """Save the new Channel."""
    channel_input = update.message.text.strip()
    channel_id = await _resolve_chat_id(channel_input, context)

    if channel_id is None:
        await update.message.reply_text(
            "Could not resolve the channel. Please provide a valid public @username. "
            "(Numeric IDs are no longer supported for security reasons)."
        )
        return EDIT_CHANNEL

    try:
        success = await db.update_config(channel_id=channel_id)
        if not success:
            raise Exception(f"Database returned False. Pool is None: {db.pool is None}")
        await update.message.reply_text(
            f"✅ Channel updated successfully (ID: `{channel_id}`).",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Failed to update Channel: {e}")
        await update.message.reply_text(f"Database update failed: {e}")

    return await start(update, context)


async def prompt_edit_admin(update: Update, context: CallbackContext) -> int:
    """Prompt the user for a new Admin Group username."""
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "📝 **Change Admin Group**\n\n"
        "Please send me the **@username** of your new **admin group**.\n\n"
        "*(Type /restart to cancel this edit and return to the main menu)*",
        parse_mode="Markdown",
    )
    return EDIT_ADMIN


async def save_edit_admin(update: Update, context: CallbackContext) -> int:
    """Save the new Admin Group."""
    admin_input = update.message.text.strip()
    admin_id = await _resolve_chat_id(admin_input, context)

    if admin_id is None:
        await update.message.reply_text(
            "Could not resolve the admin group. Please provide a valid public @username. "
            "(Numeric IDs are no longer supported for security reasons)."
        )
        return EDIT_ADMIN

    try:
        success = await db.update_config(admin_group_id=admin_id)
        if not success:
            raise Exception(f"Database returned False. Pool is None: {db.pool is None}")
        await update.message.reply_text(
            f"✅ Admin Group updated successfully (ID: `{admin_id}`).",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Failed to update Admin Group: {e}")
        await update.message.reply_text(f"Database update failed: {e}")

    return await start(update, context)


async def check_permissions(update: Update, context: CallbackContext) -> int:
    """Check the bot's permissions in the configured chats."""
    query = update.callback_query
    await query.answer()

    config = await db.get_config()
    if not config:
        await query.message.reply_text("Database is unconfigured.")
        return ConversationHandler.END

    main_group_id = config.get("main_group_id")
    channel_id = config.get("channel_id")
    admin_id = config.get("admin_group_id")

    results = []

    # Helper to check a specific chat
    async def _check_chat(chat_id: int, chat_name: str):
        if not chat_id:
            results.append(f"❌ **{chat_name}**: Not Configured")
            return
        try:
            chat = await context.bot.get_chat(chat_id)
            member = await chat.get_member(context.bot.id)

            if member.status == "creator":
                results.append(f"✅ **{chat_name}**: Creator (All Permissions OK)")
                return
            elif member.status == "administrator":
                missing_perms = []

                # Remain Anonymous must be OFF (False or None)
                if getattr(member, "is_anonymous", False):
                    missing_perms.append("Remain Anonymous (MUST BE DISABLED)")

                if chat.type == "channel":
                    if not getattr(member, "can_post_messages", False):
                        missing_perms.append("Post Messages")
                    if not getattr(member, "can_edit_messages", False):
                        missing_perms.append("Edit Messages")
                    if not getattr(member, "can_delete_messages", False):
                        missing_perms.append("Delete Messages")
                else:
                    # Check group permissions
                    group_perms = [
                        ("can_manage_chat", "Manage Chat"),
                        ("can_delete_messages", "Delete Messages"),
                        ("can_manage_video_chats", "Manage Video Chats"),
                        ("can_restrict_members", "Restrict Members"),
                        ("can_promote_members", "Promote Members"),
                        ("can_change_info", "Change Info"),
                        ("can_invite_users", "Invite Users"),
                        ("can_pin_messages", "Pin Messages"),
                    ]
                    # Also check handle topics if applicable
                    # Telegram's API sets `is_forum` to True if Topics are enabled in the supergroup
                    if chat.is_forum:
                        group_perms.append(("can_manage_topics", "Manage Topics"))

                    for attr, name in group_perms:
                        if getattr(member, attr, None) is False:
                            missing_perms.append(name)

                if missing_perms:
                    results.append(
                        f"⚠️ **{chat_name}**: Missing permissions: {', '.join(missing_perms)}"
                    )
                else:
                    results.append(f"✅ **{chat_name}**: Admin Access OK")
            else:
                results.append(
                    f"⚠️ **{chat_name}**: Present, but NOT an Admin. Please promote the bot."
                )
        except Exception as e:
            results.append(
                f"❌ **{chat_name}**: Error Accessing (Is the bot a member?) - `{e}`"
            )

    await _check_chat(main_group_id, "Main Group")
    await _check_chat(channel_id, "Channel")
    await _check_chat(admin_id, "Admin Group")

    cxp_topic_id = config.get("cxp_topic_id")
    if cxp_topic_id:
        results.append(f"✅ **CXP Topic ID Configured**: `{cxp_topic_id}`")
    else:
        results.append("❌ **CXP Topic**: Not Configured")

    report = "🛡️ **Permission Check Results**\n\n" + "\n\n".join(results)

    keyboard = [
        [InlineKeyboardButton("🔄 Check Again", callback_data="check_perms")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_main")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        report, reply_markup=reply_markup, parse_mode="Markdown"
    )
    return ConversationHandler.END


async def restart(update: Update, context: CallbackContext) -> int:
    """Restart the configuration completely."""
    await update.message.reply_text(
        "Configuration restarted. Type /start to begin again."
    )
    context.user_data.clear()
    return ConversationHandler.END


async def prompt_edit_welcome(update: Update, context: CallbackContext) -> int:
    """Prompt the user for a new Welcome Message."""
    query = update.callback_query
    await query.answer()

    config = await db.get_config()
    current_msg = config.get("welcome_message") if config else "Not set"

    await query.message.reply_text(
        f"💬 **Change Welcome Message**\n\n"
        f"Here is your current welcome message:\n"
        f"----------------------\n"
        f"{current_msg}\n"
        f"----------------------\n\n"
        f"Please send me the **new welcome message text**. You can use `{{mention}}` "
        f"to mention the user.\n\n"
        f"*(Type /restart to cancel this edit and return to the main menu)*",
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )
    return EDIT_WELCOME


async def save_edit_welcome(update: Update, context: CallbackContext) -> int:
    """Save the new Welcome Message."""
    welcome_input = update.message.text.strip()

    try:
        success = await db.update_config(welcome_message=welcome_input)
        if not success:
            raise Exception(f"Database returned False. Pool is None: {db.pool is None}")
        await update.message.reply_text(
            f"✅ Welcome message updated successfully.",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Failed to update Welcome Message: {e}")
        await update.message.reply_text(f"Database update failed: {e}")

    return await start(update, context)


async def prompt_edit_cxp(update: Update, context: CallbackContext) -> int:
    """Prompt the user for a new CXP Topic."""
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "📝 **Change CXP Topic**\n\n"
        "Please send me the link to your **CXP Dedicated Topic**, or forward a message from it.\n\n"
        "*(Type /restart to cancel this edit and return to the main menu)*",
        parse_mode="Markdown",
    )
    return EDIT_CXP


async def save_edit_cxp(update: Update, context: CallbackContext) -> int:
    """Save the new CXP Topic ID."""
    topic_id = await _extract_topic_id(update.message)

    if topic_id is None:
        await update.message.reply_text(
            "Could not extract a Topic ID. Please send a valid topic link or forward a message."
        )
        return EDIT_CXP

    try:
        success = await db.update_config(cxp_topic_id=topic_id)
        if not success:
            raise Exception(f"Database returned False. Pool is None: {db.pool is None}")
        await update.message.reply_text(
            f"✅ CXP Topic updated successfully (ID: `{topic_id}`).",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Failed to update CXP Topic ID: {e}")
        await update.message.reply_text(f"Database update failed: {e}")

    return await start(update, context)


# Note: Additional edit states and check_perms will be implemented in subsequent functions.


def get_config_conversation_handler() -> ConversationHandler:
    warnings.filterwarnings("ignore", category=PTBUserWarning)
    return ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(group_menu, pattern="^group_menu$"),
            CallbackQueryHandler(back_to_main, pattern="^back_main$"),
            CallbackQueryHandler(check_permissions, pattern="^check_perms$"),
            CallbackQueryHandler(prompt_edit_main, pattern="^edit_main$"),
            CallbackQueryHandler(prompt_edit_channel, pattern="^edit_channel$"),
            CallbackQueryHandler(prompt_edit_admin, pattern="^edit_admin$"),
            CallbackQueryHandler(prompt_edit_welcome, pattern="^edit_welcome$"),
            CallbackQueryHandler(prompt_edit_cxp, pattern="^edit_cxp$"),
        ],
        states={
            MAIN_GROUP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_main_group)
            ],
            PUBLIC_CHANNEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_public_channel)
            ],
            ADMIN_CHANNEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_admin_channel)
            ],
            CXP_TOPIC: [MessageHandler(filters.ALL & ~filters.COMMAND, get_cxp_topic)],
            EDIT_MAIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_edit_main)
            ],
            EDIT_CHANNEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_edit_channel)
            ],
            EDIT_ADMIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_edit_admin)
            ],
            EDIT_WELCOME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_edit_welcome)
            ],
            EDIT_CXP: [MessageHandler(filters.ALL & ~filters.COMMAND, save_edit_cxp)],
        },
        fallbacks=[CommandHandler("restart", restart)],
        per_message=False,
    )
