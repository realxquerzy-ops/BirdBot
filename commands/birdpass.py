from datetime import datetime, time, timedelta, timezone

import discord
from discord.ext import commands

from commands.birdpass_image import render_birdpass_card
from mods import get_mods


class BirdPassCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    LEVEL_REWARDS = {
        2: [("Good Bird", 1)],
        3: [("Good Bird", 2)],
        4: [("Fat Bird", 1)],
        5: [("Chick", 1)],
        6: [("Fat Bird", 2)],
        7: [("Yellow Bird", 1)],
        8: [("Scarlet Mascow", 1)],
        9: [("Alpha Bird", 1)],
        10: [("Cool Bird", 1)],
        11: [("Angry Bird", 1)],
        12: [("Unknowmyt Bird", 1)],
        13: [("Golden Bird", 1)],
        14: [("Rainbow Bird", 1)],
        15: [("Tennis Bird", 1)],
        16: [("Bird 618", 1)],
        17: [("Radioactive Bird", 1)],
    }

    PREMIUM_CYCLE = [
        "La Peace Bird",
        "Golden Bird",
        "Rainbow Bird",
        "Cola Bird",
        "Tennis Bird",
        "Duolingo Bird",
        "Bird 618",
        "Bird Man",
        "Radioactive Bird",
        "Emerald Bird",
        "Caseoh Bird",
        "King Bird",
    ]

    COIN_MIN = 20
    COIN_PER_LEVEL = 6

    def xp_for_level(self, level):
        return 10 * level * (level + 1)

    def compute_level(self, total_xp):
        level = 1
        while total_xp >= self.xp_for_level(level + 1):
            level += 1
        return level

    def coin_reward_for(self, level):
        if level < 2:
            return 0
        return self.COIN_MIN + level * self.COIN_PER_LEVEL

    def reward_for(self, level, guild_id=None):
        got = self._base_reward_for(level)
        if not got or guild_id is None:
            return got
        mult = float(get_mods(self.bot, guild_id).get("birdpass_reward_mult", 1.0))
        if mult == 1.0:
            return got
        return [(bird, max(1, round(count * mult))) for bird, count in got]

    def _base_reward_for(self, level):
        if level < 2:
            return []
        if level <= 17:
            return self.LEVEL_REWARDS[level]

        cycle = len(self.PREMIUM_CYCLE)
        bird = self.PREMIUM_CYCLE[(level - 18) % cycle]
        count = 1 + (level - 18) // (2 * cycle)
        return [(bird, count)]

    @staticmethod
    def format_rewards(rewards):
        if not rewards:
            return "—"
        return ", ".join(f"`{count}x {bird}`" for bird, count in rewards)

    @staticmethod
    def format_coins(coins):
        return "" if coins <= 0 else f"`{int(coins)} coins`"

    def _today_iso(self):
        return datetime.now(timezone.utc).date().isoformat()

    @staticmethod
    def _week_start():
        today = datetime.now(timezone.utc).date()
        return today - timedelta(days=today.weekday())

    async def _gain_xp(self, guild_id, user_id, channel, xp_gain):
        guild_id_db = int(guild_id)
        user_id_db = int(user_id)

        xp, claimed_level, week_xp, week_start = self.bot.db.get_birdpass(guild_id_db, user_id_db)
        ws = self._week_start()
        if week_start is None or week_start != ws:
            week_xp = 0.0
            week_start = ws

        xp_mult_mod = float(get_mods(self.bot, guild_id_db).get("birdpass_xp_mult", 1.0))
        xp_gain = int(xp_gain * xp_mult_mod)

        old_level = self.compute_level(xp)
        new_xp = xp + xp_gain
        new_level = self.compute_level(new_xp)
        week_xp += xp_gain
        self.bot.db.save_birdpass(guild_id_db, user_id_db, new_xp, new_level, week_xp, week_start)

        if new_level <= old_level or new_level <= claimed_level:
            return

        rewards = []
        coins = 0
        for level in range(claimed_level + 1, new_level + 1):
            rewards.extend(self.reward_for(level, guild_id=guild_id_db))
            coins += self.coin_reward_for(level)

        if rewards:
            inventory = self.bot.db.get_inventory(guild_id_db, user_id_db)
            for bird, count in rewards:
                inventory.extend([bird] * count)
            self.bot.db.save_inventory(guild_id_db, user_id_db, inventory)

        if coins > 0:
            self.bot.db.add_birdcoin(guild_id_db, user_id_db, coins)

        if channel:
            try:
                reward_lines = [self.format_rewards(rewards)]
                if coins > 0:
                    reward_lines.append(f"🪙 {self.format_coins(coins)}")
                embed = discord.Embed(
                    title="🐦 BirdPass Level Up!",
                    description=f"<@{user_id}> reached **Level {new_level}**!",
                    color=discord.Color.gold()
                )
                embed.add_field(name="📈 XP", value=f"+{xp_gain} XP (Total: `{new_xp}`)", inline=True)
                embed.add_field(name="🎁 Rewards", value="\n".join(reward_lines), inline=True)
                await channel.send(embed=embed, delete_after=15)
            except Exception as e:
                print(f"Could not send birdpass level up: {e}")

    async def award_battle_xp(self, guild_id, user_id, channel, xp_amount):
        await self._gain_xp(int(guild_id), int(user_id), channel, int(xp_amount))

    async def add_xp(self, guild_id, user_id, channel, bird_name, xp_mult=1.0):
        value = self.bot.bird_values.get(bird_name, 1)
        xp_gain = int(round(value * 2 * xp_mult))
        await self._gain_xp(int(guild_id), int(user_id), channel, xp_gain)

    async def _avatar_pil(self, user):
        if user is None:
            return None
        try:
            data = await user.display_avatar.with_size(128).read()
            if not data:
                return None
            from PIL import Image as PILImage
            from io import BytesIO
            return PILImage.open(BytesIO(data))
        except Exception:
            return None

    def _member_for(self, guild, user_id):
        member = guild.get_member(user_id)
        if member is not None:
            return member
        return self.bot.get_user(user_id)

    @discord.app_commands.command(name="birdpass", description="View your BirdPass level, XP and the weekly Top 3")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def birdpass(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
            return

        guild_id = interaction.guild.id
        user_id = interaction.user.id

        xp, _, week_xp, _ = self.bot.db.get_birdpass(guild_id, user_id)
        level = self.compute_level(xp)
        threshold = self.xp_for_level(level)
        next_threshold = self.xp_for_level(level + 1)

        progress = int(xp - threshold)
        need = next_threshold - threshold

        next_reward = self.format_rewards(self.reward_for(level + 1))
        next_coins = self.format_coins(self.coin_reward_for(level + 1))
        if next_coins:
            next_reward = f"{next_reward} + {next_coins}"
        upcoming = []
        for offset in range(2, 7):
            up_rewards = self.format_rewards(self.reward_for(level + offset))
            up_coins = self.format_coins(self.coin_reward_for(level + offset))
            if up_coins:
                up_rewards = f"{up_rewards} + {up_coins}"
            upcoming.append(f"Lvl {level + offset}: {up_rewards}")

        top_rows = self.bot.db.get_weekly_top(guild_id, self._week_start(), 3)
        top3 = []
        for i, (uid, uxp) in enumerate(top_rows):
            member = self._member_for(interaction.guild, uid)
            name = member.display_name if member else f"User {uid}"
            av_img = await self._avatar_pil(member)
            top3.append((name, av_img, uxp))

        av_img = await self._avatar_pil(interaction.user)

        try:
            buf = render_birdpass_card(
                display_name=interaction.user.display_name,
                guild_name=interaction.guild.name,
                av_img=av_img,
                level=level,
                xp=xp,
                into=progress,
                need=need,
                next_reward=next_reward,
                upcoming=upcoming,
                top3=top3,
            )
        except Exception as e:
            print(f"BirdPass image failed: {e}")
            buf = None

        if buf is not None:
            file = discord.File(buf, filename="birdpass.png")
            embed = discord.Embed(color=discord.Color.gold())
            embed.set_image(url="attachment://birdpass.png")
            embed.set_footer(text="Catch birds to earn XP! Weekly Top 3 resets every Monday.")
            await interaction.followup.send(embed=embed, file=file)
        else:
            embed = discord.Embed(
                title=f"🐦 {interaction.user.name}'s BirdPass",
                description=(
                    f"🔹 **Level:** `{level}`\n"
                    f"📊 **Total XP:** `{int(xp)}`\n"
                    f"📈 **Weekly XP:** `{int(week_xp)}`\n"
                    f"{progress}/{need} XP to Level {level + 1}\n\n"
                    f"🎁 **Next Reward (Level {level + 1}):** {next_reward}\n"
                    f"🔮 **Coming up:**\n" + "\n".join(upcoming)
                ),
                color=discord.Color.gold()
            )
            await interaction.followup.send(embed=embed)

    @discord.app_commands.command(name="daily", description="Claim your daily reward: get 2x Fat Bird!")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def daily(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
            return

        guild_id = interaction.guild.id
        user_id = interaction.user.id
        today = self._today_iso()

        last_claim = self.bot.db.get_last_daily_claim(guild_id, user_id)
        if last_claim == today:
            now = datetime.now(timezone.utc)
            next_claim = datetime.combine(now.date() + timedelta(days=1), time.min, tzinfo=timezone.utc)
            remaining = next_claim - now
            hours, rem = divmod(int(remaining.total_seconds()), 3600)
            minutes = rem // 60
            embed = discord.Embed(
                title="❌ Already Claimed",
                description=f"You already claimed your daily reward today!\nCome back in **{hours}h {minutes}m**.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            return

        inventory = self.bot.db.get_inventory(guild_id, user_id)
        inventory.extend(["Fat Bird", "Fat Bird"])
        self.bot.db.save_inventory(guild_id, user_id, inventory)
        self.bot.db.set_daily_claim(guild_id, user_id, today)

        embed = discord.Embed(
            title="🎁 Daily Reward Claimed!",
            description=f"🎉 **{interaction.user.mention}** claimed their daily reward and received **2x Fat Bird**!",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(BirdPassCog(bot))