import asyncio

from collections import Counter

import discord
from discord.ext import commands

CAGE_CAPACITY = {1: 3, 2: 5, 3: 8, 4: 12, 5: 16}
UPGRADE_COST = {1: 50, 2: 150, 3: 400, 4: 1000}
MAX_LEVEL = 5


class CagePutSelect(discord.ui.Select):
    def __init__(self, view):
        inv = view.bot.db.get_inventory(view.guild_id, view.user.id)
        counts = Counter(inv)
        options = []
        for name, count in counts.most_common(25):
            options.append(discord.SelectOption(
                label=f"{name} (x{count})",
                value=name,
                description=f"Value: {view.bot.bird_values.get(name, 1)}",
            ))
        if not options:
            options = [discord.SelectOption(label="No birds available", value="__none__")]
        super().__init__(placeholder="Pick a bird to put in cage...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if self.values[0] == "__none__":
            await interaction.response.send_message("❌ You have no birds!", ephemeral=True)
            return

        name = self.values[0]
        cage = view.bot.db.get_birdcage(view.guild_id, view.user.id)
        cap = CAGE_CAPACITY.get(cage["level"], 3)

        if len(cage["birds"]) >= cap:
            await interaction.response.send_message(
                f"❌ Cage is full! ({cap} slots). Upgrade with `/birdcage`.",
                ephemeral=True,
            )
            return

        inv = view.bot.db.get_inventory(view.guild_id, view.user.id)
        if name not in inv:
            await interaction.response.send_message("❌ You no longer have that bird!", ephemeral=True)
            return

        inv.remove(name)
        view.bot.db.save_inventory(view.guild_id, view.user.id, inv)

        cage["birds"].append(name)
        view.bot.db.save_birdcage(view.guild_id, view.user.id, cage["birds"], cage["level"], cage["accumulated"])

        await interaction.response.edit_message(embed=view.build_embed())
        await interaction.followup.send(f"🐦 **{name}** kafese eklendi!", ephemeral=True)


class CageView(discord.ui.View):
    def __init__(self, bot, guild_id, user_id):
        super().__init__(timeout=120)
        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id
        self._user = None

    @property
    def user(self):
        if self._user is None:
            self._user = self.bot.get_user(self.user_id)
        return self._user

    def build_embed(self):
        cage = self.bot.db.get_birdcage(self.guild_id, self.user_id)
        cap = CAGE_CAPACITY.get(cage["level"], 3)
        slot_text = f"{len(cage['birds'])}/{cap}"

        if cage["birds"]:
            counts = Counter(cage["birds"])
            bird_lines = []
            for name, count in counts.most_common():
                val = self.bot.bird_values.get(name, 1)
                bird_lines.append(f"  {name} ×{count}  —  `{val}` each")
            bird_text = "\n".join(bird_lines)
        else:
            bird_text = "Empty"

        upgrade_text = ""
        if cage["level"] < MAX_LEVEL:
            cost = UPGRADE_COST.get(cage["level"], 99999)
            next_cap = CAGE_CAPACITY.get(cage["level"] + 1, cap)
            upgrade_text = f"\n\n⬆️ Upgrade to Lv.{cage['level'] + 1}: **{cost} BirdCoin** → {next_cap} slots"
        else:
            upgrade_text = "\n\n🏆 Already at max level!"

        embed = discord.Embed(
            title=f"🦜 Bird Cage — {self.user.name}",
            description=(
                f"**Slots:** {slot_text}\n"
                f"**Level:** {cage['level']}\n"
                f"**Accumulated:** `{cage['accumulated']:.2f}` BirdCoin\n\n"
                f"**Caged Birds:**\n{bird_text}"
                f"{upgrade_text}"
            ),
            color=discord.Color.dark_green(),
        )
        return embed

    @discord.ui.button(label="Put Bird", style=discord.ButtonStyle.green, row=1)
    async def put_bird(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Not your cage!", ephemeral=True)
            return
        put_view = PutBirdView(self.bot, self.guild_id, self.user_id, self)
        put_view._msg = self._msg
        await interaction.response.edit_message(view=put_view)

    @discord.ui.button(label="Cash Out", style=discord.ButtonStyle.blurple, row=1)
    async def cash_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Not your cage!", ephemeral=True)
            return

        cage = self.bot.db.get_birdcage(self.guild_id, self.user_id)
        if not cage["birds"]:
            await interaction.response.send_message("❌ No birds in cage!", ephemeral=True)
            return

        accumulated = cage["accumulated"]
        birds = list(cage["birds"])

        self.bot.db.save_birdcage(self.guild_id, self.user_id, [], cage["level"], 0.0)

        inv = self.bot.db.get_inventory(self.guild_id, self.user_id)
        inv.extend(birds)
        self.bot.db.save_inventory(self.guild_id, self.user_id, inv)

        if accumulated > 0:
            self.bot.db.add_birdcoin(self.guild_id, self.user_id, accumulated)

        embed = discord.Embed(
            title="🪙 Cage Cashed Out!",
            description=(
                f"**Birds returned:** {len(birds)}\n"
                f"**BirdCoin earned:** `{accumulated:.2f}`"
            ),
            color=discord.Color.gold(),
        )
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Upgrade", style=discord.ButtonStyle.blurple, row=2)
    async def upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Not your cage!", ephemeral=True)
            return

        cage = self.bot.db.get_birdcage(self.guild_id, self.user_id)
        if cage["level"] >= MAX_LEVEL:
            await interaction.response.send_message("❌ Already at max level!", ephemeral=True)
            return

        cost = UPGRADE_COST.get(cage["level"], 99999)
        balance = self.bot.db.get_birdcoin(self.guild_id, self.user_id) or 0
        if balance < cost:
            await interaction.response.send_message(
                f"❌ Need **{cost} BirdCoin** but you have `{balance:.0f}`.", ephemeral=True,
            )
            return

        self.bot.db.remove_birdcoin(self.guild_id, self.user_id, cost)
        new_level = cage["level"] + 1
        self.bot.db.save_birdcage(self.guild_id, self.user_id, cage["birds"], new_level, cage["accumulated"])

        new_cap = CAGE_CAPACITY.get(new_level, 16)
        embed = discord.Embed(
            title="⬆️ Cage Upgraded!",
            description=f"Level **{new_level}** — **{new_cap}** slots!",
            color=discord.Color.purple(),
        )
        await interaction.response.edit_message(embed=self.build_embed())

    async def on_timeout(self):
        try:
            await self._msg.edit(view=None)
        except Exception:
            pass


class PutBirdView(discord.ui.View):
    def __init__(self, bot, guild_id, user_id, parent_view):
        super().__init__(timeout=60)
        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id
        self.parent_view = parent_view
        self.add_item(CagePutSelect(self))

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Not your cage!", ephemeral=True)
            return
        await interaction.response.edit_message(embed=self.parent_view.build_embed(), view=self.parent_view)

    async def on_timeout(self):
        try:
            await self._msg.edit(view=None)
        except Exception:
            pass


class BirdCageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.loop.create_task(self._income_loop())

    async def _income_loop(self):
        while True:
            try:
                await self._tick()
            except Exception:
                pass
            await asyncio.sleep(60)

    async def _tick(self):
        cages = self.bot.db.get_all_birdcages()
        for cage in cages:
            if not cage["birds"]:
                continue
            total_value = sum(self.bot.bird_values.get(name, 1) for name in cage["birds"])
            income_per_min = total_value / 30.0
            cage["accumulated"] += income_per_min
            self.bot.db.save_birdcage(
                cage["guild_id"], cage["user_id"],
                cage["birds"], cage["level"], cage["accumulated"],
            )

    @discord.app_commands.command(name="birdcage", description="View and manage your bird cage")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def birdcage(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("❌ Server only!", ephemeral=True)
            return

        view = CageView(self.bot, interaction.guild.id, interaction.user.id)
        msg = await interaction.response.send_message(embed=view.build_embed(), view=view)
        view._msg = msg


async def setup(bot):
    await bot.add_cog(BirdCageCog(bot))
