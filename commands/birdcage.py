import logging

from collections import Counter

import discord
from discord.ext import commands, tasks

CAGE_CAPACITY = {1: 3, 2: 5, 3: 8, 4: 12, 5: 16, 6: 24, 7: 32, 8: 42, 9: 55, 10: 70, 11: 90, 12: 115, 13: 145, 14: 180, 15: 220}
UPGRADE_COST = {1: 50, 2: 150, 3: 400, 4: 1000, 5: 2000, 6: 4000, 7: 7500, 8: 13000, 9: 21000, 10: 32000, 11: 47000, 12: 66000, 13: 90000, 14: 120000}
MAX_LEVEL = 15
INCOME_CAP = {1: 100, 2: 250, 3: 500, 4: 1000, 5: 4000, 6: 6000, 7: 9000, 8: 13500, 9: 20000, 10: 30000, 11: 45000, 12: 65000, 13: 90000, 14: 120000, 15: 160000}


class PutAmountModal(discord.ui.Modal, title="Put birds in cage"):
    def __init__(self, view, bird_name, max_put):
        super().__init__()
        self.put_view = view
        self.bird_name = bird_name
        self.max_put = max_put
        self.amount = discord.ui.TextInput(
            label="Quantity",
            placeholder=f"{bird_name} — 1 to {max_put}",
            default=str(max_put),
            required=True,
            max_length=3,
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        view = self.put_view
        if interaction.user.id != view.user_id:
            await interaction.response.send_message("❌ Not your cage!", ephemeral=True)
            return
        try:
            requested = int(str(self.amount.value).strip())
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number.", ephemeral=True)
            return
        if requested <= 0:
            await interaction.response.send_message("❌ Quantity must be at least 1.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        cage = view.bot.db.get_birdcage(view.guild_id, view.user_id)
        cap = CAGE_CAPACITY.get(cage["level"], 3)
        free = cap - len(cage["birds"])
        if free <= 0:
            await interaction.followup.send(
                f"❌ Cage is full! ({cap} slots). Upgrade with `/birdcage`.",
                ephemeral=True,
            )
            return

        inv = view.bot.db.get_inventory(view.guild_id, view.user_id)
        owned = inv.count(self.bird_name)
        if owned <= 0:
            await interaction.followup.send("❌ You no longer have that bird!", ephemeral=True)
            return

        placed = min(requested, owned, free)
        for _ in range(placed):
            inv.remove(self.bird_name)
        view.bot.db.save_inventory(view.guild_id, view.user_id, inv)

        cage["birds"].extend([self.bird_name] * placed)
        view.bot.db.save_birdcage(
            view.guild_id, view.user_id,
            cage["birds"], cage["level"], cage["accumulated"],
        )

        try:
            new_put = PutBirdView(view.bot, view.guild_id, view.user_id, view.parent_view)
            new_put._msg = view._msg
            if view._msg:
                await view._msg.edit(embed=view.parent_view.build_embed(), view=new_put)
        except Exception:
            pass

        note = f" (only {placed} fit)" if placed < requested else ""
        await interaction.followup.send(
            f"✅ Put **{placed}× {self.bird_name}** into the cage.{note}",
            ephemeral=True,
        )


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
        if interaction.user.id != view.user_id:
            await interaction.response.send_message("❌ Not your cage!", ephemeral=True)
            return
        if self.values[0] == "__none__":
            await interaction.response.send_message("❌ You have no birds!", ephemeral=True)
            return

        name = self.values[0]
        cage = view.bot.db.get_birdcage(view.guild_id, view.user_id)
        cap = CAGE_CAPACITY.get(cage["level"], 3)
        free = cap - len(cage["birds"])
        if free <= 0:
            await interaction.response.send_message(
                f"❌ Cage is full! ({cap} slots). Upgrade with `/birdcage`.",
                ephemeral=True,
            )
            return

        inv = view.bot.db.get_inventory(view.guild_id, view.user_id)
        owned = inv.count(name)
        if owned <= 0:
            await interaction.response.send_message("❌ You no longer have that bird!", ephemeral=True)
            return

        max_put = min(free, owned)
        await interaction.response.send_modal(PutAmountModal(view, name, max_put))


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
        income_cap = INCOME_CAP.get(cage["level"], INCOME_CAP[MAX_LEVEL])

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
                f"**Accumulated:** `{cage['accumulated']:.2f}` / `{income_cap}` BirdCoin\n\n"
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
        await interaction.response.edit_message(embed=self.build_embed(), view=put_view)

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

        await interaction.response.edit_message(embed=self.build_embed())

    async def on_timeout(self):
        if self._msg:
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
        self._user = None
        self.add_item(CagePutSelect(self))

    @property
    def user(self):
        if self._user is None:
            self._user = self.bot.get_user(self.user_id)
        return self._user

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Not your cage!", ephemeral=True)
            return
        await interaction.response.edit_message(embed=self.parent_view.build_embed(), view=self.parent_view)

    async def on_timeout(self):
        if self._msg:
            try:
                await self._msg.edit(view=None)
            except Exception:
                pass


class BirdCageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log = logging.getLogger("birdbot.birdcage")
        self.birdcage_income.start()

    def cog_unload(self):
        self.birdcage_income.cancel()

    @tasks.loop(seconds=60.0)
    async def birdcage_income(self):
        cages = self.bot.db.get_all_birdcages()
        if not cages:
            return
        for cage in cages:
            try:
                if not cage["birds"]:
                    continue
                total_value = sum(self.bot.bird_values.get(name, 1) for name in cage["birds"])
                income_per_min = total_value / 50.0
                limit = INCOME_CAP.get(cage["level"], INCOME_CAP[MAX_LEVEL])
                if cage["accumulated"] >= limit:
                    continue
                cage["accumulated"] = min(cage["accumulated"] + income_per_min, limit)
                self.bot.db.save_birdcage(
                    cage["guild_id"], cage["user_id"],
                    cage["birds"], cage["level"], cage["accumulated"],
                )
            except Exception as e:
                self.log.error("income tick fail for %s/%s: %s", cage["guild_id"], cage["user_id"], e)

    @birdcage_income.before_loop
    async def before_birdcage_income(self):
        await self.bot.wait_until_ready()

    @discord.app_commands.command(name="birdcage", description="View and manage your bird cage")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def birdcage(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("❌ Server only!", ephemeral=True)
            return

        await interaction.response.defer()
        view = CageView(self.bot, interaction.guild.id, interaction.user.id)
        msg = await interaction.followup.send(embed=view.build_embed(), view=view)
        view._msg = msg


async def setup(bot):
    await bot.add_cog(BirdCageCog(bot))
