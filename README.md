# Dexter (TCNchatbot)

[@TCNchatbot](https://t.me/TCNchatbot)

A complex, feature-rich Telegram bot configured for comprehensive community moderation, management, and engagement. Built with a modular Python backend. (A React Telegram Mini-App template is included for future development but is currently a placeholder and not required).

---

## 🌟 Features

### 🛡️ Community Management & Moderation
- **Welcome Verification**: Greets new users with community rules, restricts their permissions until they interact with a verification button, and automatically kicks unverified users after 5 minutes to prevent spam.
- **Service Message Cleaner**: Automatically deletes noisy Telegram service messages (e.g., "User joined the group", "Message pinned") to keep the chat clean.
- **Admin Alerts**: Users can quickly ping all group administrators in emergencies by simply mentioning `@admin` in the chat.
- **Moderation Tools**: Standard commands for community management: `/mute`, `/unmute`, `/kick`, `/ban`.

### 🎮 CXP (Community Experience Points) System
- **Earn Points**: Users earn `50 CXP` for chatting (limited to 1 per minute).
- **Reaction Economy**: Active members can earn `+50 CXP` broadly from positive reactions on their messages, or lose `-50 CXP` from negative reactions. 
- **Levels & Influence**: Users level up based on CXP. Higher-level users multiply the CXP effect of their reactions!
     * *Lvl 1-4:* Script Kiddie | *Lvl 5-9:* Hash Cracker
     * *Lvl 10-19:* True Operator | *Lvl 20-29:* Dirty Phreak
     * *Lvl 30-39:* Ledger Forger | *Lvl 40-49:* Clean Splicer
     * *Lvl 50-59:* Whale Hunter | *Lvl 60+:* Zero-Day Broker
- **Leaderboards**: View the top active members globally (`/leaderboard`) or filter by timeframe (`/leaderboard day`, `week`, `month`).
- **Contests**: Admins can use `/setcontest` to define a specific date range for special events, trackable via `/contest`.
- **Mini-Games**: Users can use `/steal` to attempt to steal 25-100 CXP from a random user (1-hour cooldown).

### 🌐 Translation & Internationalization
- **Quick Translation**: Start or reply to a message with a language code command to instantly translate it (e.g., `/en`, `/es`, `/fr`, `/pt`, `/id`, `/ru`, `/tr`, `/fa`, `/uk`).
- **Interactive Menu**: Reply to any message with `/translate` to open an inline button menu with language options.

### 🤖 AI Assistant integration
- **Gemini Integration**: Users can ask the bot questions regarding community lore, mechanics, or general inquiries using `/ask <question>`.

### ⏰ Time Zone Management
- **Check Times**: Easily check the exact time for a specific location (`/time London`) or another user (`/time @username`).
- **Set Local Time**: Users can configure their personal time zone using `/settime <location>`.

### 📢 Channel Posting & Forwarding
- **Drafting Posts**: Designated channel admins can DM the bot to draft and preview messages before posting.
- **Media & Formatting**: Supports text, photos, and markdown-formatted buttons for professional channel announcements.
- **Auto-Forwarding**: Automatically forwards channel posts to a designated discussion topic in the main group.

### 👑 Owner DM Navigation Panel
- **Setup Wizard**: When the bot owner first DMs the bot, they are guided through an interactive setup process to link their main group, announcement channel, and admin topic.
- **Bot Configuration**: A convenient inline-button menu to change group mappings, customize the welcome message, and verify that the bot has all the required permissions across different chats.
- **Channel Admin Management**: The owner can seamlessly add or remove channel admins who are authorized to draft and post to the connected channel.

### ⚙️ Telegram Mini-App (Placeholder)
- **Future Development**: A React WebApp structure is included in the project but is currently just a placeholder and not used for any active features. It is not required for the bot to run.

---

## 🛠 Prerequisites

Before starting, ensure you have the following installed:
- **Python 3.14+** & [Poetry](https://python-poetry.org/docs/#installation) (for the backend)
- **Node.js 18+** & npm (for the React Mini-App)
- **PostgreSQL Database**
- **Telegram Bot Token** (obtain from [@BotFather](https://t.me/BotFather))
- **Google Gemini API Key** (for AI features)

---

## 🚀 Setup & Installation

Follow these steps to get a local instance of the bot running from scratch.

### 1. Clone the Repository
```bash
git clone https://github.com/symmetricalboy/tcnchatbot.git
cd tcnchatbot
```
*(Note: ensure the folder matches your repository name)*

### 2. Backend Setup
The bot's backend is built with Python, FastAPI, and `python-telegram-bot` (`v22+`), managed by Poetry.

```bash
# Navigate to the backend directory (or stay in root if poetry is configured there)
cd backend

# Install dependencies using Poetry
poetry install
```

#### Environment Variables
Copy the `.env.example` file to create your local `.env` configuration file:
```bash
cp .env.example .env
```
Open `.env` and configure the following required variables:
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
BOT_OWNER_ID=your_telegram_user_id_here
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
GEMINI_API_KEY=your_gemini_api_key_here
PORT=3000 # Default local port for FastAPI
```

*(Optional)* `PUBLIC_DOMAIN` can be set if you are using webhooks (e.g., via ngrok) instead of long polling.

### 3. Database Initialization
Ensure your PostgreSQL database server is running and the database specified in your `DATABASE_URL` (e.g., `dbname`) exists. The bot uses `asyncpg` to connect and will handle its own table generation/verification upon first run.

### 4. Interactive Bot Setup (Crucial)
Once the backend is running, the bot **must** be configured through Telegram. This maps your Discord/Telegram chats to the bot's database:
1. Start a Private Chat (DM) with your bot using the Telegram account you specified in the `BOT_OWNER_ID` environment variable.
2. Send `/start` to the bot.
3. The bot will initiate a **Setup Wizard** asking for the `@usernames` of your Main Group, Channel, and Admin Group, as well as the link to your CXP topic.
4. After completing this process, the Owner Dashboard will become available, and the bot will actively function in your configured chats. *(Note: Ensure your groups/channels have public `@usernames` set for linking).*

### 5. Mini-App Setup (Optional)
The front-end WebApp is built with React and Vite, but is currently a placeholder and **not required**.

```bash
# Navigate to the mini-app directory
cd ../mini-app

# Install dependencies
npm install
```

---

## 🏃 Running the Bot

### Local Development

You need to start both the Python backend and the React front-end development servers.

**Terminal 1 (Backend):**
```bash
# From the project root or backend directory
poetry run python backend/bot.py
```
*This starts the Telegram bot (via long polling if no public domain is set) and the FastAPI server concurrently.*

**Terminal 2 (Mini-App):**
```bash
# From the mini-app directory
npm run dev
```
*This starts the Vite React application on `http://localhost:5173`.*

### Production Deployment (Railway)
The repository includes a `railway.toml` for easy deployment.
1. Connect your GitHub repository to [Railway](https://railway.app/).
2. Provision a PostgreSQL Add-on within the Railway project.
3. Configure your Environment Variables in Railway (`TELEGRAM_BOT_TOKEN`, `BOT_OWNER_ID`, `GEMINI_API_KEY`, etc.). Railway handles the `PORT` and `DATABASE_URL` automatically.
4. Deploy!

---

*Developed by [@symmboy](https://t.me/symmboy)*
