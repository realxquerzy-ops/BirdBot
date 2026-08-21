import discord
from discord.ext import commands

class QuantityModal(discord.ui.Modal):
    def __init__(self, select_item, max_count, view_instance):
        super().__init__(title="Select Quantity")
        self.select_item = select_item
        self.max_count = max_count
        self.view_instance = view_instance
        
        self.count_input = discord.ui.TextInput(
            label=f"Quantity (Max: {max_count})",
            placeholder="Enter a number...",
            min_length=1,
            max_length=3,
            default="1"
        )
        self.add_item(self.count_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.count_input.value)
            if val < 1 or val > self.max_count:
                raise ValueError()
        except ValueError:
            await interaction.response.send_message(f"❌ Please enter a valid number between 1 and {self.max_count}!", ephemeral=True)
            return

        self.select_item.selected_count = val
        await interaction.response.edit_message(content=self.view_instance.update_status_text(), view=self.view_instance)

class TradeSelect(discord.ui.Select):
    def __init__(self, user_birds, placeholder, owner_id, bird_values):
        self.user_birds = user_birds
        self.owner_id = owner_id
        self.bird_values = bird_values
        unique_birds = list(set(user_birds))
        
        options = [discord.SelectOption(label=bird, description=f"Value: {bird_values.get(bird, 1)} | Available: {user_birds.count(bird)}") for bird in unique_birds[:25]]
        
        if not options:
            options = [discord.SelectOption(label="No birds available", description="You have no birds")]
            
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options)
        self.selected_bird = None
        self.selected_count = 0

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ You cannot modify the other user's offer!", ephemeral=True)
            return

        if self.values[0] == "No birds available":
            await interaction.response.send_message("❌ You don't have any birds to select!", ephemeral=True)
            return

        self.selected_bird = self.values[0]
        max_count = self.user_birds.count(self.selected_bird)
        
        if hasattr(self.view, "confirmed_users"):
            self.view.confirmed_users.clear()

        modal = QuantityModal(self, max_count, self.view)
        await interaction.response.send_modal(modal)

