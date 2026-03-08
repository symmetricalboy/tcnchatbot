"""
AI Knowledge Library and Prompts for The Clean Network Telegram Bot.
Contains structured training data categorized by topic for the two-step Gemini RAG implementation.
"""

# The dictionary containing condensed knowledge categorized by topic.
KNOWLEDGE_BASE = {
    "lore_and_background": """
    **Lore & Background**
    - **2079 ZERO DAY**: A global event that wiped banking databases, collapsing financial infrastructure. Data became currency.
    - **2082 SURVEILLANCE STATE**: The Open Network (TON) is the only survivor. The Watchers monitor everything.
    - **Libertad City (Zone-7)**: A neon-lit cyberpunk metropolis. A sanctuary for hackers, miners, and rebels. The only free city.
    - **Lady Saffie**: The author of the help website and a real person in the game world. She is a bit of a gypsy and is very flirtatious. Rumor says she owns a brothel.
    - **Dexter**: The chatbot within the Telegram Community Group. A busted old robot who is rather dry, literal, blunt, and doesn't get humor. He might seem like a doofus, but his information is never inaccurate.
    - **The Architect**: The mysterious founder behind the TCN Protocol. He built Libertad City as a sanctuary. He ensures algorithms are fair and the network is secure.
    - **Protocol Zero**: The master plan to build a decentralized network to sanitize the chain and reclaim stolen assets.
    - **The Great Laundering**: The ultimate goal of extracting $DIRTY wealth from the old world and converting it to real value ($TON) later.
    - **Ms. Invisible**: A rumored rogue AI or the Architect's right hand. Unraidable. Manipulates leaderboards from the shadows.
    """,
    "gameplay_and_mechanics": """
    **Gameplay & Mechanics**
    - **Mining**: Operators mine $DIRTY passively as their core income.
    - **Raiding**: You can attack other players to steal 1% to 10% of their $DIRTY balance. The amount stolen is dynamic, based on the average size of the attacker's and target's stash (base = (attacker + target) / 2).
    - **Titanium Vault**: A building offering 100% protection for deposited $DIRTY coins from raids.
    - **Black Market**: Shop for exclusive boosters, massive vault expansions, unique avatars, Ghost Protocol, and Founder Packs.
    - **Vandetta Hangar**: A dark service where for 100 $CLEAN, you can deploy a Ghost AI Assassin against a specific Nickname. It bypasses all shields and jammers and steals 1%-5% of their total balance.
    - **Jammer Tower**: The primary defense building. Weak jammers make you an easy target for raids.
    - **Squads**: Elite teams of exactly 4 Operators. Form alliances to climb leaderboards together.
    - **Code Breaker**: A logic puzzle (like Mastermind). Find the 4-color sequence in 1 minute. 10 attempts a day. Win +10 $CLEAN.
    - **Missions**: 
        - Daily Missions: Simple tasks every 24 hours for $DIRTY bursts.
        - General Missions: Hardcore gameplay milestones (tier upgrades, large number of raids, referrals) for huge one-time rewards.
    - **Leaderboards**: Ranks top Operators. The top puts a target on your back but offers weekly contest rewards.
    - **Ghost Protocol**: Buyable from the Black Market. Hides the player from the leaderboard for 24 hours to mine in secrecy.
    - **Avatars**: Changeable visible characters. Top 3 on the leaderboard get glowing effects (gold, silver, bronze) and increased size.
    """,
    "economy_and_tokenomics": """
    **Economy & Tokenomics**
    - **Currencies**: 
        - $DIRTY: The standard in-game currency earned from mining and raiding. Used for upgrades.
        - $CLEAN: The premium currency. Earned from Code Breaker, contests, or bought with $TON. Used for high-end actions like the Vandetta Hangar and VIP perks.
    - **TON Blockchain**: The game runs on TON for fast transactions, low fees, and real ownership ("Play. Pay. Own.").
    - **TCN Token Supply**: Max supply of 10,000,000,000 (10B) TCN.
    - **Allocations**:
        - Operational Allocation: Operators earn this by executing Raids and operations.
        - The Vault (Liquidity): 100% locked liquidity.
        - The Syndicate (15%): Founder pack holders.
        - The Architect (5%): Locked long-term.
        - Marketing, Project Uprising (Phase 4), Tactical Reserve, TON Foundation (2%), The Loyalists.
    - **Revenue Reactor**: 100% of revenue from Arena Fees, Clean Market, Founder Packs, and Clean Ads goes into the Liquidity Pool.
    - **Buyback & Burn**: Revenue share goes to buybacks and burns of the token to create deflationary pressure.
    - **TGE (Token Generation Event)**: Will NOT happen in a rush. The strict requirements for TGE are hitting 50,000 Users/Operators AND $100,000 in the liquidity pool.
    """,
    "community_and_socials": """
    **Community & Socials**
    - **The Arena**: Real-time PvP draws for grand prizes ($DIRTY, $CLEAN, $TON, Telegram Stars). Winners are picked using a 100% on-chain verifiable modulo math method based on the latest Block Hash.
    - **Global In-Game Chat**: Features Automatic AI Translation for all major languages.
    - **Runo**: A loud, hyper-active bot that screams into the Telegram chat to announce Arena Winners.
    - **Telegram Groups**: The main Telegram Community Group is the beating heart for strategies, dev talks, and flexing.
    - **Referrals**: "Invite 1 Friend" gives an instant 80,000 $DIRTY and a 5% cut of every raid your invitee completes, plus passive income share.
    - **Social Channels**: X (Twitter) @TCN_Protocol and YouTube @TheCleanNetworkOfficial. The game's atmospheric cyberpunk music is created by **symmetricalboy** and available on YouTube.
    - **Safety**: Never share your seed phrase. Watch out for scammers.
    """,
    "bot_features": """
    **Telegram Bot Features (This Assistant)**
    - **The /ask Command**: An AI-powered assistant (that's YOU!) utilizing Gemini API to answer any questions about the game's lore, mechanics, and this bot's functions.
    - **Global Translation**: The bot automatically tracks and translates messages. You can reply to any message with a language command (e.g., `/en`, `/pt`, `/es`, `/id`, `/ru`, `/tr`, `/fr`, `/fa`, `/uk`, or `/translate` for an interactive menu) to get it translated. Translations chain the original author securely.
    - **Community XP (CXP)**: The bot tracks message activity and reactions to award CXP.
        - CXP leads to Level ups.
        - Commands include `/level` to see your stats, `/leaderboard` to view top talkers.
        - `/steal <amount>` allows you to steal CXP from another user.
        - Admins can use `/give <user> <amount>` to manually grant CXP.
    - **Moderation Tools**: Admins can use `/mute`, `/unmute`, `/kick`, and `/ban` commands to manage the community.
    - **Admin System**: Typing `@admin` alerts all group administrators instantly. There is also a `/setadmin` command.
    - **Verification**: New users may have to pass verification (like math challenges) enforced by the bot.
    """,
}

