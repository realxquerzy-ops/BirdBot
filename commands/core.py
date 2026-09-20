import asyncio
import datetime
import logging
import random
import time

import discord
from discord.ext import commands, tasks


def generate_math_question():
    a = random.randint(2, 12)
    b = random.randint(2, 9)
    c = random.randint(2, 8)
    op2 = random.choice(["+", "x", "-"])
    op1 = random.choice(["+", "x", "-"])
    if random.random() < 0.5:
        if op1 == "-" and b > a:
            a, b = b, a
        sub = a + b if op1 == "+" else (a * b if op1 == "x" else a - b)
        expr = f"({a} {op1} {b}) {op2} {c}"
        left, right = sub, c
    else:
        if op1 == "-" and c > b:
            b, c = c, b
        sub = b + c if op1 == "+" else (b * c if op1 == "x" else b - c)
        expr = f"{a} {op2} ({b} {op1} {c})"
        left, right = a, sub
    if op2 == "+":
        total = left + right
    elif op2 == "x":
        total = left * right
    else:
        total = left - right
    return expr, total


class CoreCog(commands.Cog):
    MISSPELLS = {"burd", "berd", "bord", "birdd", "birt", "beard", "b1rd", "gbird", "birb"}
    log = logging.getLogger("birdbot.spawner")

    def __init__(self, bot):
        self.bot = bot
        if not hasattr(self.bot, "fastest_times"):
            self.bot.fastest_times = {}
        if not hasattr(self.bot, "last_active"):
            self.bot.last_active = {}
        self.spawn_weights = [float(bird["weight"]) for bird in self.bot.birds]
        self.next_spawn_times = {}
        self.bird_spawner.start()

    def cog_unload(self):
        self.bird_spawner.cancel()

    def _new_spawn_state(self):
        return {"active": False, "name": None, "spawn_time": None, "msg_obj": None, "pending_user": None}

    def _schedule_next_spawn(self, guild_id):
        """Cooldown catch anından itibaren başlasın — hızlı kullanıcılar için anında respawn engeli."""
        self.next_spawn_times[guild_id] = time.time() + random.randint(120, 240)

    WEEKEND_RARITY_EXP = 0.85

    def _is_weekend(self):
        return datetime.datetime.now().weekday() >= 5

    def spawn_weights_for(self, guild_id):
        boost = 0
        try:
            boost = self.bot.db.get_guild_boost(int(guild_id))
        except Exception:
            pass

        exp = 1.0
        if boost > 0:
            exp = max(0.30, 1.0 - 0.035 * boost)

        if self._is_weekend():
            exp *= self.WEEKEND_RARITY_EXP

        if exp >= 1.0:
            return self.spawn_weights
        return [float(bird["weight"]) ** exp for bird in self.bot.birds]

    @tasks.loop(seconds=30.0)
    async def bird_spawner(self):
        now = time.time()
        self.bot.server_settings = self.bot.db.get_server_settings()

        for guild_id, channel_id in list(self.bot.server_settings.items()):
            try:
                guild = self.bot.get_guild(int(guild_id))
                if guild is None:
                    continue
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
                    except Exception as e:
                        self.log.error("fetch_channel fail for %s: %s", guild.name, e)
                        continue

                bird = random.choices(self.bot.birds, weights=self.spawn_weights_for(guild_id), k=1)[0]
                self.log.info("SPAWN %s in %s", bird["name"], guild.name)

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
                    self.log.error("Error in spawner send: %s", e)

                self._schedule_next_spawn(guild_id)
            except Exception as e:
                self.log.error("Error in spawner: %s", e)

    @bird_spawner.before_loop
    async def before_bird_spawner(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(5)
        for guild_id in list(self.bot.server_settings.keys()):
            self._schedule_next_spawn(guild_id)
        self.log.info("spawner startup: scheduled next spawns (deploy back-to-back guard)")

    async def force_spawn(self, guild_id, source=None):
        guild_id = str(guild_id)
        try:
            guild = self.bot.get_guild(int(guild_id))
            if guild is None:
                return False

            state = self.bot.spawn_states.get(guild_id)
            if state is None:
                state = self._new_spawn_state()
                self.bot.spawn_states[guild_id] = state
            if state["active"]:
                return False

            channel_id = self.bot.server_settings.get(guild_id)
            if not channel_id:
                return False
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                channel = await self.bot.fetch_channel(int(channel_id))

            bird = random.choices(self.bot.birds, weights=self.spawn_weights_for(guild_id), k=1)[0]
            state["active"] = True
            state["spawn_time"] = time.time()
            state["name"] = bird["name"]

            sticker = None
            try:
                sticker = await self.bot.fetch_sticker(bird["sticker_id"])
            except Exception:
                pass

            content_text = f"A wild **{bird['name']}** appeared! Type **bird** to catch it!"
            if source:
                content_text += f" *({source})*"
            if sticker:
                await channel.send(content=content_text, stickers=[sticker])
            else:
                await channel.send(content=content_text)
            return True
        except Exception as e:
            print(f"Error in force_spawn: {e}")
            return False

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        try:
            gid = int(message.guild.id) if message.guild else 0
            if message.author.id not in self.bot.whitelisted_users and self.bot.db.is_user_banned(gid, message.author.id):
                return
        except Exception:
            pass

        self.bot.last_active[message.author.id] = time.time()

        if message.guild:
            powerups_cog = self.bot.get_cog("PowerupsCog")
            if powerups_cog and powerups_cog.is_muzzled(int(message.guild.id), message.author.id):
                try:
                    if message.channel.permissions_for(message.guild.me).manage_messages:
                        await message.delete()
                except Exception:
                    pass
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

        guild_id_int = int(guild_id)
        user_id_int = int(user_id)

        powerups_cog = self.bot.get_cog("PowerupsCog")
        if powerups_cog and powerups_cog.consume_miss(guild_id_int, user_id_int):
            state["active"] = False
            state["name"] = None
            self._schedule_next_spawn(guild_id)
            await message.reply("💨 **The bird got spooked and flew away!** *(Distraction)*")
            return

        if caught_bird == "Duolingo Bird":
            if state.get("pending_user") and state["pending_user"] != user_id:
                await message.reply("⏳ The **Duolingo Bird** is already being questioned — one at a time!")
                return
            state["pending_user"] = user_id

            expr, answer = generate_math_question()
            await message.reply(
                f"🧮 **{message.author.mention}** a **Duolingo Bird** appeared, but it only accepts mathematicians!\n"
                f"Solve to catch it:\n**{expr}**"
            )

            def check(m):
                return m.author == message.author and m.channel == message.channel and not m.author.bot

            correct_msg = None
            deadline = time.time() + 30.0
            while time.time() < deadline:
                try:
                    answer_msg = await self.bot.wait_for(
                        "message", check=check, timeout=deadline - time.time()
                    )
                except asyncio.TimeoutError:
                    answer_msg = None
                    break
                try:
                    user_answer = int(answer_msg.content.strip())
                except ValueError:
                    continue
                correct_msg = answer_msg
                break

            if correct_msg is None:
                state["active"] = False
                state["name"] = None
                state["pending_user"] = None
                self._schedule_next_spawn(guild_id)
                await message.channel.send("⏰ Time's up! The **Duolingo Bird** flew away!")
                return

            if user_answer != answer:
                state["active"] = False
                state["name"] = None
                state["pending_user"] = None
                self._schedule_next_spawn(guild_id)
                await correct_msg.reply(f"❌ Wrong! The answer was **{answer}**. The **Duolingo Bird** flew away!")
                return

            state["pending_user"] = None
            await correct_msg.reply("✅ Correct! The **Duolingo Bird** is caught!")

        if user_id not in self.bot.fastest_times or catch_duration < self.bot.fastest_times[user_id]:
            self.bot.fastest_times[user_id] = catch_duration

        state["active"] = False
        state["name"] = None
        self._schedule_next_spawn(guild_id)

        xp_mult = 1.0
        double_chance = 0.0
        double_icon = ""
        doubled = False
        if powerups_cog:
            self_mult, double_chance, double_icon = powerups_cog.catch_effects(guild_id_int, user_id_int)
            if powerups_cog.consume_half_xp(guild_id_int, user_id_int):
                xp_mult *= 0.5
            xp_mult *= self_mult

        user_birds = self.bot.db.get_inventory(guild_id_int, user_id_int)
        user_birds.append(caught_bird)
        if double_chance and random.random() < double_chance:
            user_birds.append(caught_bird)
            doubled = True
        self.bot.db.save_inventory(guild_id_int, user_id_int, user_birds)

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
                await birdpass_cog.add_xp(guild_id_int, user_id_int, message.channel, caught_bird, xp_mult=xp_mult)
            except Exception as e:
                print(f"Error in birdpass xp: {e}")

        extra = f" *(... and a double! {double_icon})*" if doubled else ""
        await message.reply(f"🎉 **{message.author.mention}** successfully caught the **{caught_bird}** in **{catch_duration:.2f}s**!{extra}")

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
                "</powerups:0> - View your powerups and active effects\n"
                "</use:0> - Use a powerup or sabotage another player\n"
                "</birdpass:0> - View your BirdPass level and rewards\n"
                "</daily:0> - Claim your daily reward\n"
                "</sell:0> - Sell birds for BirdCoin\n"
                "</shop:0> - Buy powerups with BirdCoin\n"
                "</birdcage:0> - Put birds in your cage to earn passive BirdCoin\n"
                "</balance:0> - View your BirdCoin balance"
            ),
            color=discord.Color.blue()
        )

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(CoreCog(bot))