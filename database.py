import asyncpg
import os
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            logger.error("DATABASE_URL is not set in the environment.")
            return

        try:
            self.pool = await asyncpg.create_pool(database_url)
            await self.init_db()
            logger.info("Connected to the database successfully.")
        except Exception as e:
            logger.error(f"Failed to connect to the database: {e}")

    async def disconnect(self):
        if self.pool:
            await self.pool.close()

    async def init_db(self):
        if not self.pool:
            return

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bot_config (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    topic_group_id BIGINT,
                    channel_id BIGINT,
                    admin_group_id BIGINT
                );
                
                INSERT INTO bot_config (id) VALUES (1) ON CONFLICT (id) DO NOTHING;
            """
            )

    async def get_config(self):
        if not self.pool:
            return None
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM bot_config WHERE id = 1")

    async def update_config(self, **kwargs):
        if not self.pool:
            return False

        valid_keys = {
            "topic_group_id",
            "channel_id",
            "admin_group_id",
        }
        updates = []
        values = []

        for k, v in kwargs.items():
            if k in valid_keys:
                values.append(v)
                updates.append(f"{k} = ${len(values)}")

        if not updates:
            return False

        set_clause = ", ".join(updates)
        query = f"UPDATE bot_config SET {set_clause} WHERE id = 1"

        async with self.pool.acquire() as conn:
            await conn.execute(query, *values)
            return True


db = Database()
