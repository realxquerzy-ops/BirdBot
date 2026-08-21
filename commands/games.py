import discord
from discord.ext import commands
import random

class GamesCog(commands.Cog):
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
        "perfect": {"name": "Perfect", "desc": "Catch a bird in exactly 1 second (?.00s)", "hidden": True},
        "scammer": {"name": "Scammer", "desc": "Scam someone in a trade", "hidden": True},
        "scammed": {"name": "Scammed", "desc": "Get scammed in a trade", "hidden": True},
        "not_again": {"name": "Not again bud", "desc": "Try to use the /pip command a second time", "hidden": True},
        "top_1": {"name": "Top 1", "desc": "Be top 1 in the leaderboards", "hidden": False},
        "milk": {"name": "milk", "desc": "???", "hidden": True},
        "luck": {"name": "Luck", "desc": "Catch the exact same bird 3 times in a row", "hidden": False},
        "rich_bird": {"name": "Rich Bird", "desc": "Have an inventory value of 50+ points with fewer than 10 birds", "hidden": False},
        "giveaway": {"name": "Giveaway", "desc": "Give away a valuable bird for free in a trade", "hidden": True},
        "a_real_bird": {"name": "A Real Bird", "desc": "Get 100% on the /birdrate command", "hidden": True},
        "rarest": {"name": "Rarest", "desc": "Catch the rarest bird", "hidden": True}
    }

    async def unlock_achievement(self, user_id, ach_id, channel=None, guild_id=None):
        if not guild_id and channel and getattr(channel, "guild", None):
            guild_id = channel.guild.id

        guild_id_str = str(guild_id) if guild_id else "global"
        user_id_str = str(user_id)

        if guild_id_str not in self.bot.achievements_data:
            self.bot.achievements_data[guild_id_str] = {}

        if user_id_str not in self.bot.achievements_data[guild_id_str]:
            self.bot.achievements_data[guild_id_str][user_id_str] = []

        if ach_id not in self.bot.achievements_data[guild_id_str][user_id_str]:
            self.bot.achievements_data[guild_id_str][user_id_str].append(ach_id)
            self.bot.save_json("achievements.json", self.bot.achievements_data)

            ach_info = self.ACHIEVEMENTS_LIST.get(ach_id)
            if ach_info and channel:
                try:
                    embed = discord.Embed(
                        title="🏆 Achievement Unlocked!",
                        description=f"<@{user_id}> unlocked **{ach_info['name']}**!\n-# {ach_info['desc']}",
                        color=discord.Color.gold()
                    )
                    await channel.send(embed=embed)
                except Exception as e:
                    print(f"Could not send achievement notification: {e}")

    def check_stat_achievements(self, user_id, guild_id, channel=None, caught_bird_name=None):
        if not guild_id:
            return

        user_id_str = str(user_id)
        guild_id_str = str(guild_id)

        total_birds = 0
        user_birds = []
        if guild_id_str in self.bot.server_inventories:
            user_birds = self.bot.server_inventories[guild_id_str].get(user_id_str, [])
            total_birds = len(user_birds)

        if total_birds >= 1:
            self.bot.loop.create_task(self.unlock_achievement(user_id, "it_begins", channel, guild_id=guild_id))

        if total_birds >= 10:
            self.bot.loop.create_task(self.unlock_achievement(user_id, "likes_birds", channel, guild_id=guild_id))

        if total_birds >= 100:
            self.bot.loop.create_task(self.unlock_achievement(user_id, "is_a_bird", channel, guild_id=guild_id))

        if 0 < total_birds < 10:
            total_value = 0
            for b_name in user_birds:
                for bird_obj in self.bot.birds:
                    if bird_obj["name"].lower() == b_name.lower():
                        total_value += bird_obj.get("value", 0)
                        break
            if total_value >= 50:
                self.bot.loop.create_task(self.unlock_achievement(user_id, "rich_bird", channel, guild_id=guild_id))

        if caught_bird_name and self.bot.birds:
            valid_birds = [b for b in self.bot.birds if "weight" in b]
            if valid_birds:
                rarest_bird = min(valid_birds, key=lambda x: float(x["weight"]))
                if rarest_bird["name"].lower() == caught_bird_name.lower():
                    self.bot.loop.create_task(self.unlock_achievement(user_id, "rarest", channel, guild_id=guild_id))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        content_lower = message.content.lower().strip()
        if content_lower == "milk":
            await self.unlock_achievement(
                message.author.id, 
                "milk", 
                message.channel, 
                guild_id=message.guild.id if message.guild else None
            )

    @discord.app_commands.command(name="bird", description="Display a bird")
    @discord.app_commands.allowed_installs(guilds=True, users=True)
    @discord.app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def bird_spawn(self, interaction: discord.Interaction, bird_name: str):
        await interaction.response.defer(ephemeral=True)
        matched_bird = None
        for bird in self.bot.birds:
            if bird["name"].lower() == bird_name.lower():
                matched_bird = bird
                break

        if not matched_bird:
            available_birds = ", ".join([b["name"] for b in self.bot.birds])
            await interaction.followup.send(
                f"❌ Bird '{bird_name}' not found!\n**Available Birds:** {available_birds}", 
                ephemeral=True
            )
            return

        guild_id = str(interaction.guild.id) if interaction.guild else None
        target_channel = interaction.channel

        if guild_id and guild_id in self.bot.server_settings:
            ch = self.bot.get_channel(self.bot.server_settings[guild_id])
            if ch:
                target_channel = ch

        sticker = None
        try:
            sticker = await self.bot.fetch_sticker(matched_bird["sticker_id"])
        except Exception:
            pass

        await interaction.followup.send(f"✅ Bird **{matched_bird['name']}** successfully created!", ephemeral=True)
        content_text = f"A wild **{matched_bird['name']}** appeared! Type **bird** to catch it!\n-# (fake)"

        try:
            if sticker and isinstance(target_channel, discord.TextChannel):
                try:
                    await target_channel.send(content=content_text, stickers=[sticker])
                except discord.HTTPException:
                    await target_channel.send(content=content_text)
            else:
                await target_channel.send(content=content_text)
        except Exception as e:
            print(f"Could not send test bird message: {e}")

    @discord.app_commands.command(name="pip", description="???")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def pip_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)

        if guild_id not in self.bot.pip_claims:
            self.bot.pip_claims[guild_id] = {}

        if self.bot.pip_claims[guild_id].get(user_id, False):
            await self.unlock_achievement(interaction.user.id, "not_again", interaction.channel, guild_id=interaction.guild.id)
            await self.unlock_achievement(interaction.user.id, "pip", interaction.channel, guild_id=interaction.guild.id)
            
            embed = discord.Embed(
                title="❌ Already Claimed",
                description="You have already claimed this secret reward in this server!",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if guild_id not in self.bot.server_inventories:
            self.bot.server_inventories[guild_id] = {}
            
        if user_id not in self.bot.server_inventories[guild_id]:
            self.bot.server_inventories[guild_id][user_id] = []

        self.bot.server_inventories[guild_id][user_id].extend(["Good Bird", "Good Bird"])
        self.bot.save_json("inventory.json", self.bot.server_inventories)

        self.bot.pip_claims[guild_id][user_id] = True
        self.bot.save_json("pip_claims.json", self.bot.pip_claims)

        await self.unlock_achievement(interaction.user.id, "pip", interaction.channel, guild_id=interaction.guild.id)
        self.check_stat_achievements(interaction.user.id, interaction.guild.id, interaction.channel)

        embed = discord.Embed(
            title="🤫 Secret Discovered!",
            description=f"🎉 **{interaction.user.mention}** found the secret! You received **2x Good Bird** in this server!",
            color=discord.Color.purple()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.app_commands.command(name="birdrate", description="View your birdrate")
    @discord.app_commands.allowed_installs(guilds=True, users=True)
    @discord.app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def birdrate(self, interaction: discord.Interaction, member: discord.User = None):
        await interaction.response.defer()
        target_user = member or interaction.user
        rate_val = random.randint(85, 100) if target_user.id in self.bot.whitelisted_users else random.randint(1, 100)
            
        if rate_val == 100:
            await self.unlock_achievement(
                target_user.id, 
                "a_real_bird", 
                interaction.channel, 
                guild_id=interaction.guild.id if interaction.guild else None
            )

        embed = discord.Embed(
            title="Bird Rate",
            description=f"**{target_user.name}** is **{rate_val}%** bird 🐦",
            color=discord.Color.purple()
        )
        await interaction.followup.send(embed=embed)

    @discord.app_commands.command(name="gamble", description="Gamble your birds for a 50% chance to double them or lose them all!")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def gamble(self, interaction: discord.Interaction, bird_name: str, number: int):
        await interaction.response.defer(ephemeral=False)
        try:
            if not interaction.guild:
                await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
                return

            if number <= 0:
                await interaction.followup.send("❌ You must gamble at least 1 bird!", ephemeral=True)
                return

            matched_bird_name = None
            for bird in self.bot.birds:
                if bird["name"].lower() == bird_name.lower():
                    matched_bird_name = bird["name"]
                    break

            if not matched_bird_name:
                await interaction.followup.send(f"❌ Bird '{bird_name}' not found!", ephemeral=True)
                return

            guild_id = str(interaction.guild.id)
            user_id = str(interaction.user.id)

            if guild_id not in self.bot.server_inventories:
                self.bot.server_inventories[guild_id] = {}
            
            user_birds = self.bot.server_inventories[guild_id].get(user_id, [])

            current_count = user_birds.count(matched_bird_name)
            if current_count < number:
                await interaction.followup.send(f"❌ You don't have enough **{matched_bird_name}**! You have `{current_count}`, but tried to gamble `{number}`.", ephemeral=True)
                return

            won = random.choice([True, False])

            if won:
                for _ in range(number):
                    user_birds.append(matched_bird_name)
                self.bot.save_json("inventory.json", self.bot.server_inventories)
                self.check_stat_achievements(interaction.user.id, interaction.guild.id, interaction.channel)

                embed = discord.Embed(
                    title="🎰 Gamble Successful!",
                    description=f"🎉 **{interaction.user.mention}** won the gamble and doubled **{number}x {matched_bird_name}**! They now have `+{number}` extra.",
                    color=discord.Color.green()
                )
                await interaction.followup.send(embed=embed)
            else:
                for _ in range(number):
                    user_birds.remove(matched_bird_name)
                self.bot.save_json("inventory.json", self.bot.server_inventories)

                embed = discord.Embed(
                    title="🎰 Gamble Lost!",
                    description=f"💀 **{interaction.user.mention}** lost the gamble and their **{number}x {matched_bird_name}** vanished into thin air...",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed)
        except Exception as e:
            print(f"Error in gamble command: {e}")
            await interaction.followup.send("❌ An error occurred while executing this command.", ephemeral=True)

    @discord.app_commands.command(name="gift", description="Gift birds from your inventory to another user")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def gift(self, interaction: discord.Interaction, member: discord.Member, bird_name: str, number: int):
        await interaction.response.defer(ephemeral=False)
        try:
            if not interaction.guild:
                await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
                return

            if member.bot:
                await interaction.followup.send("❌ You cannot gift birds to bots!", ephemeral=True)
                return

            if member.id == interaction.user.id:
                await interaction.followup.send("❌ You cannot gift birds to yourself!", ephemeral=True)
                return

            if number <= 0:
                await interaction.followup.send("❌ You must gift at least 1 bird!", ephemeral=True)
                return

            matched_bird = None
            for bird in self.bot.birds:
                if bird["name"].lower() == bird_name.lower():
                    matched_bird = bird
                    break

            if not matched_bird:
                await interaction.followup.send(f"❌ Bird '{bird_name}' not found!", ephemeral=True)
                return

            matched_bird_name = matched_bird["name"]
            guild_id = str(interaction.guild.id)
            sender_id = str(interaction.user.id)
            receiver_id = str(member.id)

            if guild_id not in self.bot.server_inventories:
                self.bot.server_inventories[guild_id] = {}

            sender_birds = self.bot.server_inventories[guild_id].get(sender_id, [])

            current_count = sender_birds.count(matched_bird_name)
            if current_count < number:
                await interaction.followup.send(f"❌ You don't have enough **{matched_bird_name}**! You have `{current_count}`, but tried to gift `{number}`.", ephemeral=True)
                return

            for _ in range(number):
                sender_birds.remove(matched_bird_name)

            if receiver_id not in self.bot.server_inventories[guild_id]:
                self.bot.server_inventories[guild_id][receiver_id] = []
            
            for _ in range(number):
                self.bot.server_inventories[guild_id][receiver_id].append(matched_bird_name)

            self.bot.save_json("inventory.json", self.bot.server_inventories)
            self.check_stat_achievements(member.id, interaction.guild.id, interaction.channel)

            bird_value = matched_bird.get("value", 0)
            if bird_value > 13:
                await self.unlock_achievement(interaction.user.id, "giveaway", interaction.channel, guild_id=interaction.guild.id)

            embed = discord.Embed(
                title="🎁 Bird Gifted!",
                description=f"✅ {interaction.user.mention} successfully gifted **{number}x {matched_bird_name}** to {member.mention}!",
                color=discord.Color.blue()
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            print(f"Error in gift command: {e}")
            await interaction.followup.send("❌ An error occurred while executing this command.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(GamesCog(bot))