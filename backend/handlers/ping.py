import os
import time
from telegram import Update
from telegram.ext import CallbackContext

async def ping_cmd(update: Update, context: CallbackContext):
    """Handler for /ping to check bot response time and connection method."""
    start_time = time.time()
    
    # Send initial message to calculate round-trip latency
    msg = await update.message.reply_text("Pong! 🏓\nCalculating latency...")
    
    end_time = time.time()
    latency_ms = round((end_time - start_time) * 1000)
    
    # Determine the connection method based on environment variables
    # (These variables are used in bot.py to decide between webhook and polling)
    railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    public_domain = os.environ.get("PUBLIC_DOMAIN")
    
    method = "Webhook" if (railway_domain or public_domain) else "Long Polling"
    
    await msg.edit_text(
        f"Pong! 🏓\nLatency: `{latency_ms}ms`\nConnection: `{method}`", 
        parse_mode="Markdown"
    )
