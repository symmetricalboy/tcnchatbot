# The Clean Network - Megabot Architecture & Roadmap

## Vision
A comprehensive, modular, and highly scalable "Megabot" that acts as the central nervous system for **The Clean Network** game community. This bot manages public engagement, content publishing, moderation, ticket-based support, and back-office team operations.

---

## Technical Overview & Architectural Philosophy
To prevent the codebase from becoming an unmanageable monolith (`bot.py`), the project strictly adheres to a **Domain-Driven Modular Architecture**. 

Every major feature is isolated into its own dedicated package containing its own logic, database models, and handlers. This ensures that independent teams or contributors can iterate on discrete components rapidly without triggering merge conflicts or interfering with other core bot systems. This architecture also strictly separates concerns: database logic, state management, UI presentation, and core feature logic are distinct layers.

## Master Directory Structure
```text
tcnchatbot/
├── bot.py                 # Application factory and runner
├── core/                  # Heartbeat mechanisms, global error handlers, base classes
├── config/                # Environment variables, feature flags, secret management
├── database/              # ORM configurations, connections, migration scripts (Alembic)
├── state/                 # FSMs (Finite State Machines), Redis/Memcached integration
├── ui/                    # Shared UI components (Keyboards, Menus, Formatting)
├── services/              # External API adapters (Game Server, GitHub API, LLMs)
├── modules/               # Isolated feature domains (The logic of the bot)
│   ├── permissions/       # Central Chain of Trust system
│   ├── routing/           # DM-to-Topic ticket routing (Shared Inbox)
│   ├── cxp/               # Community Experience Points system
│   ├── ai/                # LLM integrations and game context
│   ├── moderation/        # Spam filtering and moderation tools
│   ├── content/           # Channel authoring and broadcasting
│   └── engagement/        # Giveaways, Game updates
└── scripts/               # Developer utilities, CI/CD, setup scripts
```

---

## Architectural Layers (The Deep Dive)

### 1. The Core Backbone (`core/` & `config/`)
*The foundation that keeps the bot breathing.*
- **Initialization & Factory (`bot.py`)**: Bootstraps the application, loading middleware, registering routers, and gracefully bringing up/down background tasks.
- **Global Error Handling**: A centralized interceptor for unhandled exceptions. Notifies the **Dev Group > Bot Errors/Console** topic with stack traces securely, while showing polite failure messages to end-users.
- **Middleware Pipeline**: Security-first approach. All incoming updates pass through early middlewares (Spam check, Global Ban check, Maintenance Mode).
- **Environment Management (`config/`)**: Strongly-typed configuration parsed using a library like Pydantic. Environment variables drive feature toggles and API integrations.

### 2. Database & Storage Layer (`database/`)
*Persistent memory and fast access.*
- **Async ORM**: (e.g., SQLAlchemy 2.0 or Tortoise ORM) to manage scalable, non-blocking asynchronous queries.
- **Connection Pooling**: Managing high concurrency against PostgreSQL (or equivalent).
- **Migrations**: Automated revision tracking (e.g., Alembic) ensuring smooth, conflict-free table updates.
- **Repository Pattern**: Database operations are abstracted away from Telegram handles. E.g., `UserRepository.get_user(id)` instead of writing SQL inside message handlers.

### 3. State Management (`state/`)
*Remembering where the user is in a multi-step process.*
- **Finite State Machine (FSM)**: Manages complex conversations (e.g., The Owner's initial setup wizard, or crafting a multi-part post).
- **Transient Memory**: Redis-backed cache for high-speed, temporary data like rate-limiting counters, active UI pagination states, and callback payload memory.
- **Session Locking**: Prevents race conditions when a user mashes buttons concurrently.

### 4. Presentation & UI Layer (`ui/`)
*Standardizing how the bot looks and feels.*
- **Template Engine**: Reusable Markdown/HTML formatting templates for consistency across all messages.
- **Component Library**:
  - `MenuBuilder`: Standardized utility for generating complex Inline Keyboards (buttons).
  - `PaginationManager`: Handles infinite scrolling menus for things like the Admin Action Queue or CXP leaderboards.
  - `ConfirmationDialog`: Reusable components for destructive actions (e.g., "Are you sure you want to ban this user? [Yes] / [No]").
- **Scoped Rendering**: UI builders natively check the `permissions` module before rendering. E.g., The "Settings" menu renders differently if the user is a Mod vs. an Admin.

### 5. Essential Feature Modules (`modules/`)
*The distinct capabilities of the bot, isolated for safety.*
- **`permissions/`**: The absolute **Chain of Trust**. The Owner is root and delegates tokenized access to Admins/Mods. Administers scoped DM panels.
- **`routing/`**: The Shared Inbox. Dynamically reads DMs and translates them into **Support Group Topics**. Maintains bi-directional syncing of messages, media, and edits.
- **`cxp/`**: The Reaction Economy. Calculates Base CXP (posting), Weighted CXP (reactions), tracks positive/negative emojis, and maintains leveling/leaderboards.
- **`moderation/`**: Spam heuristics engine, Captcha generation/verification, and administrative execution tools (`/ban`, `/mute`).
- **`content/`**: DM-based visually rich composer for sending perfectly formatted official broadcasts to the **Channel**.
- **`ai/`**: Retrieval Augmented Generation (RAG) system loaded with game lore and FAQs. Functions in DMs for private assist and the Public Group for community answers.
- **`engagement/`**: Webhook listeners to convert game server triggers into engaging community notifications. Manages automated Giveaways.

### 6. External Services (`services/`)
*Connecting out to the rest of the world.*
- **Game Server Adapter**: Polling or listening via Webhook for *The Clean Network* database changes/events.
- **GitHub Adapter**: Receives Webhooks on PRs, creates cleanly formatted summaries, and routes them to the **Dev Group > GitHub Integration** topic.
- **LLM Gateway**: Shared API client (e.g., OpenAI/Anthropic) ensuring the AI module respects rate limits and token budgets.

---

## Central Hubs Map (Groups & Channels)
The bot isolates communication across these distinct nodes:
- **Public Group**: 
  - *Main Discussion*
  - *AI Public Chat Topic*
  - *Giveaway/Event Topic*
- **Channel**: Official posts (fed by `content/` module).
- **Admin Group**: 
  - *Admin/Mod Actions Log*
  - *Admin Chat*
  - *Action Queue* (Pending reviews)
- **Dev Group**: 
  - *Game Info Logging*
  - *Bot Errors/Console*
  - *GitHub Integration*
- **Support Group**: 
  - *User Tickets (Shared Inbox Topic per User)*
- **Log Group**: 
  - *Global Audit Trails (Segmented by topics)*

---

## Infrastructure & Deployment
*Automating the boring stuff.*
- **Dependency Management**: Utilizing **Poetry** for strict, reproducible dependency resolution and virtual environments.
- **Hosting & Deployment**: Natively deployed to **Railway**, leveraging its built-in containerization, Postgres/Redis provisioning, and continuous deployment from GitHub without the overhead of maintaining custom Dockerfiles.
- **CI/CD Pipeline**: GitHub Actions hooked into linting (`ruff`, `black`, `mypy`) and unit testing for core modules before merging.
- **Health Checks & Uptime**: Handled natively by **Railway**. If the main bot process fatals or hangs, the container manager automatically restarts it, eliminating the explicit need for manual routing webhooks or third-party pinging services.
