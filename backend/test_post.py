import asyncio
from telegram.ext import Application
import sys


async def check_post_init(application: Application):
    print("HELLO FROM POST_INIT")
    with open("post_init_run.txt", "w") as f:
        f.write("run")


async def main():
    # Use a dummy token to avoid InvalidToken
    application = (
        Application.builder()
        .token("123456789:AABBCCDDEEFFggHHiijjKKllMMnnOOpp_qq")
        .post_init(check_post_init)
        .build()
    )

    try:
        print("Initializing...")
        await application.initialize()
        print("Starting...")
        await application.start()
        print("Started.")
    except Exception as e:
        print(f"Exception: {e}")
    finally:
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
