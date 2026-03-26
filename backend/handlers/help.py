from telegram import Update
from telegram.ext import CallbackContext


async def help_cmd(update: Update, context: CallbackContext):
    """Handler for /help to show general bot info."""
    msg = (
        "🤖 **About TCN's Chatbot, Dexter** 🤖\n\n"
        "I am here to manage the community, handle translation, and track community engagement.\n\n"
        "**Features:**\n"
        "• **CXP System**: Earn Community Experience Points (CXP) by chatting and reacting to messages. As you level up, your reactions carry more weight!\n"
        "• **Leaderboards & Contests**: Compete with others and view the most active community members across different timeframes (daily, weekly, monthly) or during special contests.\n"
        "• **Translations**: I can automatically translate messages between different languages so everyone can understand each other.\n"
        "• **Time Zones**: Use me to check the current time anywhere in the world, or link your location to your account.\n"
        "• **AI Assistant**: Ask me anything about the game's lore, mechanics, or my features.\n\n"
        "**Earning CXP:**\n"
        "• **Messages**: Earn `50 CXP` for chatting (limit 1 per minute).\n"
        "• **Reactions**: Earn or lose CXP when others react to your messages.\n"
        "  Positive emojis give `+50 CXP`, negative emojis give `-50 CXP`.\n"
        "• **Influence**: Higher level users multiply the CXP of their reactions! Your vote carries more weight as you rank up.\n\n"
        "**Level Titles:**\n"
        "• **Lvl 1-4:** Script Kiddie\n"
        "• **Lvl 5-9:** Hash Cracker\n"
        "• **Lvl 10-19:** True Operator\n"
        "• **Lvl 20-29:** Dirty Phreak\n"
        "• **Lvl 30-39:** Ledger Forger\n"
        "• **Lvl 40-49:** Clean Splicer\n"
        "• **Lvl 50-59:** Whale Hunter\n"
        "• **Lvl 60+:** Zero-Day Broker\n\n"
        "To view the specific commands and how to use them, type `/commands`."
    )
    try:
        await update.message.delete()
    except Exception:
        pass

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        message_thread_id=update.message.message_thread_id,
        text=msg,
        parse_mode="Markdown",
    )


async def commands_cmd(update: Update, context: CallbackContext):
    """Handler for /commands to show CXP info."""
    msg = (
        "🌟 **User Commands** 🌟\n\n"
        "**Bot Command Center / CXP Commands:**\n"
        "• `/level` — View your own stats and rank.\n"
        "  *Syntax:* `/level` or `/level @username`\n\n"
        "• `/leaderboard` — View the top 10 CXP leaders (Admins excluded).\n"
        "  *Syntax:* `/leaderboard` (all-time) or `/leaderboard <day|week|month|contest>`\n\n"
        "• `/contest` — View the current contest leaderboard.\n"
        "  *Syntax:* `/contest`\n\n"
        "• `/steal` — Steal 25-100 CXP from a random user! 1-hour cooldown.\n"
        "  *Syntax:* `/steal`\n\n"
        "• `/ask` — Ask the AI assistant a question about the game.\n"
        "  *Syntax:* `/ask <question>`\n\n"
        "• `/time` — Get the current exact time for a user or location.\n"
        "  *Syntax:* `/time <location>` or `/time @username`\n\n"
        "• `/settime` — Set your own local time zone/location.\n"
        "  *Syntax:* `/settime <location>`\n\n"
        "• `/ping` — Check bot response latency and connection method.\n"
        "  *Syntax:* `/ping`\n\n"
        "**Translation Commands:**\n"
        "Start a message with or reply to a message with one of the following commands to translate it:\n"
        "`/en` (English), `/es` (Spanish), `/fr` (French),\n"
        "`/pt` (Portuguese), `/id` (Indonesian), `/fa` (Persian),\n"
        "`/ru` (Russian), `/uk` (Ukrainian), `/tr` (Turkish).\n"
        "You can also reply to a message with `/translate` for an interactive translation menu."
    )
    try:
        await update.message.delete()
    except Exception:
        pass

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        message_thread_id=update.message.message_thread_id,
        text=msg,
        parse_mode="Markdown",
    )
