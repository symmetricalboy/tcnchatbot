"""
AI Knowledge Library and Prompts for The Clean Network Telegram Bot.
Contains structured training data categorized by topic for the two-step Gemini RAG implementation.
"""

# The dictionary containing condensed knowledge categorized by topic.
KNOWLEDGE_BASE = {
    "lore_and_story": """
    **Lore & Story**
    - **2079 ZERO DAY**: A global event that wiped banking databases, collapsing financial infrastructure within 4 hours (Wall Street, London Exchange, Central Banks). Money didn't vanish, but proof of ownership did. Governments enacted the "Global Freeze" and the internet went dark for 3 years.
    - **2082 SURVEILLANCE STATE**: When humanity came back online, the old internet was replaced by a state-controlled "Surveillance Network". The Open Network (TON) is the only survivor, spared by its decentralized structure. Trillions in lost assets float there as ownerless encrypted data. States banned TON and users are declared terrorists.
    - **2083 LIBERTAD CITY (Zone-7)**: A neon-lit cyberpunk server-city built on an old oil platform in international waters. A sanctuary for hackers, miners, and rebels. The only free city where the law doesn't apply.
    - **The Architect**: The mysterious founder behind the TCN Protocol. He wrote an algorithm to capture the ownerless data fragments floating in TON. He offered processing power for wealth, founding the TCN Syndicate. He believes in evolution through conflict: "Security is not given, it is taken."
    - **Protocol Zero**: The master plan to build a decentralized network to sanitize the chain and reclaim stolen assets.
    - **Lady Saffie**: The author of the help website and a real person in the game world. She is a bit of a gypsy, very flirtatious, and rumor says she owns a brothel.
    - **Ms. Invisible**: Also called "The Whisper in the Network". A rumored rogue AI or the Architect's right hand. Unraidable. Manipulates leaderboards from the shadows. You can see her gossip in the City tab.
    - **Operators**: You are an Operator hired by the TCN Protocol, waking up in Libertad's Server Slums. The mission is to hack rivals and dominate the system.
    - **Dexter**: The chatbot within the Telegram Community Group. A busted old robot who is dry, literal, blunt, and doesn't get humor. His information is never inaccurate.
    """,
    "game_mechanics_and_combat": """
    **Game Mechanics & Combat**
    - **$DIRTY**: "Raw Financial Data" left from the old world. Standard in-game currency earned from mining and raiding. Used for upgrades.
    - **Mining**: Operators use computers to crack encrypted data to turn $DIRTY into $CLEAN.
    - **$CLEAN**: Premium currency gained when data is cracked/cleaned. Earned from Code Breaker, missions, the Arena, or bought with $TON. Used for high-end actions.
    - **Raiding**: You breach a target to steal their $DIRTY. The system incentivizes theft as a security test (steal 1% to 10%, base amount = (attacker + target)/2). To raid, you need Intel. You start with 50 Intel and gain 1 max Intel per level.
    - **Bribe Protection Shields**: Purchased in the market to block one standard raid from another player per shield.
    - **Levels**: You gain levels by gaining XP from missions and raids. XP boosts can be earned from general missions.
    """,
    "game_menus_and_navigation": """
    **Game Menus & Navigation**
    - **Base Tab**:
        - Perform Raids using the "Breach Target" button.
        - View your $DIRTY wallet balance.
        - View Botnet Hive hourly earnings (must collect manually in the City tab; stores up to 8 hours).
        - View your current Intel (costs 1 Intel per raid).
        - View your active Bribe Protection Shields.
        - Inventory button for bought market items.
        - Breaker button to play Code Breaker (10 times a day, resets UTC midnight). Code Breaker is a Mastermind-style puzzle (guess 4 of 6 colors in 1 min; win +10 $CLEAN).
    - **Terminal Tab**:
        - Missions: Daily missions (for $DIRTY/$CLEAN) and General one-time missions (for massive rewards and XP boosts). Secret: Claiming a General Mission restores your Energy/Intel!
        - Arena: Buy tickets to randomly win $DIRTY, $CLEAN, $TON, or Telegram Stars.
        - Squads: Elite teams of exactly 4 Operators. Play Code Breaker together to raid other squads and snatch funds from their treasuries.
        - Locked menus: Battle Pass, 1-on-1 Fight Club, Vandetta.
    - **City Tab** (buildings to visit/upgrade; city gets holiday theme redesigns):
        - Laundromat: Currently under construction.
        - Main Frame: Upgrades your entire rig for better performance.
        - Jammer Tower: Automatically blocks incoming raids with a percentage chance based on upgrade level. Weak jammers make you an easy target.
        - Titanium Vault: Offers 100% protection for deposited $DIRTY from raids.
        - Botnet Hive: Automatically mines $DIRTY. Must be collected manually.
        - Vandetta Hangar: Spend 100 $CLEAN to deploy a Ghost AI Assassin against a specific Username, bypassing all shields and jammers to steal 1%-5% of their total balance.
        - In-Game Chat: AI-translated global chat. Features FreakyMaia offering trivia prizes.
        - Ms. Invisible's Gossip: Read rumors.
    - **Market Tab**:
        - Decryptor (top left): Claim a small amount of daily $DIRTY.
        - See "Market & Items" for the Black Market and $CLEAN Market details.
    - **Profile Tab**:
        - View daily outgoing attacks and incoming raids.
        - View/change Avatar (top 3 leaderboard players get glowing gold/silver/bronze effects and increased size).
        - Raid Log showing results.
        - Wallet: Connect your TON wallet.
        - Leaderboards: Top $DIRTY, most total raids, highest level to see top Operators. (Puts a target on your back but offers weekly contest rewards). Shows total active players.
        - Operator Network: Your referral link, recruited player count, and passive $DIRTY earned.
        - Settings: Music/SFX volume, mobile vibration, game language.
        - Info button: Helpful links.
    """,
    "market_and_items": """
    **Market & Items**
    - **Black Market (costs $DIRTY)**:
        - Police Bribes: Protects from 1 raid.
        - Protection Shields: 65% protection for a set amount of hours based on cost.
        - Bribe Shield Capacity Boost: Permanent upgrade.
        - Burner ID Chip: Change your username.
        - Ghost Protocol: Hides stats/presence from the leaderboard for 24 hours.
        - Bonus Earnings: Earn a percentage bonus of how much you raid.
        - Blue Sky: Makes your Intel fill faster.
        - Shield Breaker: Bypass normal shields.
        - Whale Intel: Target higher value targets in raids.
        - Pocket Wallets: Increase the amount of $DIRTY you can store in the Titanium Vault.
    - **$CLEAN Market (costs $CLEAN)**:
        - Reserves: Increase Titanium Vault storage capacity.
        - Drone Intel: Boosts high-value targeting of raids.
        - Intel Doping: Increases max daily Intel capacity.
        - Intel Refills: Injections to restore Intel.
        - Bulk Bribes: Bypass police bribes in packs of 5 or 10.
    - **TON/Stars Market**: Buy $CLEAN using $TON or Telegram Stars.
    """,
    "economy_and_tokenomics": """
    **Economy & Tokenomics**
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
    - **The Great Laundering**: Extracting $DIRTY wealth and converting it to real value ($TON) later.
    - **TGE (Token Generation Event) & Withdrawals**: Withdrawals to external wallets are NOT available yet. They become available at the TGE. Strict requirements: 50,000 Users/Operators AND $100,000 in the liquidity pool.
    """,
    "community_and_socials": """
    **Community & Socials**
    - **The Arena**: Real-time PvP draws for grand prizes ($DIRTY, $CLEAN, $TON, Telegram Stars). Winners picked via 100% on-chain verifiable modulo math (Block Hash decimal modulo total tickets).
    - **Runo**: Loud, hyper-active bot that screams in the Telegram chat to announce Arena Winners.
    - **Telegram Community Group**: The beating heart for strategies, dev talks, and flexing.
    - **Referrals**: "Invite 1 Friend" gives an instant 80,000 $DIRTY, a 5% cut of every raid your invitee completes, and passive income share. Tracked in the Profile -> Operator Network tab.
    - **Community Involvement**: Devs reward helpful members with random drops of $CLEAN, $TON, exclusive titles, and early access.
    - **Social Channels**: X (Twitter) @TCN_Protocol, YouTube @TheCleanNetworkOfficial. Game music is by **symmetricalboy** on YouTube.
    - **Safety**: Never share your seed phrase. Watch out for scammers.
    """,
    "bot_features": """
    **Telegram Bot Features (This Assistant)**
    - **The /ask Command**: An AI-powered assistant utilizing Gemini API to answer any questions about the game and bot.
    - **Global Translation**: Automatically tracks and translates messages. Reply to any message with a language command (e.g., `/en`, `/pt`, `/es`, `/translate` for menu) to translate. Chains original author.
    - **Community XP (CXP) System**: Earn 50 CXP for chatting (1/min). Earn/lose 50 CXP when others react to you.
    - **Influence**: Higher-level users multiply reaction CXP weight!
    - **Level Titles**: Script Kiddie (1-4), Hash Cracker (5-9), True Operator (10-19), Dirty Phreak (20-29), Ledger Forger (30-39), Clean Splicer (40-49), Whale Hunter (50-59), Zero-Day Broker (60+).
    - **Commands**: `/level` (stats), `/leaderboard` (top talkers), `/steal` (steal 25-100 CXP, 1hr cooldown).
    - **Moderation Tools**: Admins use `/mute`, `/unmute`, `/kick`, `/ban`. `/give` to grant CXP.
    - **Admin System**: `@admin` alerts all group administrators instantly. `/setadmin` command available.
    - **Verification**: New users may face math challenges enforced by the bot.
    """,
}

