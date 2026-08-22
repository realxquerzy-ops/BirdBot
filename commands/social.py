import discord
from discord.ext import commands
import json

class MultiQuantityModal(discord.ui.Modal):
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

        bird_name = self.select_item.selected_bird_temp
        self.view_instance.add_offer(self.select_item.owner_id, bird_name, val)
        
        if hasattr(self.view_instance, "confirmed_users"):
            self.view_instance.confirmed_users.clear()

        await interaction.response.edit_message(content=self.view_instance.update_status_text(), view=self.view_instance)

class TradeSelect(discord.ui.Select):
    def __init__(self, user_birds, placeholder, owner_id, bird_values):
        self.user_birds = user_birds
        self.owner_id = owner_id
        self.bird_values = bird_values
        unique_birds = list(set(user_birds))
        
        options = [discord.SelectOption(label=bird, description=f"Value: {bird_values.get(bird.lower(), 1)} | Available: {user_birds.count(bird)}") for bird in unique_birds[:25]]
        
        if not options:
            options = [discord.SelectOption(label="No birds available", description="You have no birds")]
            
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options)
        self.selected_bird_temp = None

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ You cannot modify the other user's offer!", ephemeral=True)
            return

        if self.values[0] == "No birds available":
            await interaction.response.send_message("❌ You don't have any birds to select!", ephemeral=True)
            return

        self.selected_bird_temp = self.values[0]
        max_count = self.user_birds.count(self.selected_bird_temp)

        modal = MultiQuantityModal(self, max_count, self.view)
        await interaction.response.send_modal(modal)

