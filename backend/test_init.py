import asyncio
import os
from database import db
from telegram.ext import Application


async def my_post_init(app):
    print("Executing post_init")
    await db.connect()
    print(f"Pool state in post_init: {db.pool}")


async def main():
    os.environ["DATABASE_URL"] = "postgres://fake:fake@localhost:5432/fake"
    app = Application.builder().token("12345:ABCDEF").post_init(my_post_init).build()

    try:
        # Avoid throwing on get_me
        app.bot.get_me = lambda *args, **kwargs: asyncio.Future()
        app.bot.get_me().set_result(None)
    except Exception:
        pass

    try:
        await app.initialize()
    except Exception as e:
        print(f"Initialize exception: {e}")

    print(f"Pool state after initialize: {db.pool}")


if __name__ == "__main__":
    asyncio.run(main())