class TradeConfirmView(discord.ui.View):
    def __init__(self, bot, initiator, target, guild_id):
        super().__init__(timeout=60)
        self.bot = bot
        self.initiator = initiator
        self.target = target
        self.guild_id = guild_id
        self.confirmed_users = set()

        guild_inv = bot.server_inventories.get(guild_id, {})
        self.init_birds = guild_inv.get(str(initiator.id), [])
        self.target_birds = guild_inv.get(str(target.id), [])

        self.init_select = TradeSelect(self.init_birds, f"{initiator.name}'s offer", initiator.id, bot.bird_values)
        self.target_select = TradeSelect(self.target_birds, f"{target.name}'s offer", target.id, bot.bird_values)
        
        self.add_item(self.init_select)
        self.add_item(self.target_select)

    def update_status_text(self):
        init_offer = f"{self.init_select.selected_count}x {self.init_select.selected_bird}" if self.init_select.selected_bird else "Nothing selected"
        target_offer = f"{self.target_select.selected_count}x {self.target_select.selected_bird}" if self.target_select.selected_bird else "Nothing selected"

        init_status = "✅ Confirmed" if self.initiator.id in self.confirmed_users else "⏳ Pending..."
        target_status = "✅ Confirmed" if self.target.id in self.confirmed_users else "⏳ Pending..."

        return (
            f"🤝 Trade active between **{self.initiator.name}** and **{self.target.name}**.\n\n"
            f"🔵 **{self.initiator.name}'s Offer:** {init_offer} ({init_status})\n"
            f"🟢 **{self.target.name}'s Offer:** {target_offer} ({target_status})"
        )

    async def unlock_achievement(self, user_id, ach_id, channel=None):
        user_id_str = str(user_id)
        if user_id_str not in self.bot.achievements_data:
            self.bot.achievements_data[user_id_str] = []
        if ach_id not in self.bot.achievements_data[user_id_str]:
            self.bot.achievements_data[user_id_str].append(ach_id)
            self.bot.save_json("achievements.json", self.bot.achievements_data)

    @discord.ui.button(label="Confirm Trade", style=discord.ButtonStyle.green, row=2)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in [self.initiator, self.target]:
            await interaction.response.send_message("You are not part of this trade!", ephemeral=True)
            return

        if not self.init_select.selected_bird or self.init_select.selected_count <= 0 or not self.target_select.selected_bird or self.target_select.selected_count <= 0:
            await interaction.response.send_message("Both users must select a bird and a valid quantity to trade!", ephemeral=True)
            return

        self.confirmed_users.add(interaction.user.id)

        if len(self.confirmed_users) < 2:
            await interaction.response.edit_message(content=self.update_status_text(), view=self)
            return

        init_bird = self.init_select.selected_bird
        init_count = self.init_select.selected_count
        target_bird = self.target_select.selected_bird
        target_count = self.target_select.selected_count

        guild_inv = self.bot.server_inventories[self.guild_id]
        init_id = str(self.initiator.id)
        target_id = str(self.target.id)

        init_user_birds = guild_inv.get(init_id, [])
        target_user_birds = guild_inv.get(target_id, [])

        if init_user_birds.count(init_bird) >= init_count and target_user_birds.count(target_bird) >= target_count:
            for _ in range(init_count):
                init_user_birds.remove(init_bird)
                target_user_birds.append(init_bird)

            for _ in range(target_count):
                target_user_birds.remove(target_bird)
                init_user_birds.append(target_bird)

            self.bot.save_json("inventory.json", self.bot.server_inventories)

            await self.unlock_achievement(self.initiator.id, "a_trade", interaction.channel)
            await self.unlock_achievement(self.target.id, "a_trade", interaction.channel)

            init_val = init_count * self.bot.bird_values.get(init_bird, 1)
            target_val = target_count * self.bot.bird_values.get(target_bird, 1)

            total_weight = sum(float(b["weight"]) for b in self.bot.birds)
            for b_info in self.bot.birds:
                if b_info["name"] == init_bird and total_weight > 0:
                    pct = (float(b_info["weight"]) / total_weight) * 100
                    if pct < 10.0 and target_val == 0:
                        await self.unlock_achievement(self.initiator.id, "giveaway")
                        
                if b_info["name"] == target_bird and total_weight > 0:
                    pct = (float(b_info["weight"]) / total_weight) * 100
                    if pct < 10.0 and init_val == 0:
                        await self.unlock_achievement(self.target.id, "giveaway")

            if init_val > target_val * 3:
                await self.unlock_achievement(self.target.id, "scammer")
                await self.unlock_achievement(self.initiator.id, "scammed")
            elif target_val > init_val * 3:
                await self.unlock_achievement(self.initiator.id, "scammer")
                await self.unlock_achievement(self.target.id, "scammed")

            embed = discord.Embed(
                title="🤝 Trade Successful!",
                description=f"**{self.initiator.name}** gave `{init_count}x {init_bird}` and got `{target_count}x {target_bird}`!",
                color=discord.Color.green()
            )
            await interaction.response.edit_message(content=None, embed=embed, view=None)
            self.stop()
        else:
            await interaction.response.send_message("❌ Trade failed! One of the users no longer has enough of the selected birds.", ephemeral=True)

    @discord.ui.button(label="Cancel / Decline", style=discord.ButtonStyle.red, row=2)
    async def cancel_trade(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in [self.initiator, self.target]:
            await interaction.response.send_message("You cannot cancel this trade!", ephemeral=True)
            return
        await interaction.response.edit_message(content="❌ Trade was cancelled by a participant.", view=None)
        self.stop()

class TradeRequestView(discord.ui.View):
    def __init__(self, bot, initiator, target, guild_id):
        super().__init__(timeout=30)
        self.bot = bot
        self.initiator = initiator
        self.target = target
        self.guild_id = guild_id

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.target:
            await interaction.response.send_message("Only the user who received the trade request can accept it!", ephemeral=True)
            return
        
        guild_inv = self.bot.server_inventories.get(self.guild_id, {})
        if not guild_inv.get(str(self.target.id), []):
            await interaction.response.send_message("You don't have any birds to trade in this server!", ephemeral=True)
            return

        view = TradeConfirmView(self.bot, self.initiator, self.target, self.guild_id)
        content = (
            f"🤝 Trade active between **{self.initiator.name}** and **{self.target.name}**.\n\n"
            f"🔵 **{self.initiator.name}'s Offer:** Nothing selected (⏳ Pending...)\n"
            f"🟢 **{self.target.name}'s Offer:** Nothing selected (⏳ Pending...)"
        )
        await interaction.response.edit_message(content=content, view=view)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.target and interaction.user != self.initiator:
            await interaction.response.send_message("You cannot decline this trade!", ephemeral=True)
            return
        await interaction.response.edit_message(content="❌ Trade request declined.", view=None)
        self.stop()

class SocialCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    ACHIEVEMENTS_LIST = {
        "it_begins": {"name": "It begins...", "desc": "Catch your first bird", "hidden": False},
        "likes_birds": {"name": "Likes Birds", "desc": "Catch 10 birds", "hidden": False},
        "is_a_bird": {"name": "IS a bird", "desc": "Catch 100 birds", "hidden": False},
        "a_trade": {"name": "A Trade", "desc": "Complete your first trade", "hidden": False},
        "too_fast": {"name": "Too fast", "desc": "Catch a bird in under 3 seconds", "hidden": False},
        "pip": {"name": "Pip?", "desc": "???", "hidden": True},
        "just_why": {"name": "Just why?", "desc": "DM the BirdBot 'no pip'", "hidden": True},
        "perfect": {"name": "Perfect", "desc": "Catch a bird in exactly 1 second", "hidden": True},
        "scammer": {"name": "Scammer", "desc": "Scam someone in a trade", "hidden": True},
        "scammed": {"name": "Scammed", "desc": "Get scammed in a trade", "hidden": True},
        "not_again": {"name": "Not again bud", "desc": "Try to use the /pip command a second time", "hidden": True},
        "top_1": {"name": "Top 1", "desc": "Be top 1 in the leaderboards", "hidden": False},
        "milk": {"name": "milk", "desc": "???", "hidden": True},
        "luck": {"name": "Luck", "desc": "Catch the exact same bird 3 times in a row", "hidden": False},
        "rich_bird": {"name": "Rich Bird", "desc": "Have an inventory value of 50+ points with fewer than 10 birds", "hidden": False},
        "giveaway": {"name": "Giveaway", "desc": "Give away a valuable bird for free in a trade", "hidden": True},
        "a_real_bird": {"name": "A Real Bird", "desc": "Get 100% on the /birdrate command", "hidden": True},
        "rarest": {"name": "Rarest", "desc": "Catch the rarest bird 2 times in a row", "hidden": True}
    }

    @discord.app_commands.command(name="trade", description="Trade birds with another user in this server")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def trade(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer()
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
            return

        if member.bot or member == interaction.user:
            await interaction.followup.send("❌ You cannot trade with bots or yourself!", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        guild_inv = self.bot.server_inventories.get(guild_id, {})
        
        if not guild_inv.get(str(interaction.user.id), []):
            await interaction.followup.send("❌ You don't have any birds in your inventory to trade!", ephemeral=True)
            return

        view = TradeRequestView(self.bot, interaction.user, member, guild_id)
        await interaction.followup.send(content=f"🤝 {member.mention}, you have received a trade request from **{interaction.user.name}**!", view=view)

    @discord.app_commands.command(name="achievements", description="View your or another user's unlocked achievements")
    @discord.app_commands.allowed_installs(guilds=True, users=True)
    @discord.app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def achievements(self, interaction: discord.Interaction, member: discord.User = None):
        await interaction.response.defer()
        target_user = member or interaction.user
        target_id = str(target_user.id)
        user_ach = self.bot.achievements_data.get(target_id, [])
        
        desc = ""
        for ach_id, info in self.ACHIEVEMENTS_LIST.items():
            unlocked = ach_id in user_ach
            status = "✅" if unlocked else "❌"
            if info["hidden"] and not unlocked:
                desc += f"{status} **{info['name']}** — `???`\n"
            else:
                desc += f"{status} **{info['name']}** — {info['desc']}\n"

        embed = discord.Embed(
            title=f"🏆 {target_user.name}'s Achievements",
            description=desc,
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Unlocked: {len(user_ach)} / {len(self.ACHIEVEMENTS_LIST)}")
        await interaction.followup.send(embed=embed)

    @discord.app_commands.command(name="dm", description="Sends you a direct message")
    @discord.app_commands.allowed_installs(guilds=True, users=True)
    @discord.app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def dm_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.user.send("hey")
            await interaction.followup.send("✨ Check your DMs!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ Couldn't send you a DM. Check your privacy settings.", ephemeral=True)

    @discord.app_commands.command(name="say", description="Send a custom message as the bot (Owner only)")
    @discord.app_commands.allowed_installs(guilds=True, users=True)
    @discord.app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def say_command(self, interaction: discord.Interaction, message: str):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id not in self.bot.whitelisted_users:
            await interaction.followup.send("❌ You do not have permission to use this command!", ephemeral=True)
            return
        
        await interaction.followup.send("Message sent successfully!", ephemeral=True)
        if interaction.channel:
            await interaction.channel.send(message)

    @discord.app_commands.command(name="resetspawn", description="Debug: Force reset the bird spawn lock for this context (Whitelist only)")
    @discord.app_commands.allowed_installs(guilds=True, users=True)
    @discord.app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def resetspawn(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id not in self.bot.whitelisted_users:
            await interaction.followup.send("❌ You do not have permission to use this debug command!", ephemeral=True)
            return

        guild_id = str(interaction.guild.id) if interaction.guild else "dm"
        self.bot.spawn_states[guild_id] = {"active": False, "name": None, "spawn_time": None, "msg_obj": None}
        await interaction.followup.send("🧹 **Debug:** Spawn lock has been successfully forced reset!", ephemeral=True)

    @discord.app_commands.command(name="setchannel", description="Set the channel where birds will spawn (Admin only)")
    @discord.app_commands.checks.has_permissions(manage_channels=True)
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def setchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        self.bot.server_settings[guild_id] = channel.id
        self.bot.save_json("settings.json", self.bot.server_settings)
        
        self.bot.spawn_states[guild_id] = {"active": False, "name": None, "spawn_time": None, "msg_obj": None}

        embed = discord.Embed(
            title="⚙️ Setup Complete",
            description=f"Bird spawn channel has been set to {channel.mention}!",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(SocialCog(bot))