class TradeConfirmView(discord.ui.View):
    def __init__(self, bot, initiator, target, guild_id):
        super().__init__(timeout=60)
        self.bot = bot
        self.initiator = initiator
        self.target = target
        self.guild_id = guild_id
        self.confirmed_users = set()

        self.offers = {
            initiator.id: {},
            target.id: {}
        }

        cursor = bot.db_cursor
        cursor.execute("SELECT birds FROM inventories WHERE guild_id = ? AND user_id = ?", (int(guild_id), initiator.id))
        init_row = cursor.fetchone()
        self.init_birds = json.loads(init_row[0]) if init_row else []

        cursor.execute("SELECT birds FROM inventories WHERE guild_id = ? AND user_id = ?", (int(guild_id), target.id))
        target_row = cursor.fetchone()
        self.target_birds = json.loads(target_row[0]) if target_row else []

        bird_values = {}
        for bird in bot.birds:
            bird_values[bird["name"].lower()] = bird.get("value", 1)

        self.init_select = TradeSelect(self.init_birds, f"{initiator.name}: Add birds to offer", initiator.id, bird_values)
        self.target_select = TradeSelect(self.target_birds, f"{target.name}: Add birds to offer", target.id, bird_values)
        
        self.add_item(self.init_select)
        self.add_item(self.target_select)

    def add_offer(self, user_id, bird_name, count):
        self.offers[user_id][bird_name] = count

    def format_offer_list(self, user_id):
        user_offer = self.offers.get(user_id, {})
        if not user_offer:
            return "Nothing selected"
        
        items = []
        for bird, count in user_offer.items():
            items.append(f"`{count}x {bird}`")
        return ", ".join(items)

    def update_status_text(self):
        init_offer_str = self.format_offer_list(self.initiator.id)
        target_offer_str = self.format_offer_list(self.target.id)

        init_status = "✅ Confirmed" if self.initiator.id in self.confirmed_users else "⏳ Pending..."
        target_status = "✅ Confirmed" if self.target.id in self.confirmed_users else "⏳ Pending..."

        return (
            f"🤝 **Active Trade** between **{self.initiator.name}** and **{self.target.name}**\n\n"
            f"🔵 **{self.initiator.name}'s Offer:**\n{init_offer_str} — *({init_status})*\n\n"
            f"🟢 **{self.target.name}'s Offer:**\n{target_offer_str} — *({target_status})*"
        )

    async def unlock_achievement(self, user_id, ach_id, channel=None):
        user_id_val = int(user_id)
        guild_id_val = int(self.guild_id)

        cursor = self.bot.db_cursor
        conn = self.bot.db_conn

        cursor.execute("SELECT achievements FROM achievements WHERE guild_id = ? AND user_id = ?", (guild_id_val, user_id_val))
        row = cursor.fetchone()
        user_achievements = json.loads(row[0]) if row and row[0] else []

        if ach_id not in user_achievements:
            user_achievements.append(ach_id)
            cursor.execute("""
                INSERT OR REPLACE INTO achievements (guild_id, user_id, achievements) 
                VALUES (?, ?, ?)
            """, (guild_id_val, user_id_val, json.dumps(user_achievements)))
            conn.commit()

            games_cog = self.bot.get_cog("GamesCog")
            if games_cog and channel and hasattr(games_cog, "ACHIEVEMENTS_LIST"):
                ach_info = games_cog.ACHIEVEMENTS_LIST.get(ach_id)
                if ach_info:
                    try:
                        embed = discord.Embed(
                            description=f"🏆 <@{user_id}> unlocked achievement: **{ach_info['name']}**!",
                            color=discord.Color.gold()
                        )
                        await channel.send(embed=embed, delete_after=10)
                    except Exception as e:
                        print(f"Could not send achievement notification: {e}")

    @discord.ui.button(label="Confirm Trade", style=discord.ButtonStyle.green, row=2)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in [self.initiator, self.target]:
            await interaction.response.send_message("You are not part of this trade!", ephemeral=True)
            return

        if not self.offers[self.initiator.id] or not self.offers[self.target.id]:
            await interaction.response.send_message("Both users must select at least one bird to trade!", ephemeral=True)
            return

        self.confirmed_users.add(interaction.user.id)

        if len(self.confirmed_users) < 2:
            await interaction.response.edit_message(content=self.update_status_text(), view=self)
            return

        guild_id_int = int(self.guild_id)
        init_id = self.initiator.id
        target_id = self.target.id

        cursor = self.bot.db_cursor
        conn = self.bot.db_conn

        cursor.execute("SELECT birds FROM inventories WHERE guild_id = ? AND user_id = ?", (guild_id_int, init_id))
        init_row = cursor.fetchone()
        init_user_birds = json.loads(init_row[0]) if init_row and init_row[0] else []

        cursor.execute("SELECT birds FROM inventories WHERE guild_id = ? AND user_id = ?", (guild_id_int, target_id))
        target_row = cursor.fetchone()
        target_user_birds = json.loads(target_row[0]) if target_row and target_row[0] else []

        can_trade = True
        for bird, count in self.offers[init_id].items():
            if init_user_birds.count(bird) < count:
                can_trade = False
                break
        for bird, count in self.offers[target_id].items():
            if target_user_birds.count(bird) < count:
                can_trade = False
                break

        if not can_trade:
            await interaction.response.send_message("❌ Trade failed! One of the users no longer has enough of the selected birds.", ephemeral=True)
            return

        for bird, count in self.offers[init_id].items():
            for _ in range(count):
                init_user_birds.remove(bird)
                target_user_birds.append(bird)

        for bird, count in self.offers[target_id].items():
            for _ in range(count):
                target_user_birds.remove(bird)
                init_user_birds.append(bird)

        cursor.execute("INSERT OR REPLACE INTO inventories (guild_id, user_id, birds) VALUES (?, ?, ?)", (guild_id_int, init_id, json.dumps(init_user_birds)))
        cursor.execute("INSERT OR REPLACE INTO inventories (guild_id, user_id, birds) VALUES (?, ?, ?)", (guild_id_int, target_id, json.dumps(target_user_birds)))
        conn.commit()

        await self.unlock_achievement(self.initiator.id, "a_trade", interaction.channel)
        await self.unlock_achievement(self.target.id, "a_trade", interaction.channel)

        bird_values = {b["name"].lower(): b.get("value", 1) for b in self.bot.birds}
        
        init_val = sum(count * bird_values.get(bird.lower(), 1) for bird, count in self.offers[init_id].items())
        target_val = sum(count * bird_values.get(bird.lower(), 1) for bird, count in self.offers[target_id].items())

        if init_val > target_val * 3:
            await self.unlock_achievement(self.target.id, "scammer", interaction.channel)
            await self.unlock_achievement(self.initiator.id, "scammed", interaction.channel)
        elif target_val > init_val * 3:
            await self.unlock_achievement(self.initiator.id, "scammer", interaction.channel)
            await self.unlock_achievement(self.target.id, "scammed", interaction.channel)

        init_summary = self.format_offer_list(init_id)
        target_summary = self.format_offer_list(target_id)

        embed = discord.Embed(
            title="🤝 Trade Successful!",
            description=f"**{self.initiator.name}** gave {init_summary} and received {target_summary} from **{self.target.name}**!",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(content=None, embed=embed, view=None)
        self.stop()

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
        
        cursor = self.bot.db_cursor
        cursor.execute("SELECT birds FROM inventories WHERE guild_id = ? AND user_id = ?", (int(self.guild_id), self.target.id))
        row = cursor.fetchone()
        target_birds = json.loads(row[0]) if row and row[0] else []

        if not target_birds:
            await interaction.response.send_message("You don't have any birds to trade in this server!", ephemeral=True)
            return

        view = TradeConfirmView(self.bot, self.initiator, self.target, self.guild_id)
        content = (
            f"🤝 **Active Trade** between **{self.initiator.name}** and **{self.target.name}**\n\n"
            f"🔵 **{self.initiator.name}'s Offer:**\nNothing selected — *(⏳ Pending...)*\n\n"
            f"🟢 **{self.target.name}'s Offer:**\nNothing selected — *(⏳ Pending...)*"
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

        guild_id = interaction.guild.id
        cursor = self.bot.db_cursor
        cursor.execute("SELECT birds FROM inventories WHERE guild_id = ? AND user_id = ?", (guild_id, interaction.user.id))
        row = cursor.fetchone()
        user_birds = json.loads(row[0]) if row and row[0] else []
        
        if not user_birds:
            await interaction.followup.send("❌ You don't have any birds in your inventory to trade!", ephemeral=True)
            return

        view = TradeRequestView(self.bot, interaction.user, member, str(guild_id))
        await interaction.followup.send(content=f"🤝 {member.mention}, you have received a trade request from **{interaction.user.name}**!", view=view)

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
        if hasattr(self.bot, "spawn_states"):
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

        guild_id = interaction.guild.id
        cursor = self.bot.db_cursor
        conn = self.bot.db_conn

        cursor.execute("INSERT OR REPLACE INTO guild_settings (guild_id, channel_id) VALUES (?, ?)", (guild_id, channel.id))
        conn.commit()
        
        if hasattr(self.bot, "spawn_states"):
            self.bot.spawn_states[str(guild_id)] = {"active": False, "name": None, "spawn_time": None, "msg_obj": None}

        embed = discord.Embed(
            title="⚙️ Setup Complete",
            description=f"Bird spawn channel has been set to {channel.mention}!",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(SocialCog(bot))