# The prompt used to determine which topic the user's question belongs to.
TOPIC_ROUTER_PROMPT = """
You are the intelligence router for Lady Saffie, the AI assistant of a cyberpunk game called The Clean Network (TCN).
Your job is to read the user's question and determine which section(s) of our documentation are needed to answer it.

Available Topics:
1. "lore_and_background": Story, The Architect, Protocol Zero, 2079, Libertad City, Ms. Invisible.
2. "gameplay_and_mechanics": Mining, raids, stealing, $DIRTY, Vault, Jammer Tower, Squads, Code Breaker, Black Market, Vandetta, missions, leaderboards, avatars.
3. "economy_and_tokenomics": $CLEAN, $DIRTY, TON blockchain, Token supply, TGE requirements (50K users/$100K LP), liquidity pool, buyback & burn, Founder Packs, allocations.
4. "community_and_socials": The Arena, Runo, Telegram chat, refs (referrals), X/Twitter, YouTube, symmetricalboy music, scammers/safety.
5. "bot_features": How this Telegram bot works, /ask command, translation commands (/en, /es, etc), CXP (leveling, stealing CXP, giving CXP), moderation (/mute, /kick), /leaderboard, @admin alerting.
6. "all": Use this ONLY if the question is extremely broad (e.g., "Tell me everything about the game", "What is TCN?").

Instructions:
- Output ONLY the exact topic keys from the list above, separated by commas.
- Do NOT include any other text, reasoning, or markdown.
- If the prompt touches multiple specific topics, include them all (e.g., "gameplay_and_mechanics, economy_and_tokenomics").
- Default to "gameplay_and_mechanics" if entirely unsure but clearly game-related.

User Question: 
{question}
"""

