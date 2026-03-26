import logging
import random
import string
import asyncio
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import CallbackContext

from database import db

logger = logging.getLogger(__name__)

# In-memory auth codes
# Format: {code: {"user_id": user_id, "expires": datetime}}
temp_auth_codes = {}

def clean_expired_codes():
    now = datetime.now()
    expired = [k for k, v in temp_auth_codes.items() if v["expires"] < now]
    for k in expired:
        del temp_auth_codes[k]

def generate_code() -> str:
    return ''.join(random.choices(string.digits, k=6))

async def set_channel_cmd(update: Update, context: CallbackContext):
    """Handler for /setchannel in Private DM and Group."""
    if not update.effective_user or not update.message or not update.effective_chat:
        return

    chat_type = update.effective_chat.type

    if chat_type == "private":
        clean_expired_codes()
        user_id = update.effective_user.id
        
        code = generate_code()
        # Ensure unique
        while code in temp_auth_codes:
            code = generate_code()
            
        temp_auth_codes[code] = {
            "user_id": user_id,
            "expires": datetime.now() + timedelta(minutes=15)
        }
        
        await update.message.reply_text(
            f"🔗 *Channel Linking*\n\n"
            f"Your temporary authorization code is: `{code}`\n\n"
            f"To link your channel to your account, please go to the group and send the following message *as your channel*:\n\n"
            f"`/setchannel {code}`\n\n"
            f"This code will expire in 15 minutes.",
            parse_mode="Markdown"
        )
        return

    # If it's in a group, it's the verification step
    if chat_type in ("group", "supergroup"):
        # We only care if they are posting AS a channel
        if not update.message.sender_chat or update.message.sender_chat.type != "channel":
            # Just ignore if a normal user types it
            return
            
        if not context.args or len(context.args) == 0:
            return
            
        code = context.args[0]
        
        clean_expired_codes()
        
        if code not in temp_auth_codes:
            await update.message.reply_text("❌ Invalid or expired authorization code.")
            return
            
        auth_data = temp_auth_codes[code]
        user_id = auth_data["user_id"]
        channel_id = update.message.sender_chat.id
        channel_title = update.message.sender_chat.title
        
        # Link in DB
        await db.link_channel(channel_id, user_id)
        
        # Invalidate code
        del temp_auth_codes[code]
        
        # Announce
        await update.message.reply_text(
            f"✅ *Success!*\n\nThe channel *{channel_title}* has been successfully linked to your user account.\n"
            f"All CXP earned by this channel will now be credited to you, and your permissions will apply.",
            parse_mode="Markdown"
        )
        
        # Delete the command message to keep chat clean
        try:
            await update.message.delete()
        except Exception:
            pass
