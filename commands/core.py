import discord
from discord.ext import commands, tasks
import random
import asyncio
import time
import json

class CoreCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # En hızlı süreleri tutmak için sözlük (user_id -> en kısa süre)
        if not hasattr(self.bot, "fastest_times"):
            self.bot.fastest_times = {}
        self.bird_spawner.start()

    def cog_unload(self):
        self.bird_spawner.cancel()

    # Veritabanından sunucu ayarlarını (kanal ID'lerini) çeken yardımcı fonksiyon
    def get_all_server_settings(self):
        cursor = self.bot.db_cursor
        cursor.execute("SELECT guild_id, channel_id FROM guild_settings")
        return {str(row[0]): row[1] for row in cursor.fetchall()}

    @tasks.loop(seconds=300.0)
    async def bird_spawner(self):
        wait_time = random.randint(300, 600)
        await asyncio.sleep(wait_time)

        server_settings = self.get_all_server_settings()

        for guild_id, channel_id in list(server_settings.items()):
            try:
                if guild_id not in self.bot.spawn_states:
                    self.bot.spawn_states[guild_id] = {"active": False, "name": None, "spawn_time": None, "msg_obj": None}
                    
                if self.bot.spawn_states[guild_id]["active"]:
                    continue

                channel = self.bot.get_channel(int(channel_id))
                if not channel:
                    try:
                        channel = await self.bot.fetch_channel(int(channel_id))
                    except Exception:
                        continue

                self.bot.spawn_states[guild_id]["active"] = True
                self.bot.spawn_states[guild_id]["spawn_time"] = time.time()

                selected_bird = random.choices(
                    self.bot.birds, 
                    weights=[float(bird["weight"]) for bird in self.bot.birds], 
                    k=1
                )[0]

                self.bot.spawn_states[guild_id]["name"] = selected_bird["name"]

                sticker = None
                try:
                    sticker = await self.bot.fetch_sticker(selected_bird["sticker_id"])
                except Exception:
                    pass

                content_text = f"A wild **{selected_bird['name']}** appeared! Type **bird** to catch it!"
                if sticker:
                    msg = await channel.send(content=content_text, stickers=[sticker])
                else:
                    msg = await channel.send(content=content_text)
                    
                self.bot.spawn_states[guild_id]["msg_obj"] = msg
                
            except Exception as e:
                print(f"Error in spawner: {e}")

    @bird_spawner.before_loop
    async def before_bird_spawner(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(5)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        user_id = str(message.author.id)
        content_lower = message.content.lower().strip()

        # "milk" başarımı için mesaj kontrolü (sunucu bazlı)
        if content_lower == "milk":
            games_cog = self.bot.get_cog("GamesCog")
            if games_cog:
                await games_cog.unlock_achievement(
                    message.author.id, 
                    "milk", 
                    message.channel, 
                    guild_id=message.guild.id if message.guild else None
                )

        if isinstance(message.channel, discord.DMChannel):
            if "no pip" in content_lower:
                await message.reply("\n".join(["pip the goat"] * 5))
            else:
                await message.reply("pip")
            return

        guild_id = str(message.guild.id) if message.guild else None
        server_settings = self.get_all_server_settings()
        
        if guild_id and guild_id in server_settings:
            if message.channel.id == server_settings[guild_id]:
                if guild_id not in self.bot.spawn_states:
                    self.bot.spawn_states[guild_id] = {"active": False, "name": None, "spawn_time": None, "msg_obj": None}

                if self.bot.spawn_states[guild_id]["active"]:
                    if content_lower == "bird":
                        caught_bird = self.bot.spawn_states[guild_id]["name"]
                        spawn_time = self.bot.spawn_states[guild_id].get("spawn_time", time.time())
                        catch_duration = time.time() - spawn_time

                        # En hızlı süreyi güncelle ve bot üzerinde sakla
                        if user_id not in self.bot.fastest_times or catch_duration < self.bot.fastest_times[user_id]:
                            self.bot.fastest_times[user_id] = catch_duration

                        self.bot.spawn_states[guild_id]["active"] = False
                        self.bot.spawn_states[guild_id]["name"] = None
                        
                        # --- VERİTABANINDAN ENVANTERİ ÇEK VE GÜNCELLE (PostgreSQL Uyumlu) ---
                        cursor = self.bot.db_cursor
                        conn = self.bot.db_conn
                        
                        cursor.execute("SELECT birds FROM inventories WHERE guild_id = %s AND user_id = %s", (int(guild_id), int(user_id)))
                        row = cursor.fetchone()
                        
                        if row:
                            user_birds = json.loads(row[0])
                        else:
                            user_birds = []
                            
                        user_birds.append(caught_bird)
                        
                        # PostgreSQL ON CONFLICT (UPSERT) yapısı
                        cursor.execute("""
                            INSERT INTO inventories (guild_id, user_id, birds) 
                            VALUES (%s, %s, %s)
                            ON CONFLICT (guild_id, user_id) 
                            DO UPDATE SET birds = EXCLUDED.birds
                        """, (int(guild_id), int(user_id), json.dumps(user_birds)))
                        conn.commit()
                        # -----------------------------------------------------------------

                        # Başarım kontrolleri (sunucu ID'si ile)
                        games_cog = self.bot.get_cog("GamesCog")
                        if games_cog:
                            if catch_duration < 3.0:
                                await games_cog.unlock_achievement(message.author.id, "too_fast", message.channel, guild_id=message.guild.id)
                            
                            if abs(catch_duration - round(catch_duration)) < 0.05:
                                await games_cog.unlock_achievement(message.author.id, "perfect", message.channel, guild_id=message.guild.id)

                            games_cog.check_stat_achievements(message.author.id, message.guild.id, message.channel, caught_bird_name=caught_bird)

                        msg_obj = self.bot.spawn_states[guild_id].get("msg_obj")
                        if msg_obj:
                            try:
                                await msg_obj.edit(content=msg_obj.content + " **(Collected)**")
                            except Exception:
                                pass

                        await message.reply(f"🎉 **{message.author.mention}** successfully caught the **{caught_bird}** in **{catch_duration:.2f}s**!")

    @discord.app_commands.command(name="help", description="Show bot commands")
    @discord.app_commands.allowed_installs(guilds=True, users=True)
    @discord.app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def help_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        embed = discord.Embed(
            title="📖 Commands",
            description=(
                "</achievements:0> - View your achievements\n"
                "</bird:0> - Display a bird\n"
                "</birdrate:0> - View your birdrate\n"
                "</droprates:0> - View bird drop rates\n"
                "</inventory:0> - View your inventory\n"
                "</leaderboard:0> - View the leaderboard\n"
                "</glb:0> - View global and advanced leaderboards\n"
                "</gift:0> - Gift birds to another user\n"
                "</dm:0> - DM settings or info\n"
                "</gamble:0> - Gamble your birds\n"
                "</trade:0> - Trade birds with someone"
            ),
            color=discord.Color.blue()
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(CoreCog(bot))