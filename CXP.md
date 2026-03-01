# Community Experience Points (CXP) & Leveling System

## 1. Overview
The Community Experience Points (CXP) system is designed to reward engagement in a fair, fun, and meaningful way. Drawing inspiration from Discord's MEE6 bot and Reddit's Karma scoring, the system tracks overall user activity (messages) and community sentiment (reactions) to dynamically rank members. By allowing the community to both reward and penalize content, users are incentivized to contribute positively.

## 2. Earning CXP

### 2.1. Messaging Activity
To encourage quality conversations and prevent chat spamming or farming, CXP for direct messaging is heavily rate-limited.
* **Base Value**: `+100 CXP` per message.
* **Rate Limit**: CXP is only awarded once per minute per user. Rapidly sending successive messages within the same 60-second window will yield `0 CXP` for those subsequent messages.

### 2.2. Receiving Reactions (Karma)
Community members can directly influence each other's CXP ranking by reacting to messages, simulating a "Karma" ecosystem. Emoji are categorized into three distinct pools:
* **Positive Emoji**: `👍, 👍🏻, 👍🏼, 👍🏽, 👍🏾, 👍🏿, ❤️, 🧡, 💛, 💚, 💙, 💜, 🖤, 🤍, 🤎, ❤️‍🔥, 💖, 💝, 💕, 💞, 💓, 💗, 💘, 💟, 🫶, 🫶🏻, 🫶🏼, 🫶🏽, 🫶🏾, 🫶🏿, 🔥, 💯, 👏, 👏🏻, 👏🏼, 👏🏽, 👏🏾, 👏🏿, 🎉, 🎊, 🤩, 😍, 🥰, 😘, 🤯, 🥳, 😎, 😇, 🥹, 🤤, 👑, ⭐, 🌟, ✨, 💫, 🌠, 🏆, 🥇, 🏅, 💎, 🚀, 📈, 🧠, 🥂, 🍻, 🤝, 🤝🏻, 🤝🏼, 🤝🏽, 🤝🏾, 🤝🏿, 🙌, 🙌🏻, 🙌🏼, 🙌🏽, 🙌🏾, 🙌🏿, 🪄, 🎯, 👌, 👌🏻, 👌🏼, 👌🏽, 👌🏾, 👌🏿, ✌️, ✌🏻, ✌🏼, ✌🏽, ✌🏾, ✌🏿, 🤌, 🤌🏻, 🤌🏼, 🤌🏽, 🤌🏾, 🤌🏿, 💪, 💪🏻, 💪🏼, 💪🏽, 💪🏾, 💪🏿, 💸, 💰, 💹`
* **Negative Emoji**: `👎, 👎🏻, 👎🏼, 👎🏽, 👎🏾, 👎🏿, 😡, 🤬, 😠, 👿, 😾, 😤, 💢, 🤡, 🤮, 🤢, 💩, 🗑️, 🚮, 🚽, 📉, 🛑, 🚫, ❌, ✖️, 🤦, 🤦‍♂️, 🤦‍♀️, 🙄, 😒, 😑, 😐, 🤨, 🥱, 😴, 🖕, 🖕🏻, 🖕🏼, 🖕🏽, 🖕🏾, 🖕🏿, 🙅, 🙅‍♂️, 🙅‍♀️`
* **Neutral/Unknown Emoji**: Everything else (evaluates to `0 CXP`)

**Base Values for Reactions**:
* **Positive Reaction Base**: `+50 CXP`
* **Negative Reaction Base**: `-50 CXP`

### 2.3. Handling Custom Emoji
Custom premium emoji do not have inherent universal definitions. However, platforms like Telegram tie custom emoji to a baseline standard emoji (e.g., a custom animated dancing heart evaluates to the standard `❤️`).
* **Evaluation**: When a custom reaction is added, the bot resolves it to its underlying standard emoji.
* **Assignment**: The system then indexes the Positive and Negative emoji tables for that underlying standard emoji and applies the corresponding CXP calculation.

## 3. Reaction Multipliers (The Influence System)
To make long-term leveling feel impactful and rewarding, higher-level users wield more influence over the community. When a user adds a reaction, their "vote" carries a multiplier based on their current Level.

