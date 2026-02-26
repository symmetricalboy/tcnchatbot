import os
import asyncio
from telegram import Bot
from dotenv import load_dotenv


async def main():
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    bot = Bot(token)
    info = await bot.get_webhook_info()
    print(f"Current webhook: {info}")
    await bot.delete_webhook(drop_pending_updates=True)
    print("Deleted webhook!")


if __name__ == "__main__":
    asyncio.run(main())
