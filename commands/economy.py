from collections import Counter

import discord
from discord.ext import commands


class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_inventory_value(self, user_birds):
        return sum(self.bot.bird_values.get(bird, 1) for bird in user_birds)

    @discord.app_commands.command(name="droprates", description="View the spawn chance percentages and values of each bird")
    @discord.app_commands.allowed_installs(guilds=True, users=True)
    @discord.app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def droprates(self, interaction: discord.Interaction):
        await interaction.response.defer()
        total_weight = sum(float(bird["weight"]) for bird in self.bot.birds)
        rates_text = ""

        for bird in self.bot.birds:
            percentage = (float(bird["weight"]) / total_weight) * 100 if total_weight > 0 else 0.0
            rates_text += f"• **{bird['name']}** (Value: `{bird['value']}`): `{percentage:.2f}%`\n"

        embed = discord.Embed(
            title="📊 Bird Spawn Drop Rates & Values",
            description=rates_text,
            color=discord.Color.blue()
        )
        embed.set_footer(text="Higher rarity means higher value and lower drop rate!")
        await interaction.followup.send(embed=embed)

    @discord.app_commands.command(name="inventory", description="View your caught birds inventory for this server")
    @discord.app_commands.describe(member="View another user's inventory")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def inventory(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server!")
            return

        guild_id = interaction.guild.id
        target = member or interaction.user

        if target.id == self.bot.user.id:
            BIRDBOT_COUNT = 2**31 - 1
            bird_counts = {bird["name"]: BIRDBOT_COUNT for bird in self.bot.birds}
            total_val = sum(self.bot.bird_values.get(name, 1) * count for name, count in bird_counts.items())
            total_birds = sum(bird_counts.values())
            inventory_text = "\n".join([
                f"• **{bird}** (Value: {self.bot.bird_values.get(bird, 1)}): `{count:,}x`"
                for bird, count in bird_counts.items()
            ])
            embed = discord.Embed(
                title=f"📦 {target.name}'s Server Bird Inventory",
                description=inventory_text + f"\n\n💎 **Total Inventory Value:** `{total_val:,}` points",
                color=discord.Color.green()
            )
            embed.set_footer(text=f"Total Birds Caught Here: {total_birds:,}")
            await interaction.followup.send(embed=embed)
            return

        user_birds = self.bot.db.get_inventory(guild_id, target.id)

        if not user_birds:
            embed = discord.Embed(
                title=f"📦 {target.name}'s Server Inventory",
                description=f"{'You have' if target == interaction.user else target.name + ' has'} no birds in this server yet!",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            return

        bird_counts = Counter(user_birds)
        total_val = self.get_inventory_value(user_birds)
        inventory_text = "\n".join([f"• **{bird}** (Value: {self.bot.bird_values.get(bird, 1)}): `{count}x`" for bird, count in bird_counts.items()])

        embed = discord.Embed(
            title=f"📦 {target.name}'s Server Bird Inventory",
            description=inventory_text + f"\n\n💎 **Total Inventory Value:** `{total_val}` points",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Total Birds Caught Here: {len(user_birds)}")
        await interaction.followup.send(embed=embed)

    @discord.app_commands.command(name="leaderboard", description="View the top bird value leaderboard for this server")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server!")
            return

        guild_id = interaction.guild.id
        rows = self.bot.db.fetchall(
            "SELECT user_id, birds FROM inventories WHERE guild_id = %s", (guild_id,)
        )

        if not rows:
            embed = discord.Embed(
                title="🏆 Server Bird Value Leaderboard",
                description="No birds have been caught in this server yet!",
                color=discord.Color.orange()
            )
            await interaction.followup.send(embed=embed)
            return

        user_totals = []
        for row in rows:
            user_id = row[0]
            if int(user_id) == self.bot.user.id:
                continue
            birds = self.bot.db._loads_json(row[1])
            user_totals.append((user_id, self.get_inventory_value(birds), len(birds)))

        user_totals.sort(key=lambda x: x[1], reverse=True)
        top_users = user_totals[:10]

        lb_text = ""
        for index, (user_id, total_val, total_count) in enumerate(top_users, start=1):
            try:
                user = await self.bot.fetch_user(int(user_id))
                username = user.name
            except Exception:
                username = f"User_{user_id}"

            medal = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else f"`#{index}`"
            lb_text += f"{medal} **{username}** — `{total_val}` points *({total_count} birds)*\n"

        embed = discord.Embed(
            title="🏆 Server Bird Value Leaderboard (Top 10)",
            description=lb_text,
            color=discord.Color.gold()
        )
        await interaction.followup.send(embed=embed)

        if top_users:
            top_id = top_users[0][0]
            games_cog = self.bot.get_cog("GamesCog")
            if games_cog and top_users[0][1] > 0:
                games_cog.bot.loop.create_task(
                    games_cog.unlock_achievement(top_id, "top_1", interaction.channel, guild_id=guild_id)
                )


async def setup(bot):
    await bot.add_cog(EconomyCog(bot))