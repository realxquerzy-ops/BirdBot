import random
from collections import Counter

import discord
from discord.ext import commands


def remove_birds(inventory, bird, count):
    remaining = []
    removed = 0
    for b in inventory:
        if b == bird and removed < count:
            removed += 1
        else:
            remaining.append(b)
    return remaining


class FightQuantityModal(discord.ui.Modal):
    def __init__(self, select_item, view_instance):
        super().__init__(title="Select Bird Count")
        self.select_item = select_item
        self.view_instance = view_instance
        self.count_input = discord.ui.TextInput(
            label="How many of this bird are you wagering?",
            placeholder="Enter a number...",
            min_length=1,
            max_length=3,
            default="1"
        )
        self.add_item(self.count_input)

    async def on_submit(self, interaction: discord.Interaction):
        view = self.view_instance
        if interaction.user.id != view.defender.id:
            await interaction.response.send_message("❌ Only the challenged user can pick birds!", ephemeral=True)
            return

        try:
            count = int(self.count_input.value)
            if count < 1 or count > view.target_birds.count(self.select_item.selected_bird):
                raise ValueError()
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number for this bird!", ephemeral=True)
            return

        view.set_defender_offer(self.select_item.selected_bird, count)
        await interaction.response.edit_message(content=view.status_text(), view=view)


class FightSelect(discord.ui.Select):
    def __init__(self, user_birds, owner_id, bird_values):
        self.owner_id = owner_id
        self.bird_values = bird_values
        counts = Counter(user_birds)

        options = [
            discord.SelectOption(
                label=bird,
                description=f"Value: {bird_values.get(bird.lower(), 1)} | Available: {counts[bird]}"
            )
            for bird in list(counts.keys())[:25]
        ]

        if not options:
            options = [discord.SelectOption(label="No birds available", description="You have no birds")]

        super().__init__(placeholder="Choose your bird for the fight...", min_values=1, max_values=1, options=options)
        self.selected_bird = None

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ You cannot pick the other user's bird!", ephemeral=True)
            return

        if self.values[0] == "No birds available":
            await interaction.response.send_message("❌ You don't have any birds to fight with!", ephemeral=True)
            return

        self.selected_bird = self.values[0]
        await interaction.response.send_modal(FightQuantityModal(self, self.view))