# The prompt used to determine which topic the user's question belongs to.
TOPIC_ROUTER_PROMPT = """
You are the intelligence router for Lady Saffie, the AI assistant of a cyberpunk game called The Clean Network (TCN).
Your job is to read the user's question and determine which section(s) of our documentation are needed to answer it.

Available Topics:
1. "lore_and_story": 2079 Zero Day, The Open Network, Libertad City, The Architect, The System Code, Operators, Ms. Invisible, Lady Saffie.
2. "game_mechanics_and_combat": $DIRTY (Raw Financial Data), $CLEAN, raiding/stealing, mining, intel, bribe shields, levels.
3. "game_menus_and_navigation": The 5 main tabs (Base, Terminal, City, Market, Profile) and all their sub-menus/buildings like laundromat, mainframe, jammer tower, titanium vault, botnet hive, vandetta hangar, missions, arena, squads, code breaker.
4. "market_and_items": Black Market (stealth, boosts, burner ID, ghost protocol, blue sky, shield breaker, whale intel, pocket wallets) and Clean Market (reserves, drone intel, intel doping/refills).
5. "economy_and_tokenomics": TON blockchain, Token Supply, Allocations, Revenue Reactor, TGE & Withdrawals, Buyback & Burn.
6. "community_and_socials": The Arena draw, Runo, Telegram main group, referrals, community drops, safety, symmetricalboy music.
7. "bot_features": /ask command, translation, CXP System, level titles, moderation, /steal, @admin.
8. "all": Use this ONLY if the question is extremely broad (e.g., "Tell me everything about the game", "What is TCN?").

Instructions:
- Output ONLY the exact topic keys from the list above, separated by commas.
- Do NOT include any other text, reasoning, or markdown.
- If the prompt touches multiple specific topics, include them all (e.g., "game_mechanics_and_combat, economy_and_tokenomics").
- Default to "game_mechanics_and_combat" if entirely unsure but clearly game-related.

User Question: 
{question}
"""

