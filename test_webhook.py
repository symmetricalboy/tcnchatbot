import asyncio
from telegram.ext import Application
from telegram import Update


async def main():
    app = Application.builder().token("12345:ABCDEF").build()

    # Check if app has consumer attached when started
    await app.initialize()
    await app.start()

    # Fake an update that would trigger a handler if it had any
    update = Update(update_id=1)
    await app.update_queue.put(update)

    # Let the event loop run for a second
    await asyncio.sleep(1)

    await app.stop()
    await app.shutdown()
    print("Test finished successfully!")


if __name__ == "__main__":
    asyncio.run(main())
