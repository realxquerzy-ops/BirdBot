import os

import discord
from discord.ext import commands

from db import Database

# --- VERİTABANI BAĞLANTISI (PostgreSQL - Railway) ---
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ HATA: DATABASE_URL bulunamadı! Lütfen Railway PostgreSQL değişkenini ekleyin.")
    exit(1)

db = Database(DATABASE_URL)

# Tabloları Oluşturuyoruz
db.execute('''CREATE TABLE IF NOT EXISTS inventories (
    guild_id BIGINT,
    user_id BIGINT,
    birds TEXT,
    PRIMARY KEY (guild_id, user_id)
)''')

db.execute('''CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id BIGINT PRIMARY KEY,
    channel_id BIGINT
)''')

db.execute('''CREATE TABLE IF NOT EXISTS pip_claims (
    guild_id BIGINT,
    user_id BIGINT,
    claimed BOOLEAN,
    PRIMARY KEY (guild_id, user_id)
)''')

db.execute('''CREATE TABLE IF NOT EXISTS achievements (
    guild_id BIGINT,
    user_id BIGINT,
    achievements TEXT,
    PRIMARY KEY (guild_id, user_id)
)''')

db.execute('''CREATE TABLE IF NOT EXISTS birds_data (
    name TEXT PRIMARY KEY,
    sticker_id BIGINT,
    weight REAL,
    value REAL
)''')

db.execute('''CREATE TABLE IF NOT EXISTS birdpass (
    guild_id BIGINT,
    user_id BIGINT,
    xp REAL DEFAULT 0,
    claimed_level INTEGER DEFAULT 1,
    PRIMARY KEY (guild_id, user_id)
)''')

db.execute('''CREATE TABLE IF NOT EXISTS daily_claims (
    guild_id BIGINT,
    user_id BIGINT,
    last_claim DATE,
    PRIMARY KEY (guild_id, user_id)
)''')

db.execute('''CREATE TABLE IF NOT EXISTS powerups (
    guild_id BIGINT,
    user_id BIGINT,
    powerup TEXT,
    qty INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, user_id, powerup)
)''')

db.execute('''CREATE TABLE IF NOT EXISTS birdcoin (
    guild_id BIGINT,
    user_id BIGINT,
    balance REAL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
)''')

db.execute('''CREATE TABLE IF NOT EXISTS battle_log (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT,
    attacker_id BIGINT,
    defender_id BIGINT,
    winner_id BIGINT,
    attacker_birds TEXT,
    defender_birds TEXT,
    stolen_birds TEXT,
    created_at TIMESTAMP DEFAULT NOW()
)''')

# Sorgu hızı için indeksler
db.execute("CREATE INDEX IF NOT EXISTS idx_inventories_guild ON inventories (guild_id)")
db.execute("CREATE INDEX IF NOT EXISTS idx_inventories_user ON inventories (user_id)")
db.execute("CREATE INDEX IF NOT EXISTS idx_achievements_guild ON achievements (guild_id)")
db.execute("CREATE INDEX IF NOT EXISTS idx_pip_claims_guild ON pip_claims (guild_id)")

# --- SABİT KUŞLARI VERİTABANINA YÜKLE ---
default_birds = [
    ("Bird", 1539912459333140591, 30.0, 1),
    ("Good Bird", 1539732798217261186, 22.0, 2),
    ("Fat Bird", 1539941434004738128, 13.0, 3.6),
    ("Chick", 1540105760409788477, 9.0, 5.4),
    ("Yellow Bird", 1540087019357736960, 7.0, 6.3),
    ("Scarlet Mascow", 1540398790609997886, 5.5, 7.1),
    ("Alpha Bird", 1539935042027913296, 4.5, 8.0),
    ("Cool Bird", 1540421746895757412, 3.5, 9.0),
    ("Angry Bird", 1540101590688465037, 2.5, 10.0),
    ("Unknowmyt Bird", 1540424973368299560, 2.0, 11.5),
    ("Golden Bird", 1539980651283877908, 1.5, 13.2),
    ("Rainbow Bird", 1540114645132648478, 0.8, 19.6),
    ("Tennis Bird", 1540321518440161360, 0.4, 26.0),
    ("Duolingo Bird", 1548026648258158593, 0.3, 30.0),
    ("Bird 618", 1540321587780124693, 0.2, 35.0),
    ("Radioactive Bird", 1540372078660952175, 0.1, 50),
    ("Caseoh Bird", 1548030264167505920, 0.05, 75)
]

