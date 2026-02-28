from telegram import Update
from telegram.ext import ContextTypes

async def clean_service_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete all remaining service messages."""
    if update.message:
        try:
            await update.message.delete()
        except:
            pass
