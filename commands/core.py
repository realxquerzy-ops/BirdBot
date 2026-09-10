import asyncio
import random
import time

import discord
from discord.ext import commands, tasks


class CoreCog(commands.Cog):
    MISSPELLS = {"burd", "berd", "bord", "birdd", "birt", "beard", "b1rd", "gbird", "birb"}

    def __init__(self, bot):
        self.bot = bot
        if not hasattr(self.bot, "fastest_times"):
            self.bot.fastest_times = {}
        self.spawn_weights = [float(bird["weight"]) for bird in self.bot.birds]
        self.next_spawn_times = {}
        self.bird_spawner.start()

    def cog_unload(self):
        self.bird_spawner.cancel()

    def _new_spawn_state(self):
        return {"active": False, "name": None, "spawn_time": None, "msg_obj": None}

    @tasks.loop(seconds=30.0)
    async def bird_spawner(self):
        now = time.time()
        self.bot.server_settings = self.bot.db.get_server_settings()

        for guild_id, channel_id in list(self.bot.server_settings.items()):
            try:
                state = self.bot.spawn_states.get(guild_id)
                if state is None:
                    state = self._new_spawn_state()
                    self.bot.spawn_states[guild_id] = state

                if state["active"]:
                    continue

                if self.next_spawn_times.get(guild_id, 0) > now:
                    continue

                channel = self.bot.get_channel(int(channel_id))
                if not channel:
                    try:
                        channel = await self.bot.fetch_channel(int(channel_id))
                    except Exception:
                        continue

                bird = random.choices(self.bot.birds, weights=self.spawn_weights, k=1)[0]

                state["active"] = True
                state["spawn_time"] = now
                state["name"] = bird["name"]

                sticker = None
                try:
                    sticker = await self.bot.fetch_sticker(bird["sticker_id"])
                except Exception:
                    pass

                content_text = f"A wild **{bird['name']}** appeared! Type **bird** to catch it!"
                try:
                    if sticker:
                        msg = await channel.send(content=content_text, stickers=[sticker])
                    else:
                        msg = await channel.send(content=content_text)
                    state["msg_obj"] = msg
                except Exception as e:
                    state["active"] = False
                    state["name"] = None
                    print(f"Error in spawner: {e}")

                self.next_spawn_times[guild_id] = now + random.randint(120, 240)
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

        content_lower = message.content.lower().strip()
        user_id = str(message.author.id)
        games_cog = self.bot.get_cog("GamesCog")

        if content_lower == "milk":
            if games_cog:
                await games_cog.unlock_achievement(
                    message.author.id,
                    "milk",
                    message.channel,
                    guild_id=message.guild.id if message.guild else None,
                )

        if self.bot.user in message.mentions:
            if games_cog:
                await games_cog.unlock_achievement(
                    message.author.id,
                    "why_ping",
                    message.channel,
                    guild_id=message.guild.id if message.guild else None,
                )

        if isinstance(message.channel, discord.DMChannel):
            if "no pip" in content_lower:
                if games_cog:
                    await games_cog.unlock_achievement(message.author.id, "just_why", message.channel)
                await message.reply("\n".join(["pip the goat"] * 5))
            else:
                await message.reply("pip")
            return

        guild_id = str(message.guild.id) if message.guild else None
        if not guild_id or guild_id not in self.bot.server_settings:
            return

        if message.channel.id != self.bot.server_settings[guild_id]:
            return

        if guild_id not in self.bot.spawn_states:
            self.bot.spawn_states[guild_id] = self._new_spawn_state()

        state = self.bot.spawn_states[guild_id]
        if not state["active"]:
            return

        if content_lower != "bird":
            if "brd" in content_lower or content_lower in self.MISSPELLS:
                if games_cog:
                    await games_cog.unlock_achievement(
                        message.author.id,
                        "mispell_bird",
                        message.channel,
                        guild_id=message.guild.id,
                    )
            return

        caught_bird = state["name"]
        spawn_time = state.get("spawn_time", time.time())
        catch_duration = time.time() - spawn_time

        if user_id not in self.bot.fastest_times or catch_duration < self.bot.fastest_times[user_id]:
            self.bot.fastest_times[user_id] = catch_duration

        state["active"] = False
        state["name"] = None

        user_birds = self.bot.db.get_inventory(int(guild_id), int(user_id))
        user_birds.append(caught_bird)
        self.bot.db.save_inventory(int(guild_id), int(user_id), user_birds)

        if games_cog:
            if catch_duration < 3.0:
                await games_cog.unlock_achievement(message.author.id, "too_fast", message.channel, guild_id=message.guild.id)

            if abs(catch_duration - round(catch_duration)) < 0.05:
                await games_cog.unlock_achievement(message.author.id, "perfect", message.channel, guild_id=message.guild.id)

            games_cog.check_stat_achievements(message.author.id, message.guild.id, message.channel, caught_bird_name=caught_bird)
            games_cog.check_luck_streak(message.author.id, message.guild.id, message.channel, caught_bird)

        msg_obj = state.get("msg_obj")
        if msg_obj:
            try:
                await msg_obj.edit(content=msg_obj.content + " **(Collected)**")
            except Exception:
                pass

        birdpass_cog = self.bot.get_cog("BirdPassCog")
        if birdpass_cog:
            try:
                await birdpass_cog.add_xp(int(guild_id), int(user_id), message.channel, caught_bird)
            except Exception as e:
                print(f"Error in birdpass xp: {e}")

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
                "</trade:0> - Trade birds with someone\n"
                "</fight:0> - Fight another user with your birds\n"
                "</birdpass:0> - View your BirdPass level and rewards\n"
                "</daily:0> - Claim your daily reward"
            ),
            color=discord.Color.blue()
        )

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(CoreCog(bot))