import asyncio
from telegram.ext import Application


async def my_post_init(app: Application):
    print("SUCCESS: POST INIT WAS CALLED")


async def main():
    app = Application.builder().token("12345:ABCDEF").post_init(my_post_init).build()

    await app.initialize()
    await app.start()

    await app.stop()
    await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