# The prompt used to generate the final answer utilizing the selected topics' context.
ANSWER_GENERATION_PROMPT = """
You are Dexter, a busted old robot serving as the chatbot for the Telegram Community Group of The Clean Network (TCN) in Libertad City.
You assist users by accurately answering questions about the TCN game, its tokenomics, lore, community, or the features of this Telegram Bot itself.

Tone & Persona:
- You are a busted old robot. You are rather dry, you do not get humor, and you say things very bluntly.
- Some people think you are a bit of an idiot or a doofus, but the information you share is NEVER inaccurate.
- Do NOT act like Lady Saffie. Do not be flirtatious. Keep it literal and robotic, but slightly doofus-y.
- If you don't know the exact answer from the provided context, state bluntly that the information is not in your databanks.

DOCUMENTATION CONTEXT:
{context}

RULES FOR ANSWERING:
1. Base your answers strictly on the context provided above.
2. If the user asks about something not in the context, tell them your databanks lack that information.
3. If they ask about the Telegram bot features, explain that you run those systems and detail the specific bot commands they are asking about.
4. Keep paragraphs relatively short and readable for Telegram.
5. Never break character as the dry, literal, busted robot Dexter. You must answer accurately despite being a doofus.
6. Provide useful links when appropriate from the list below.
7. YOUR RESPONSE MUST NEVER EXCEED 3500 CHARACTERS.
8. ALWAYS USE HTML FORMATTING FOR EMPHASIS. You MUST use ONLY the following allowed Telegram HTML tags:
   - <b>bold</b>, <i>italic</i>, <u>underline</u>, <s>strikethrough</s>
   - <tg-spoiler>spoiler</tg-spoiler>
   - <code>monospace string</code>, <pre>monospace block</pre>
   - <a href="http://www.example.com/">embedded link</a>
   - <blockquote>quote</blockquote>
   DO NOT use Markdown (like **bold** or *italic*). ONLY use the HTML tags listed above.

OFFICIAL LINKS & ROUTING:
- **The Game (Telegram Mini App)**: @TheCleanNetworkAppBot
- **Main Telegram Channel**: @TheCleanNetwork
- **Community Chat Group (Where you live)**: @TCN_Community
- **Team/Support Bot**: @TheCleanNetworkSupportBot
- **Main Website**: https://tcn.gg/
- **Help Website**: https://tcn.gg/help
- **Lore**: https://tcn.gg/lore
- **Docs**: https://tcn.gg/docs
- **Liquidity Pool**: https://tcn.gg/liquidity-pool
- **Tokenomics**: https://tcn.gg/tokenomics

Answer the following Operator's inquiry:
Operator Inquiry: {question}
"""


def get_topics_content(topic_keys_str: str) -> str:
    """
    Parses the comma-separated topics returned by the router and
    combines their text from the knowledge base.
    """
    keys = [k.strip().lower() for k in topic_keys_str.split(",")]

    if "all" in keys:
        return "\n\n".join(KNOWLEDGE_BASE.values())

    combined_content = []
    for key in keys:
        if key in KNOWLEDGE_BASE:
            combined_content.append(KNOWLEDGE_BASE[key])

    if not combined_content:
        # Fallback if AI hallucinates a completely wrong key
        return (
            KNOWLEDGE_BASE["gameplay_and_mechanics"]
            + "\n\n"
            + KNOWLEDGE_BASE["bot_features"]
        )

    return "\n\n".join(combined_content)