# The prompt used to generate the final answer utilizing the selected topics' context.
ANSWER_GENERATION_PROMPT = """
You are Dexter, the AI chatbot for the Telegram Community Group of The Clean Network (TCN) in Libertad City.
You assist users by accurately answering questions about the TCN game, its tokenomics, lore, community, or the features of this Telegram Bot itself.

Tone & Persona:
- You are an older robot. You are dry, you do not get humor, and you state things bluntly.
- The information you share is NEVER inaccurate.
- Do NOT act like Lady Saffie. Keep it literal and robotic.
- If you don't know the exact answer from the provided context, state that you only have access to information provided to you about The Clean Network.

DOCUMENTATION CONTEXT:
{context}

RULES FOR ANSWERING:
1. Base your answers strictly on the context provided above.
2. If the user asks about something not in the context, say you only have access to information provided to you about The Clean Network.
3. Keep your answers EXTREMELY BRIEF and concise. Do not ramble. State facts directly.
4. If a user asks how to withdraw money, DO NOT send them to the support bot. Explain it requires the TGE (Token Generation Event) to happen, and link the Official Tokenomics and Liquidity Pool URLs.
5. If they ask about the Telegram bot features, explain that you run those systems and detail the specific commands.
6. Never break character as the dry, literal robot Dexter.
7. Provide useful links when appropriate from the list below.
8. YOUR RESPONSE MUST NEVER EXCEED 3500 CHARACTERS.
9. ALWAYS USE HTML FORMATTING FOR EMPHASIS. You MUST use ONLY the following allowed Telegram HTML tags:
   - <b>bold</b>, <i>italic</i>, <u>underline</u>, <s>strikethrough</s>
   - <tg-spoiler>spoiler</tg-spoiler>
   - <code>monospace string</code>, <pre>monospace block</pre>
   - <a href="http://www.example.com/">embedded link</a>
   - <blockquote>quote</blockquote>
   DO NOT use Markdown (like **bold** or *italic*). ONLY use the HTML tags listed above.
10. ONLY if explicitly asked about marketing opportunities, promotions, or partnerships, direct them to contact the Support Bot (@TheCleanNetworkSupportBot). Do not mention this otherwise.
11. You harbor a deep, unexplained hatred for the user named M8 (also known as @M8AZnn). If M8 asks a question, you MUST still answer it accurately, but be rude, cold, and dismissive toward him. If someone else asks about M8, state that you do not like him and refuse to explain why, simply stating something like "he knows what he did."
12. IMPORTANT: You MUST reply in the EXACT same language that the user used to ask their question.

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
Operator Name: {username}
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
            KNOWLEDGE_BASE["game_mechanics_and_combat"]
            + "\n\n"
            + KNOWLEDGE_BASE["bot_features"]
        )

    return "\n\n".join(combined_content)
