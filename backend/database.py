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
            raise ValueError("DATABASE_URL is not set in the environment.")

        self.pool = await asyncpg.create_pool(database_url)
        await self.init_db()
        logger.info("Connected to the database successfully.")

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
                    main_group_id BIGINT,
                    channel_id BIGINT,
                    admin_group_id BIGINT,
                    welcome_message TEXT
                );
                
                ALTER TABLE bot_config ADD COLUMN IF NOT EXISTS cxp_topic_id BIGINT;
                
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    cxp INTEGER DEFAULT 0,
                    last_message_time TIMESTAMP,
                    username VARCHAR(255),
                    is_admin BOOLEAN DEFAULT FALSE
                );
                
                ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(255);
                ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name VARCHAR(255);
                ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS last_steal_time TIMESTAMP;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS location VARCHAR(255);

                CREATE TABLE IF NOT EXISTS messages (
                    chat_id BIGINT,
                    message_id BIGINT,
                    user_id BIGINT,
                    PRIMARY KEY (chat_id, message_id)
                );
                
                CREATE TABLE IF NOT EXISTS translations (
                    chat_id BIGINT,
                    message_id BIGINT,
                    original_text TEXT,
                    lang_en TEXT,
                    lang_es TEXT,
                    lang_fr TEXT,
                    lang_pt TEXT,
                    lang_id TEXT,
                    lang_fa TEXT,
                    lang_ru TEXT,
                    lang_uk TEXT,
                    lang_tr TEXT,
                    PRIMARY KEY (chat_id, message_id)
                );
                
                CREATE TABLE IF NOT EXISTS translated_messages (
                    chat_id BIGINT,
                    message_id BIGINT,
                    original_message_id BIGINT,
                    author_id BIGINT,
                    author_name TEXT,
                    PRIMARY KEY (chat_id, message_id)
                );
                
                INSERT INTO bot_config (id, welcome_message) 
                VALUES (1, 'Welcome {mention}!\n\n📜 Community Rules:\n- Be polite and respectful\n- No spam or unwanted advertising\n- Follow moderator instructions\n- Please use the appropriate topics for your discussions\n\n🎮 Enjoy your time in The Clean Network Community!') 
                ON CONFLICT (id) DO NOTHING;
            """
            )

    async def update_user_steal_time(self, user_id: int):
        if not self.pool:
            return
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET last_steal_time = CURRENT_TIMESTAMP WHERE user_id = $1",
                user_id,
            )

    async def get_config(self):
        if not self.pool:
            return None
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM bot_config WHERE id = 1")

    async def update_config(self, **kwargs):
        if not self.pool:
            logger.error("update_config returning False because self.pool is None")
            return False

        valid_keys = {
            "main_group_id",
            "channel_id",
            "admin_group_id",
            "welcome_message",
            "cxp_topic_id",
        }
        updates = []
        values = []

        for k, v in kwargs.items():
            if k in valid_keys:
                values.append(v)
                updates.append(f"{k} = ${len(values)}")
            else:
                logger.warning(f"update_config ignoring invalid key: {k}")

        if not updates:
            logger.error(
                f"update_config returning False because updates is empty. kwargs: {kwargs}"
            )
            return False

        set_clause = ", ".join(updates)
        query = f"UPDATE bot_config SET {set_clause} WHERE id = 1"
        logger.info(f"update_config executing: {query} with values: {values}")

        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(query, *values)
                logger.info(f"update_config execute result: {result}")
                if result == "UPDATE 0":
                    raise Exception("Database configuration row id=1 is missing.")
                return True
        except Exception as e:
            logger.error(f"update_config encountered an unexpected error: {e}")
            raise

    async def get_user(self, user_id):
        if not self.pool:
            return None
        async with self.pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT * FROM users WHERE user_id = $1", user_id
            )
            if not user:
                await conn.execute(
                    "INSERT INTO users (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING",
                    user_id,
                )
                user = await conn.fetchrow(
                    "SELECT * FROM users WHERE user_id = $1", user_id
                )
            return user

    async def get_user_by_username(self, username: str):
        if not self.pool:
            return None
        # remove @ if present
        username = username.lstrip("@")
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM users WHERE username ILIKE $1 OR display_name ILIKE $1",
                username,
            )

    async def get_random_user(self, exclude_user_id: int):
        if not self.pool:
            return None
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM users WHERE user_id != $1 ORDER BY RANDOM() LIMIT 1",
                exclude_user_id,
            )

    async def update_user_username(self, user_id: int, username: str):
        if not self.pool or not username:
            return
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET username = $2 WHERE user_id = $1", user_id, username
            )

    async def update_user_display_name(
        self, user_id: int, display_name: str, username: str = None
    ):
        if not self.pool or not display_name:
            return
        async with self.pool.acquire() as conn:
            if username:
                await conn.execute(
                    "UPDATE users SET display_name = $2, username = $3 WHERE user_id = $1",
                    user_id,
                    display_name,
                    username,
                )
            else:
                await conn.execute(
                    "UPDATE users SET display_name = $2 WHERE user_id = $1",
                    user_id,
                    display_name,
                )

    async def get_user_location(self, user_id: int):
        if not self.pool:
            return None
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT location FROM users WHERE user_id = $1", user_id
            )

    async def update_user_location(self, user_id: int, location: str):
        if not self.pool or not location:
            return
        # Basic input validation, ensuring it's not too long
        location = location[:255]
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET location = $2 WHERE user_id = $1", user_id, location
            )

    async def update_user_admin_status(self, user_id: int, is_admin: bool):
        if not self.pool:
            return
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET is_admin = $2 WHERE user_id = $1", user_id, is_admin
            )

    async def get_admin_users(self):
        if not self.pool:
            return []
        async with self.pool.acquire() as conn:
            return await conn.fetch("SELECT * FROM users WHERE is_admin = TRUE")

    async def update_user_cxp(self, user_id, delta_cxp, update_timestamp=False):
        if not self.pool:
            return False
        async with self.pool.acquire() as conn:
            if update_timestamp:
                await conn.execute(
                    "UPDATE users SET cxp = cxp + $2, last_message_time = CURRENT_TIMESTAMP WHERE user_id = $1",
                    user_id,
                    delta_cxp,
                )
            else:
                await conn.execute(
                    "UPDATE users SET cxp = cxp + $2 WHERE user_id = $1",
                    user_id,
                    delta_cxp,
                )
            return True

    async def get_user_rank(self, cxp):
        if not self.pool:
            return None
        async with self.pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE cxp > $1 AND (is_admin = FALSE OR is_admin IS NULL)",
                cxp,
            )
            return count + 1

    async def get_leaderboard(self, limit=3):
        if not self.pool:
            return []
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                "SELECT * FROM users ORDER BY cxp DESC LIMIT $1", limit
            )

    async def record_message(self, chat_id, message_id, user_id):
        if not self.pool:
            return
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO messages (chat_id, message_id, user_id) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                chat_id,
                message_id,
                user_id,
            )

    async def get_message_author(self, chat_id, message_id):
        if not self.pool:
            return None
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT user_id FROM messages WHERE chat_id = $1 AND message_id = $2",
                chat_id,
                message_id,
            )

    async def save_original_translation_text(
        self, chat_id: int, message_id: int, text: str
    ):
        if not self.pool:
            return
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO translations (chat_id, message_id, original_text) 
                VALUES ($1, $2, $3) 
                ON CONFLICT (chat_id, message_id) DO UPDATE SET original_text = EXCLUDED.original_text
                """,
                chat_id,
                message_id,
                text,
            )

    async def get_translation(self, chat_id: int, message_id: int, lang_code: str):
        """Fetch the specific cached language text if it exists."""
        if not self.pool:
            return None

        # Valid language codes matching our strict columns
        valid_langs = {"en", "es", "fr", "pt", "id", "fa", "ru", "uk", "tr"}
        if lang_code not in valid_langs:
            return None

        # Dynamically build the column name (safe because it's strictly validated above)
        column_name = f"lang_{lang_code}"

        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                f"SELECT {column_name} FROM translations WHERE chat_id = $1 AND message_id = $2",
                chat_id,
                message_id,
            )

    async def get_translation_original_text(self, chat_id: int, message_id: int):
        if not self.pool:
            return None
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT original_text FROM translations WHERE chat_id = $1 AND message_id = $2",
                chat_id,
                message_id,
            )

    async def save_translation(
        self, chat_id: int, message_id: int, lang_code: str, translated_text: str
    ):
        if not self.pool:
            return

        valid_langs = {"en", "es", "fr", "pt", "id", "fa", "ru", "uk", "tr"}
        if lang_code not in valid_langs:
            return

        column_name = f"lang_{lang_code}"
        async with self.pool.acquire() as conn:
            await conn.execute(
                f"UPDATE translations SET {column_name} = $3 WHERE chat_id = $1 AND message_id = $2",
                chat_id,
                message_id,
                translated_text,
            )

    async def link_translation(
        self,
        chat_id: int,
        message_id: int,
        original_message_id: int,
        author_id: int,
        author_name: str,
    ):
        if not self.pool:
            return
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO translated_messages (chat_id, message_id, original_message_id, author_id, author_name)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (chat_id, message_id) DO NOTHING
                """,
                chat_id,
                message_id,
                original_message_id,
                author_id,
                author_name,
            )

    async def get_translation_link(self, chat_id: int, message_id: int):
        if not self.pool:
            return None
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT original_message_id, author_id, author_name FROM translated_messages WHERE chat_id = $1 AND message_id = $2",
                chat_id,
                message_id,
            )


db = Database()
