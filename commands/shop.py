from collections import Counter

import discord
from discord.ext import commands


class ShopCartView(discord.ui.View):
    def __init__(self, bot, cog, guild_id, user_id):
        super().__init__(timeout=60)
        self.bot = bot
        self.cog = cog
        self.guild_id = guild_id
        self.user_id = user_id
        self.message = None

        info = cog._powerup_info()
        for i, (key, price) in enumerate(cog.SHOP_PRICES.items()):
            p = info.get(key)
            name = p["name"] if p else key
            emoji = "✨" if p and p["type"] == "self" else "🪃"
            button = discord.ui.Button(
                label=f"{name} — 🪙 {cog.fmt_coin(price)}",
                emoji=emoji,
                style=discord.ButtonStyle.primary,
                row=i // 5,
            )

            async def _buy_cb(interaction: discord.Interaction, _key=key, _price=price):
                try:
                    await self._buy(interaction, _key, _price)
                except Exception as e:
                    print(f"Buy error: {e}")
                    try:
                        await interaction.followup.send("❌ Something went wrong while buying.", ephemeral=True)
                    except Exception:
                        pass

            button.callback = _buy_cb
            self.add_item(button)

    async def _refresh(self):
        embed = self.cog.build_shop_embed(self.guild_id, self.user_id)
        if self.message:
            try:
                await self.message.edit(embed=embed, view=self)
            except Exception:
                pass

    async def _buy(self, interaction, key, price):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Only the buyer can use this!", ephemeral=True)
            return

        info = self.cog._powerup_info().get(key)
        if price is None or not info:
            await interaction.response.send_message("❌ Unknown powerup!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        balance = self.bot.db.get_birdcoin(self.guild_id, self.user_id)
        if balance < price:
            games_cog = self.bot.get_cog("GamesCog")
            if games_cog:
                await games_cog.unlock_achievement(self.user_id, "shop_broke", interaction.channel, guild_id=self.guild_id)
            await interaction.followup.send(
                f"❌ Not enough BirdCoin! Need 🪙`{self.cog.fmt_coin(price)}`, you have 🪙`{self.cog.fmt_coin(balance)}`.",
                ephemeral=True
            )
            await self._refresh()
            return

        self.bot.db.remove_birdcoin(self.guild_id, self.user_id, price)
        self.bot.db.add_powerup(self.guild_id, self.user_id, key, 1)
        new_balance = self.bot.db.get_birdcoin(self.guild_id, self.user_id)

        await interaction.followup.send(
            f"🛒 Bought **{info['name']}** for 🪙`{self.cog.fmt_coin(price)}`! New balance: 🪙`{self.cog.fmt_coin(new_balance)}`.",
            ephemeral=True
        )
        await self._refresh()

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.delete()
            except Exception:
                pass


class ShopCog(commands.Cog):
    SHOP_PRICES = {
        "shield": 100,
        "double_xp": 25,
        "double_catch": 35,
        "sab_miss": 45,
        "sab_half_xp": 30,
        "sab_steal": 60,
        "golden_gut": 20,
        "bigger_net": 30,
        "scarecrow": 35,
        "bird_whistle": 60,
        "muzzle": 45,
    }

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def fmt_coin(amount):
        return f"{amount:g}"

    def _powerup_info(self):
        cog = self.bot.get_cog("PowerupsCog")
        return getattr(cog, "POWERUPS", {}) if cog else {}

    def build_shop_embed(self, guild_id, user_id):
        info = self._powerup_info()
        lines = []
        for key, price in self.SHOP_PRICES.items():
            p = info.get(key)
            name = p["name"] if p else key
            desc = p["desc"] if p else "?"
            kind = "✨" if p and p["type"] == "self" else "🪃"
            lines.append(f"**{name}** — 🪙 `{price}` *({kind})*\n└ {desc}")

        balance = self.bot.db.get_birdcoin(guild_id, user_id)
        embed = discord.Embed(
            title="🛒 Bird Power Shop",
            description="\n".join(lines),
            color=discord.Color.orange()
        )
        embed.set_footer(text=f"🪙 Your balance: {self.fmt_coin(balance)} | Press a button to buy that powerup!")
        return embed

    @discord.app_commands.command(name="sell", description="Sell birds for BirdCoin")
    @discord.app_commands.describe(bird="Which bird to sell", count="How many to sell, or type 'all' to sell everything")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def sell(self, interaction: discord.Interaction, bird: str, count: str = "1"):
        await interaction.response.defer()
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
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

        count_txt = count.strip().lower()
        if count_txt == "all":
            n = owned
        else:
            try:
                n = int(count_txt)
            except ValueError:
                await interaction.followup.send("❌ Count must be a number or 'all'!", ephemeral=True)
                return
            if n < 1:
                await interaction.followup.send("❌ Count must be at least 1!", ephemeral=True)
                return
            n = min(n, owned)

        removed = 0
        new_inv = []
        for b in inv:
            if b == canon and removed < n:
                removed += 1
            else:
                new_inv.append(b)
        self.bot.db.save_inventory(guild_id, user_id, new_inv)

        value = self.bot.bird_values.get(canon, 1)
        earned = value * n
        boost = False
        powerups_cog = self.bot.get_cog("PowerupsCog")
        if powerups_cog and powerups_cog.consume_sell_boost(guild_id, user_id):
            boost = True
            earned = round(earned * 1.5, 2)
        self.bot.db.add_birdcoin(guild_id, user_id, earned)
        new_balance = self.bot.db.get_birdcoin(guild_id, user_id)

        games_cog = self.bot.get_cog("GamesCog")
        if games_cog:
            await games_cog.unlock_achievement(user_id, "sell_first", interaction.channel, guild_id=guild_id)

        if n == owned:
            amount_txt = f"all `{n}x`"
        else:
            amount_txt = f"`{n}x` (you still have `{owned - n}x`)"
        boost_txt = "\n🪙 Golden Gut: **+50%** BirdCoin applied!" if boost else ""
        embed = discord.Embed(
            title="💸 Sale Complete!",
            description=(
                f"Sold {amount_txt} **{canon}** for 🪙 **{self.fmt_coin(earned)} BirdCoin**!\n"
                f"🪙 New balance: `{self.fmt_coin(new_balance)}`{boost_txt}"
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

    @discord.app_commands.command(name="shop", description="Buy powerups with BirdCoin")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def shop(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
            return

        guild_id = interaction.guild.id
        user_id = interaction.user.id

        view = ShopCartView(self.bot, self, guild_id, user_id)
        msg = await interaction.followup.send(embed=self.build_shop_embed(guild_id, user_id), view=view)
        view.message = msg


async def setup(bot):
    await bot.add_cog(ShopCog(bot))