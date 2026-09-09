from datetime import datetime, time, timedelta, timezone

import discord
from discord.ext import commands


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

    def xp_for_level(self, level):
        return 15 * level * (level + 1)

    def compute_level(self, total_xp):
        level = 1
        while total_xp >= self.xp_for_level(level + 1):
            level += 1
        return level

    def reward_for(self, level):
        if level < 2:
            return []
        if level <= 17:
            return self.LEVEL_REWARDS[level]

        cycle = len(self.bot.birds)
        bird = self.bot.birds[(level - 2) % cycle]["name"]
        count = 1 + (level - 18) // cycle
        return [(bird, count)]

    @staticmethod
    def format_rewards(rewards):
        if not rewards:
            return "—"
        return ", ".join(f"`{count}x {bird}`" for bird, count in rewards)

    def _today_iso(self):
        return datetime.now(timezone.utc).date().isoformat()

    async def add_xp(self, guild_id, user_id, channel, bird_name):
        value = self.bot.bird_values.get(bird_name, 1)
        xp_gain = int(round(value))

        guild_id_db = int(guild_id)
        user_id_db = int(user_id)

        xp, claimed_level = self.bot.db.get_birdpass(guild_id_db, user_id_db)
        old_level = self.compute_level(xp)
        new_xp = xp + xp_gain
        new_level = self.compute_level(new_xp)
        self.bot.db.save_birdpass(guild_id_db, user_id_db, new_xp, new_level)

        if new_level <= old_level or new_level <= claimed_level:
            return

        rewards = []
        for level in range(claimed_level + 1, new_level + 1):
            rewards.extend(self.reward_for(level))

        if rewards:
            inventory = self.bot.db.get_inventory(guild_id_db, user_id_db)
            for bird, count in rewards:
                inventory.extend([bird] * count)
            self.bot.db.save_inventory(guild_id_db, user_id_db, inventory)

        if channel:
            try:
                embed = discord.Embed(
                    title="🐦 BirdPass Level Up!",
                    description=f"<@{user_id}> reached **Level {new_level}**!",
                    color=discord.Color.gold()
                )
                embed.add_field(name="📈 XP", value=f"+{xp_gain} XP (Total: `{new_xp}`)", inline=True)
                embed.add_field(name="🎁 Rewards", value=self.format_rewards(rewards), inline=True)
                await channel.send(embed=embed, delete_after=15)
            except Exception as e:
                print(f"Could not send birdpass level up: {e}")

    @discord.app_commands.command(name="birdpass", description="View your BirdPass level, XP and upcoming rewards")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def birdpass(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
            return

        guild_id = interaction.guild.id
        user_id = interaction.user.id

        xp, _ = self.bot.db.get_birdpass(guild_id, user_id)
        level = self.compute_level(xp)
        threshold = self.xp_for_level(level)
        next_threshold = self.xp_for_level(level + 1)

        progress = int(xp - threshold)
        need = next_threshold - threshold
        pct = max(0.0, min(1.0, progress / need if need > 0 else 1.0))
        bar = "▓" * int(round(10 * pct)) + "░" * (10 - int(round(10 * pct)))

        next_reward = self.format_rewards(self.reward_for(level + 1))
        upcoming = []
        for offset in range(2, 7):
            upcoming.append(f"• Level **{level + offset}**: {self.format_rewards(self.reward_for(level + offset))}")

        embed = discord.Embed(
            title=f"🐦 {interaction.user.name}'s BirdPass",
            description=(
                f"🔹 **Level:** `{level}`\n"
                f"📊 **Total XP:** `{int(xp)}`\n"
                f"{bar} **{progress}/{need}** XP to Level {level + 1}\n\n"
                f"🎁 **Next Reward (Level {level + 1}):** {next_reward}\n"
                f"🔮 **Coming up:**\n" + "\n".join(upcoming)
            ),
            color=discord.Color.gold()
        )
        embed.set_footer(text="Catch birds to earn XP and level up! Rewards are added to your inventory automatically.")
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