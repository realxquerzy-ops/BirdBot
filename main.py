import os
import json
import discord
from discord.ext import commands
import psycopg2
from urllib.parse import urlparse

# --- VERİTABANI BAĞLANTISI (PostgreSQL) ---
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ HATA: DATABASE_URL bulunamadı! Lütfen Railway PostgreSQL değişkenini ekleyin.")
    exit(1)

# Railway URL'sini parse edip psycopg2 ile bağlanıyoruz
url = urlparse(DATABASE_URL)
conn = psycopg2.connect(
    database=url.path[1:],
    user=url.username,
    password=url.password,
    host=url.hostname,
    port=url.port
)
conn.autocommit = True
cursor = conn.cursor()

# Tabloları Tertemiz Sıfırdan Oluşturuyoruz
cursor.execute('''CREATE TABLE IF NOT EXISTS inventories (
    guild_id BIGINT,
    user_id BIGINT,
    birds TEXT,
    PRIMARY KEY (guild_id, user_id)
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id BIGINT PRIMARY KEY,
    channel_id BIGINT
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS pip_claims (
    guild_id BIGINT,
    user_id BIGINT,
    claimed BOOLEAN,
    PRIMARY KEY (guild_id, user_id)
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS achievements (
    guild_id BIGINT,
    user_id BIGINT,
    achievements TEXT,
    PRIMARY KEY (guild_id, user_id)
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS birds_data (
    name TEXT PRIMARY KEY,
    sticker_id BIGINT,
    weight REAL,
    value REAL
)''')
conn.commit()

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
    ("Bird 618", 1540321587780124693, 0.2, 35.0),
    ("Radioactive Bird", 1540372078660952175, 0.1, 50)
]

for bird in default_birds:
    cursor.execute("""
        INSERT INTO birds_data (name, sticker_id, weight, value) 
        VALUES (%s, %s, %s, %s) 
        ON CONFLICT (name) DO NOTHING
    """, bird)
conn.commit()

# --- GLOBAL VERİLER VE YARDIMCI FONKSİYONLAR ---
cursor.execute("SELECT name, sticker_id, weight, value FROM birds_data")
BIRDS = [{"name": r[0], "sticker_id": r[1], "weight": r[2], "value": r[3]} for r in cursor.fetchall()]
BIRD_VALUES = {bird["name"]: bird["value"] for bird in BIRDS}

WHITELISTED_USERS = [1469734369739538677]
RESOURCE_GUILD_IDS = [
    1511406716749611171,
    1539963070045093958,
    1540320958429265920
]

spawn_states = {}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"{bot.user} olarak giriş yapıldı ve PostgreSQL aktif!")
    
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

bot.birds = BIRDS
bot.bird_values = BIRD_VALUES
bot.whitelisted_users = WHITELISTED_USERS
bot.resource_guild_ids = RESOURCE_GUILD_IDS
bot.spawn_states = spawn_states
bot.db_conn = conn
bot.db_cursor = cursor

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("❌ HATA: DISCORD_TOKEN bulunamadı! Lütfen Railway Variables kısmına ekleyin.")
else:
    bot.run(TOKEN)