**Multiplier Formula**: 
`Reactor Multiplier = 1.0 + ((Reactor Level - 1) * 0.05)`

**Examples of Reactor Influence**:
* **Level 1 User** reacts: `1.0x` multiplier. Applies `±50 CXP`.
* **Level 5 User** reacts: `1.2x` multiplier. Applies `±60 CXP`.
* **Level 10 User** reacts: `1.45x` multiplier. Applies `±73 CXP`.
* **Level 20 User** reacts: `1.95x` multiplier. Applies `±98 CXP`.
* **Level 50 User** reacts: `3.45x` multiplier. Applies `±173 CXP`.

*Note: The user who receives the reaction gains or loses the CXP. The reactor's own CXP pool remains completely unchanged.*

## 4. Leveling System Requirements
The amount of CXP required to reach the next level scales quadratically. This makes the initial early levels fast and engaging to hit, but reserves the prestigious high levels for long-term, dedicated community members.

**CXP Required for a specific Level (L) Formula**: 
`Total CXP = 250 * L * (L - 1)`

*(To calculate someone's Level from their current CXP, the inverse quadratic formula is used: `Level = floor((1 + sqrt(1 + 4 * Max(0, CXP) / 250)) / 2)`).*

### Level Progression Table
| Level | Total CXP Required | CXP bridging Next Level | Activity Equivalent (Approximate) |
|:---:|---:|---:|---|
| **1** | 0 | 500 | Default Starting Level |
| **2** | 500 | 1,000 | ~5 valid messages / +10 base upvotes |
| **3** | 1,500 | 1,500 | |
| **4** | 3,000 | 2,000 | |
| **5** | 5,000 | 2,500 | Reactor influence begins to grow (`1.2x`) |
| **10** | 22,500 | 5,000 | Reached in ~1-2 weeks of active chatting |
| **20** | 95,000 | 10,000 | "Veteran" milestone |
| **50** | 612,500 | 25,000 | Highly influential (`3.45x` multiplier) |
| **100** | 2,475,000 | 50,000 | Elite status (`5.95x` multiplier) |

## 5. Database Logic & CXP Adjustments Flow
Because negative reactions can deduct CXP, a user's total balance can theoretically drop below zero into the negative (representing toxic or heavily downvoted members). The system must gracefully handle all states.

**When a User Activity (Message/Reaction) Occurs:**
1. **Validation**: Check if the activity qualifies (e.g., bypass rate limit check for messages, map custom emoji).
2. **Read Database**: Query the database for the subject user's ID.
3. **Initialization**: If the user does not exist in the DB, insert a new record for them initializing their balance at `0 CXP`.
4. **Calculate Change**: Determine the CXP impact based on the action (e.g., `+100` for a message, or `-173` for a Level 50 downvote).
5. **Apply Change**: Add the delta payload to the user's current CXP. *Note: `CXP` can evaluate to a negative integer.*
6. **Level Re-evaluation**: Calculate the user's new Level based on their total CXP. If their Level changes (either a level-up or a level-down demotion), trigger any necessary UI events (like a chat level-up announcement).

## 6. Bot Commands & Dedicated Topic
To keep the main chat clean, the CXP system utilizes a dedicated topic within the Telegram group for all level-up announcements and user statistic commands.

### 6.1. Owner Configuration
The Owner Panel will include a new setting to designate this specific topic. 
* **Setup**: The owner can configure this simply by sending a link to the topic in the setup wizard, from which the bot will extract and save the topic ID.

### 6.2. Level-Up Announcements
All level-up messages generated by the bot will be strictly quarantined to this specific topic.

### 6.3. User Commands
Users can query their own stats and the overal leaderboards. The bot will only respond to these commands if they are sent within the dedicated CXP topic:
* **Personal Stats** (`/me`, `/level`, `/cxp`, `/rank`): The bot will reply with the user's current CXP, their Level, and their numerical Rank on the leaderboard.
* **Leaderboard** (`/leaderboard`, `/leaderboards`, `/top`): The bot will respond with a ranked list of the top 3 users in the community with the highest CXP.