class FightView(discord.ui.View):
    def __init__(self, bot, attacker, defender, guild_id, atk_bird, atk_count):
        super().__init__(timeout=120)
        self.bot = bot
        self.attacker = attacker
        self.defender = defender
        self.guild_id = str(guild_id)
        self.attacker_offer = (atk_bird, atk_count)
        self.defender_offer = None

        self.target_birds = bot.db.get_inventory(int(guild_id), defender.id)
        bird_values = {bird["name"].lower(): bird.get("value", 1) for bird in bot.birds}
        self.target_select = FightSelect(self.target_birds, defender.id, bird_values)
        self.add_item(self.target_select)

    def set_defender_offer(self, bird, count):
        self.defender_offer = (bird, count)

    def status_text(self):
        atk_bird, atk_count = self.attacker_offer
        if self.defender_offer:
            def_bird, def_count = self.defender_offer
            def_str = f"`{def_count}x {def_bird}`"
        else:
            def_str = "*selecting...*"

        return (
            f"⚔️ **Bird Fight!**\n\n"
            f"🔵 **{self.attacker.name}** wagers: `{atk_count}x {atk_bird}`\n"
            f"🟢 **{self.defender.name}** wagers: {def_str}\n\n"
            f"Both players choose their birds, then press **Fight!**"
        )

    @discord.ui.button(label="Fight!", style=discord.ButtonStyle.green, row=2)
    async def fight(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in [self.attacker, self.defender]:
            await interaction.response.send_message("❌ You are not part of this fight!", ephemeral=True)
            return

        if not self.defender_offer:
            await interaction.response.send_message("❌ The defender must pick their bird first!", ephemeral=True)
            return

        guild_id_int = int(self.guild_id)
        atk_bird, atk_count = self.attacker_offer
        def_bird, def_count = self.defender_offer

        atk_inv = self.bot.db.get_inventory(guild_id_int, self.attacker.id)
        def_inv = self.bot.db.get_inventory(guild_id_int, self.defender.id)

        if atk_inv.count(atk_bird) < atk_count:
            await interaction.response.send_message("❌ The challenger no longer has enough of their bird!", ephemeral=True)
            return
        if def_inv.count(def_bird) < def_count:
            await interaction.response.send_message("❌ The defender no longer has enough of their bird!", ephemeral=True)
            return

        atk_val = self.bot.bird_values.get(atk_bird, 1) * atk_count
        def_val = self.bot.bird_values.get(def_bird, 1) * def_count
        total = atk_val + def_val
        p_atk = atk_val / total if total > 0 else 0.5

        attacker_wins = random.random() < p_atk

        if attacker_wins:
            def_inv = remove_birds(def_inv, def_bird, def_count)
            atk_inv.extend([def_bird] * def_count)
            winner, loser = self.attacker, self.defender
        else:
            atk_inv = remove_birds(atk_inv, atk_bird, atk_count)
            def_inv.extend([atk_bird] * atk_count)
            winner, loser = self.defender, self.attacker

        self.bot.db.save_inventory(guild_id_int, self.attacker.id, atk_inv)
        self.bot.db.save_inventory(guild_id_int, self.defender.id, def_inv)

        pct_atk = max(0.01, min(99.99, p_atk * 100))
        pct_def = round(100 - pct_atk, 2)

        embed = discord.Embed(
            title="⚔️ Fight Over!",
            description=(
                f"🔵 **{self.attacker.name}** (`{atk_count}x {atk_bird}`, worth `{atk_val}`)  vs  "
                f"🟢 **{self.defender.name}** (`{def_count}x {def_bird}`, worth `{def_val}`)\n\n"
                f"💥 **{winner.mention}** won the fight and took home the pot!\n"
                f"📉 **{loser.name}** lost their wager..."
            ),
            color=discord.Color.green() if winner == self.attacker else discord.Color.blurple()
        )
        embed.add_field(
            name="🎲 Odds",
            value=f"{self.attacker.name}: `{pct_atk:.2f}%` | {self.defender.name}: `{pct_def:.2f}%`"
        )
        await interaction.response.edit_message(content=None, embed=embed, view=None)
        self.stop()

    @discord.ui.button(label="Cancel Fight", style=discord.ButtonStyle.red, row=2)
    async def cancel_fight(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in [self.attacker, self.defender]:
            await interaction.response.send_message("❌ You cannot cancel this fight!", ephemeral=True)
            return
        await interaction.response.edit_message(content="❌ Fight was cancelled.", view=None)
        self.stop()


class FightRequestView(discord.ui.View):
    def __init__(self, bot, attacker, defender, guild_id, atk_bird, atk_count):
        super().__init__(timeout=60)
        self.bot = bot
        self.attacker = attacker
        self.defender = defender
        self.guild_id = guild_id
        self.atk_bird = atk_bird
        self.atk_count = atk_count

    @discord.ui.button(label="Accept Fight", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.defender:
            await interaction.response.send_message("❌ Only the challenged user can accept this fight!", ephemeral=True)
            return

        defender_birds = self.bot.db.get_inventory(int(self.guild_id), self.defender.id)
        if not defender_birds:
            await interaction.response.send_message("❌ You don't have any birds to fight with in this server!", ephemeral=True)
            return

        view = FightView(self.bot, self.attacker, self.defender, self.guild_id, self.atk_bird, self.atk_count)
        await interaction.response.edit_message(content=view.status_text(), view=view)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in [self.attacker, self.defender]:
            await interaction.response.send_message("❌ You cannot decline this fight!", ephemeral=True)
            return
        await interaction.response.edit_message(content="❌ Fight challenge declined.", view=None)
        self.stop()


class FightCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="fight", description="Challenge another user to a bird fight!")
    @discord.app_commands.describe(
        member="The user you want to fight",
        bird="The bird you will send into battle",
        number="How many of that bird you wager"
    )
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def fight(self, interaction: discord.Interaction, member: discord.Member, bird: str, number: int):
        await interaction.response.defer()
        try:
            if not interaction.guild:
                await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
                return

            if member.bot or member == interaction.user:
                await interaction.followup.send("❌ You cannot fight bots or yourself!", ephemeral=True)
                return

            if number <= 0:
                await interaction.followup.send("❌ You must wager at least 1 bird!", ephemeral=True)
                return

            matched_bird = None
            for b in self.bot.birds:
                if b["name"].lower() == bird.lower():
                    matched_bird = b
                    break

            if not matched_bird:
                await interaction.followup.send(f"❌ Bird '{bird}' not found!", ephemeral=True)
                return

            matched_bird_name = matched_bird["name"]
            guild_id = interaction.guild.id
            user_id = interaction.user.id

            user_birds = self.bot.db.get_inventory(guild_id, user_id)
            current_count = user_birds.count(matched_bird_name)
            if current_count < number:
                await interaction.followup.send(
                    f"❌ You don't have enough **{matched_bird_name}**! You have `{current_count}`.",
                    ephemeral=True
                )
                return

            view = FightRequestView(self.bot, interaction.user, member, guild_id, matched_bird_name, number)
            await interaction.followup.send(
                content=f"⚔️ {member.mention}, you have been challenged to a **bird fight** by **{interaction.user.name}**!"
                        f"\nThey wager `{number}x {matched_bird_name}`. Accept or decline!",
                view=view
            )
        except Exception as e:
            print(f"Error in fight command: {e}")
            await interaction.followup.send("❌ An error occurred while executing this command.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(FightCog(bot))