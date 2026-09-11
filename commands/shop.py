from collections import Counter

import discord
from discord.ext import commands


class ShopCog(commands.Cog):
    SHOP_PRICES = {
        "shield": 40,
        "double_xp": 25,
        "double_catch": 35,
        "sab_miss": 45,
        "sab_half_xp": 30,
        "sab_steal": 60,
    }

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def fmt_coin(amount):
        return f"{amount:g}"

    def _powerup_info(self):
        cog = self.bot.get_cog("PowerupsCog")
        return getattr(cog, "POWERUPS", {}) if cog else {}

    @discord.app_commands.command(name="sell", description="Sell your birds for BirdCoin!")
    @discord.app_commands.describe(bird="Which bird to sell", count="How many to sell (default 1)")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def sell(self, interaction: discord.Interaction, bird: str, count: int = 1):
        await interaction.response.defer()
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
            return
        if count < 1:
            await interaction.followup.send("❌ Count must be at least 1!", ephemeral=True)
            return

        canon = next(
            (b["name"] for b in self.bot.birds if b["name"].lower() == bird.lower()),
            None,
        )
        if not canon:
            await interaction.followup.send("❌ That's not a real bird! Check /droprates for names.", ephemeral=True)
            return

        guild_id = interaction.guild.id
        user_id = interaction.user.id

        inv = self.bot.db.get_inventory(guild_id, user_id)
        owned = Counter(inv)[canon]
        if owned <= 0:
            await interaction.followup.send(f"❌ You don't have **{canon}** to sell!", ephemeral=True)
            return
        if count > owned:
            await interaction.followup.send(f"❌ You only have `{owned}x` **{canon}**!", ephemeral=True)
            return

        removed = 0
        new_inv = []
        for b in inv:
            if b == canon and removed < count:
                removed += 1
            else:
                new_inv.append(b)
        self.bot.db.save_inventory(guild_id, user_id, new_inv)

        value = self.bot.bird_values.get(canon, 1)
        earned = value * count
        self.bot.db.add_birdcoin(guild_id, user_id, earned)
        new_balance = self.bot.db.get_birdcoin(guild_id, user_id)

        games_cog = self.bot.get_cog("GamesCog")
        if games_cog:
            await games_cog.unlock_achievement(user_id, "sell_first", interaction.channel, guild_id=guild_id)

        embed = discord.Embed(
            title="💸 Sale Complete!",
            description=(
                f"Sold `{count}x` **{canon}** for 🪙 **{self.fmt_coin(earned)} BirdCoin**!\n"
                f"🪙 New balance: `{self.fmt_coin(new_balance)}`"
            ),
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)

    @discord.app_commands.command(name="balance", description="View your BirdCoin balance")
    @discord.app_commands.describe(member="View another user's balance")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def balance(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
            return

        guild_id = interaction.guild.id
        target = member or interaction.user

        if target.id == self.bot.user.id:
            balance = 2**31 - 1
        else:
            balance = self.bot.db.get_birdcoin(guild_id, target.id)

        embed = discord.Embed(
            title=f"🪙 {target.name}'s BirdCoin",
            description=f"🪙 **`{self.fmt_coin(balance)}`** BirdCoin",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Earn BirdCoin by selling birds with /sell, spend it in /shop!")
        await interaction.followup.send(embed=embed)

    @discord.app_commands.command(name="shop", description="View the BirdCoin powerup shop")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def shop(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
            return

        guild_id = interaction.guild.id
        user_id = interaction.user.id
        info = self._powerup_info()

        lines = []
        for key, price in self.SHOP_PRICES.items():
            p = info.get(key)
            name = p["name"] if p else key
            desc = p["desc"] if p else "?"
            kind = "✨ self" if p and p["type"] == "self" else "🪃 sabotage"
            lines.append(f"**{name}** — 🪙 `{price}` *({kind})*\n└ {desc}")

        balance = self.bot.db.get_birdcoin(guild_id, user_id)
        embed = discord.Embed(
            title="🛒 Bird Power Shop",
            description="\n".join(lines),
            color=discord.Color.orange()
        )
        embed.set_footer(text=f"🪙 Your balance: {self.fmt_coin(balance)} | Buy with /buy, earn with /sell!")
        await interaction.followup.send(embed=embed)

    @discord.app_commands.command(name="buy", description="Buy a powerup with BirdCoin")
    @discord.app_commands.describe(powerup="Which powerup to buy", count="How many to buy (default 1)")
    @discord.app_commands.choices(powerup=[
        discord.app_commands.Choice(name="🛡️ Shield", value="shield"),
        discord.app_commands.Choice(name="⚡ Double XP", value="double_xp"),
        discord.app_commands.Choice(name="🍀 Lucky Net", value="double_catch"),
        discord.app_commands.Choice(name="🪃 Distraction", value="sab_miss"),
        discord.app_commands.Choice(name="📉 Demotivate", value="sab_half_xp"),
        discord.app_commands.Choice(name="🕵️ Pocket", value="sab_steal"),
    ])
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def buy(self, interaction: discord.Interaction, powerup: str, count: int = 1):
        await interaction.response.defer()
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
            return
        if count < 1:
            await interaction.followup.send("❌ Count must be at least 1!", ephemeral=True)
            return

        price = self.SHOP_PRICES.get(powerup)
        info = self._powerup_info().get(powerup)
        if price is None or not info:
            await interaction.followup.send("❌ Unknown powerup!", ephemeral=True)
            return

        guild_id = interaction.guild.id
        user_id = interaction.user.id
        cost = price * count
        balance = self.bot.db.get_birdcoin(guild_id, user_id)

        if balance < cost:
            games_cog = self.bot.get_cog("GamesCog")
            if games_cog:
                await games_cog.unlock_achievement(user_id, "shop_broke", interaction.channel, guild_id=guild_id)
            await interaction.followup.send(
                f"❌ Not enough BirdCoin! You need 🪙 `{self.fmt_coin(cost)}` but only have 🪙 `{self.fmt_coin(balance)}`.",
                ephemeral=True
            )
            return

        self.bot.db.remove_birdcoin(guild_id, user_id, cost)
        self.bot.db.add_powerup(guild_id, user_id, powerup, count)
        new_balance = self.bot.db.get_birdcoin(guild_id, user_id)

        embed = discord.Embed(
            title="🛒 Purchase Complete!",
            description=(
                f"Bought **{info['name']}** `{count}x` for 🪙 **{self.fmt_coin(cost)} BirdCoin**!\n"
                f"🎒 Added to your powerups — use with /use.\n"
                f"🪙 New balance: `{self.fmt_coin(new_balance)}`"
            ),
            color=discord.Color.orange()
        )
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ShopCog(bot))