for bird in default_birds:
    db.execute("""
        INSERT INTO birds_data (name, sticker_id, weight, value) 
        VALUES (%s, %s, %s, %s) 
        ON CONFLICT (name) DO NOTHING
    """, bird)

# --- GLOBAL VERİLER ---
BIRDS = db.get_all_birds()

BIRD_VALUES = {bird["name"]: bird["value"] for bird in BIRDS}
BIRD_VALUES_LOWER = {bird["name"].lower(): bird["value"] for bird in BIRDS}

WHITELISTED_USERS = [1469734369739538677]
RESOURCE_GUILD_IDS = [
    1511406716749611171,
    1539963070045093958,
    1540320958429265920
]

intents = discord.Intents.default()
intents.message_content = True
intents.presences = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

bot.presence_cache = {}

@bot.tree.error
async def on_tree_error(interaction: discord.Interaction, error: Exception):
    import traceback
    traceback.print_exc()
    try:
        if interaction.response.is_done():
            await interaction.followup.send("❌ Bir hata oluştu. Lütfen tekrar deneyin.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Bir hata oluştu. Lütfen tekrar deneyin.", ephemeral=True)
    except Exception:
        pass

@bot.event
async def on_presence_update(before, after):
    if before.status != after.status:
        print(f"[presence] {after} ({after.id}) -> {after.status} | bot: {after.bot}")
        bot.presence_cache[after.id] = after.status

@bot.event
async def on_ready():
    print(f"{bot.user} olarak giriş yapıldı ve PostgreSQL aktif!")
    print(f"[debug] intents: presences={bot.intents.presences} members={bot.intents.members} message_content={bot.intents.message_content}")

    for guild in bot.guilds:
        print(f"[debug] guild={guild.name!r} members=<{len(guild.members)}>")
    
    # Initialize presence cache with current member statuses
    count = 0
    for member in bot.get_all_members():
        bot.presence_cache[member.id] = member.status
        count += 1
    print(f"[debug] presence_cache initialized with {count} members")
    
    for member in bot.get_all_members():
        if member.id in bot.whitelisted_users:
            print(f"[debug] owner {member} status={member.status}")

    if os.path.exists("./commands"):
        for filename in os.listdir("./commands"):
            if filename.endswith(".py") and filename != "__init__.py":
                cog_name = f"commands.{filename[:-3]}"
                await bot.load_extension(cog_name)
                print(f"Modül yüklendi: {cog_name}")

    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} global komut senkronize edildi.")
    except Exception as e:
        print(f"Senkronizasyon hatası: {e}")

    # BirdBot'a tüm başarımları kilitle (leaderboard'larda görünmez, envanter gibi)
    games_cog = bot.get_cog("GamesCog")
    if games_cog and hasattr(games_cog, "ACHIEVEMENTS_LIST"):
        all_ach = list(games_cog.ACHIEVEMENTS_LIST.keys())
        for guild in bot.guilds:
            bot.db.save_achievements(guild.id, bot.user.id, all_ach)
        print(f"[achievements] BirdBot'a {len(all_ach)} başarım eklendi ({len(bot.guilds)} sunucu).")

bot.birds = BIRDS
bot.bird_values = BIRD_VALUES
bot.bird_values_lower = BIRD_VALUES_LOWER
bot.whitelisted_users = WHITELISTED_USERS
bot.resource_guild_ids = RESOURCE_GUILD_IDS
bot.spawn_states = {}
bot.server_settings = db.get_server_settings()
bot.db = db

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("❌ HATA: DISCORD_TOKEN bulunamadı! Lütfen Railway Variables kısmına ekleyin.")
else:
    bot.run(TOKEN)