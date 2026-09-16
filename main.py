import logging
import os
import random
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import discord
from discord.ext import commands

from db import Database

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    force=True,
    format="[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s",
)

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

db.execute('''CREATE TABLE IF NOT EXISTS guild_boosts (
    guild_id BIGINT PRIMARY KEY,
    boosts INTEGER DEFAULT 0
)''')

db.execute('''CREATE TABLE IF NOT EXISTS autodefend (
    guild_id BIGINT,
    user_id BIGINT,
    birds JSON,
    PRIMARY KEY (guild_id, user_id)
)''')

db.execute('''CREATE TABLE IF NOT EXISTS birdbot_bans (
    guild_id BIGINT,
    user_id BIGINT,
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
    ("La Peace Bird", 1548379164577374358, 1.8, 13.0),
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
    err_text = f"{error.__class__.__name__}: {error}" if error else "Unknown error"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(f"❌ An error occurred.\n```{err_text[:500]}```", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ An error occurred.\n```{err_text[:500]}```", ephemeral=True)
    except Exception:
        pass

@bot.event
async def on_presence_update(before, after):
    if before.status != after.status:
        bot.presence_cache[after.id] = after.status

@bot.event
async def on_ready():
    logging.info("%s olarak giriş yapıldı ve PostgreSQL aktif!", bot.user)
    logging.info("[debug] intents: presences=%s members=%s message_content=%s", bot.intents.presences, bot.intents.members, bot.intents.message_content)

    for guild in bot.guilds:
        logging.info("[debug] guild=%r members=<%s>", guild.name, len(guild.members))
    
    # Initialize presence cache with current member statuses
    count = 0
    for member in bot.get_all_members():
        bot.presence_cache[member.id] = member.status
        count += 1
    logging.info("[debug] presence_cache initialized with %s members", count)
    
    for member in bot.get_all_members():
        if member.id in bot.whitelisted_users:
            logging.info("[debug] owner %s status=%s", member, member.status)

    if os.path.exists("./commands"):
        for filename in os.listdir("./commands"):
            if filename.endswith(".py") and filename != "__init__.py":
                cog_name = f"commands.{filename[:-3]}"
                await bot.load_extension(cog_name)
                logging.info("Modül yüklendi: %s", cog_name)

    try:
        synced = await bot.tree.sync()
        logging.info("%s global komut senkronize edildi.", len(synced))
    except Exception as e:
        logging.error("Senkronizasyon hatası: %s", e)

    # BirdBot'a tüm başarımları kilitle (leaderboard'larda görünmez, envanter gibi)
    games_cog = bot.get_cog("GamesCog")
    if games_cog and hasattr(games_cog, "ACHIEVEMENTS_LIST"):
        all_ach = list(games_cog.ACHIEVEMENTS_LIST.keys())
        for guild in bot.guilds:
            bot.db.save_achievements(guild.id, bot.user.id, all_ach)
        logging.info("[achievements] BirdBot'a %s başarım eklendi (%s sunucu).", len(all_ach), len(bot.guilds))

    bot.loop.create_task(_self_ping_loop())

bot.birds = BIRDS
bot.bird_values = BIRD_VALUES
bot.bird_values_lower = BIRD_VALUES_LOWER
bot.whitelisted_users = WHITELISTED_USERS
bot.resource_guild_ids = RESOURCE_GUILD_IDS
bot.spawn_states = {}
bot.server_settings = db.get_server_settings()
bot.db = db

async def _tree_interaction_check(interaction):
    user = interaction.user
    if user.id in bot.whitelisted_users:
        return True
    guild_id = int(interaction.guild_id) if interaction.guild_id else 0
    try:
        if bot.db.is_user_banned(guild_id, user.id):
            try:
                await interaction.response.send_message("🚫 You are banned from using BirdBot.", ephemeral=True)
            except Exception:
                pass
            return False
    except Exception:
        pass
    return True

bot.tree.interaction_check = _tree_interaction_check


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


def _start_health_server():
    port = int(os.getenv("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logging.info("[health] Listening on :%s", port)


def _get_public_url():
    return os.getenv("RENDER_EXTERNAL_URL") or os.getenv("PUBLIC_URL")


async def _self_ping_loop():
    """Render free, 15dk inbound istek yoksa servisi uyutur (spin-down).
    Kendi public URL'sine periyodik istek atarak bunu engelliyoruz."""
    url = _get_public_url()
    if not url:
        logging.warning("[keepalive] PUBLIC_URL/RENDER_EXTERNAL_URL yok, self-ping devre dışı")
        return
    import aiohttp
    import asyncio as _asyncio
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url.rstrip('/')}/health", timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    logging.info("[keepalive] ping %s -> %s", url, resp.status)
        except Exception as e:
            logging.warning("[keepalive] ping failed: %s", e)
        await _asyncio.sleep(300)


_start_health_server()

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("❌ HATA: DISCORD_TOKEN bulunamadı! Lütfen Railway Variables kısmına ekleyin.")
else:
    retry = 0
    while True:
        try:
            bot.run(TOKEN, reconnect=True)
            break
        except discord.HTTPException as e:
            retry += 1
            wait = min(300, 20 * (2 ** (retry - 1))) + random.uniform(0, 5)
            print(f"[startup] Discord API error (HTTP {e.status}): {e}. Retrying login in {wait:.0f}s (attempt {retry})")
            time.sleep(wait)
        except KeyboardInterrupt:
            break
        except SystemExit:
            raise
        except Exception as e:
            retry += 1
            wait = min(300, 20 * (2 ** (retry - 1))) + random.uniform(0, 5)
            print(f"[startup] Unexpected error: {e}. Restarting bot in {wait:.0f}s (attempt {retry})")
            time.sleep(wait)