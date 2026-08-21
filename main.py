import discord
from discord.ext import commands
import os
import json

# JSON Yükleme / Kaydetme Araçları (Ortak Kullanım)
INVENTORY_FILE = "inventory.json"
SETTINGS_FILE = "settings.json"
PIP_FILE = "pip_claims.json"
ACHIEVEMENTS_FILE = "achievements.json"
BIRDS_FILE = "birds.json"

def load_json(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                if filename == BIRDS_FILE:
                    print(f"✅ {filename} başarıyla yüklendi! Kuş sayısı: {len(data) if isinstance(data, list) else 'Hatalı Format'}")
                return data
        except Exception as e:
            print(f"❌ {filename} okunurken hata oluştu: {e}")
            return [] if filename == BIRDS_FILE else {}
    else:
        print(f"⚠️ Uyarı: {filename} dosyası bulunamadı! Tam yol: {os.path.abspath(filename)}")
    return [] if filename == BIRDS_FILE else {}

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Global Veriler
BIRDS = load_json(BIRDS_FILE)
BIRD_VALUES = {bird["name"]: bird["value"] for bird in BIRDS}
WHITELISTED_USERS = [1469734369739538677]
RESOURCE_GUILD_IDS = [
    1511406716749611171,
    1539963070045093958,
    1540320958429265920
]

server_inventories = load_json(INVENTORY_FILE)
server_settings = load_json(SETTINGS_FILE)
pip_claims = load_json(PIP_FILE)
achievements_data = load_json(ACHIEVEMENTS_FILE)
spawn_states = {}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"{bot.user} olarak giriş yapıldı!")
    
    # Tüm modülleri (cogs) yükle
    for filename in os.listdir("./commands"):
        if filename.endswith(".py") and filename != "__init__.py":
            cog_name = f"commands.{filename[:-3]}"
            await bot.load_extension(cog_name)
            print(f"Modül yüklendi: {cog_name}")
            
    # Komutları senkronize et
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} global komut senkronize edildi.")
    except Exception as e:
        print(f"Senkronizasyon hatası: {e}")

# Cog'ların ortak verilere ve fonksiyonlara erişebilmesi için bot nesnesine ekliyoruz
bot.birds = BIRDS
bot.bird_values = BIRD_VALUES
bot.whitelisted_users = WHITELISTED_USERS
bot.resource_guild_ids = RESOURCE_GUILD_IDS
bot.server_inventories = server_inventories
bot.server_settings = server_settings
bot.pip_claims = pip_claims
bot.achievements_data = achievements_data
bot.spawn_states = spawn_states
bot.load_json = load_json
bot.save_json = save_json

# Token'ını buraya yaz
bot.run("MTUzOTkwMzcxODAzMDQ0MjU3Nw.GNxKLL.z_G0LSHO-3lArb2tjtybTpJozRQcgLUl3z40sw")