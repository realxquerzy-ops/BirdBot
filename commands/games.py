import discord
from discord.ext import commands
import random
import json

class GamesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    ACHIEVEMENTS_LIST = {
        # Mevcut Başarımlar
        "it_begins": {"name": "It begins...", "desc": "Catch your first bird", "hidden": False},
        "likes_birds": {"name": "Likes Birds", "desc": "Catch 10 birds", "hidden": False},
        "is_a_bird": {"name": "IS a bird", "desc": "Catch 100 birds", "hidden": False},
        "a_trade": {"name": "A Trade", "desc": "Complete your first trade", "hidden": False},
        "too_fast": {"name": "Too fast", "desc": "Catch a bird in under 3 seconds", "hidden": False},
        "pip": {"name": "Pip?", "desc": "???", "hidden": False},
        "just_why": {"name": "Just why?", "desc": "DM the BirdBot 'no pip'", "hidden": False},
        "perfect": {"name": "Perfect", "desc": "Catch a bird in exactly 1 second (?.00s)", "hidden": False},
        "scammer": {"name": "Scammer", "desc": "Scam someone in a trade", "hidden": False},
        "scammed": {"name": "Scammed", "desc": "Get scammed in a trade", "hidden": False},
        "not_again": {"name": "Not again bud", "desc": "Try to use the /pip command a second time", "hidden": False},
        "top_1": {"name": "Top 1", "desc": "Be top 1 in the leaderboards", "hidden": False},
        "milk": {"name": "milk", "desc": "???", "hidden": False},
        "luck": {"name": "Luck", "desc": "Catch the exact same bird 3 times in a row", "hidden": False},
        "rich_bird": {"name": "Rich Bird", "desc": "Have an inventory value of 50+ points with fewer than 10 birds", "hidden": False},
        "giveaway": {"name": "Giveaway", "desc": "Give away a valuable bird for free in a trade", "hidden": False},
        "a_real_bird": {"name": "A Real Bird", "desc": "Get 100% on the /birdrate command", "hidden": False},
        "rarest": {"name": "Rarest", "desc": "Catch the rarest bird", "hidden": False},

        # Yeni Eklenen Başarımlar
        "lets_go_gambling": {"name": "Let's go gambling!", "desc": "Gamble for the very first time", "hidden": False},
        "aww_dang_it": {"name": "Aw dang it!", "desc": "Lose your first gamble", "hidden": False},
        "skill_issue": {"name": "Skill Issue", "desc": "???", "hidden": False},
        "why_ping": {"name": "Why ping?", "desc": "Mention / ping the BirdBot", "hidden": False},
        "mispell_bird": {"name": "Mispell Bird", "desc": "Type 'brd' or misspell bird while trying to catch", "hidden": False},
        "triple_loss": {"name": "Unlucky Streak", "desc": "Lose 3 times in a row while gambling", "hidden": False},
        "big_bet": {"name": "Big Bet", "desc": "Gamble your absolute rarest bird", "hidden": False},
        "generous_rare": {"name": "Too Generous", "desc": "Gift the rarest bird in the game using /gift", "hidden": False},
        "nice_guy": {"name": "Nice Guy", "desc": "Gift a bird to a person who has 0 birds", "hidden": False},
        "broke_gambler": {"name": "Broke Gambler", "desc": "Try to gamble a bird you don't even own", "hidden": False},
        "oh_my_god": {"name": "OH MY GOD", "desc": "Gamble everything you have of a bird and win", "hidden": False},
        "its_over": {"name": "It's over.", "desc": "Gamble everything you have of a bird and lose", "hidden": False},
        "collector": {"name": "Collector", "desc": "Have every type of bird in your inventory", "hidden": False},
        "ultra_bird": {"name": "ULTRA BIRD", "desc": "Have every type of bird x5 in your inventory", "hidden": False},
        "god_bird": {"name": "GOD BIRD", "desc": "Have every type of bird x25 in your inventory", "hidden": False}
    }

    async def unlock_achievement(self, user_id, ach_id, channel=None, guild_id=None):
        if not guild_id and channel and getattr(channel, "guild", None):
            guild_id = channel.guild.id

        user_id_val = int(user_id)
        guild_id_db = int(guild_id) if guild_id else 0

        cursor = self.bot.db_cursor
        conn = self.bot.db_conn

        cursor.execute("SELECT achievements FROM achievements WHERE guild_id = ? AND user_id = ?", (guild_id_db, user_id_val))
        row = cursor.fetchone()
        
        user_achievements = json.loads(row[0]) if row and row[0] else []

        if ach_id not in user_achievements:
            user_achievements.append(ach_id)
            cursor.execute("""
                INSERT OR REPLACE INTO achievements (guild_id, user_id, achievements) 
                VALUES (?, ?, ?)
            """, (guild_id_db, user_id_val, json.dumps(user_achievements)))
            conn.commit()

            ach_info = self.ACHIEVEMENTS_LIST.get(ach_id)
            if ach_info and channel:
                try:
                    embed = discord.Embed(
                        title="🏆 Achievement Unlocked!",
                        description=f"<@{user_id}> has successfully unlocked:\n**{ach_info['name']}** — *{ach_info['desc']}*",
                        color=discord.Color.gold()
                    )
                    await channel.send(embed=embed, delete_after=10)
                except Exception as e:
                    print(f"Could not send achievement notification: {e}")

    def check_stat_achievements(self, user_id, guild_id, channel=None, caught_bird_name=None):
        if not guild_id:
            return

        cursor = self.bot.db_cursor
        cursor.execute("SELECT birds FROM inventories WHERE guild_id = ? AND user_id = ?", (int(guild_id), int(user_id)))
        row = cursor.fetchone()
        
        user_birds = json.loads(row[0]) if row and row[0] else []
        total_birds = len(user_birds)

        if isinstance(user_birds, list):
            inv_dict = {b: user_birds.count(b) for b in set(user_birds)}
        else:
            inv_dict = user_birds

        if total_birds >= 1:
            self.bot.loop.create_task(self.unlock_achievement(user_id, "it_begins", channel, guild_id=guild_id))

        if total_birds >= 10:
            self.bot.loop.create_task(self.unlock_achievement(user_id, "likes_birds", channel, guild_id=guild_id))

        if total_birds >= 100:
            self.bot.loop.create_task(self.unlock_achievement(user_id, "is_a_bird", channel, guild_id=guild_id))

        if self.bot.birds:
            all_bird_names = [b["name"] for b in self.bot.birds]
            has_all = all(inv_dict.get(name, 0) >= 1 for name in all_bird_names)
            has_all_x5 = all(inv_dict.get(name, 0) >= 5 for name in all_bird_names)
            has_all_x25 = all(inv_dict.get(name, 0) >= 25 for name in all_bird_names)

            if has_all:
                self.bot.loop.create_task(self.unlock_achievement(user_id, "collector", channel, guild_id=guild_id))
            if has_all_x5:
                self.bot.loop.create_task(self.unlock_achievement(user_id, "ultra_bird", channel, guild_id=guild_id))
            if has_all_x25:
                self.bot.loop.create_task(self.unlock_achievement(user_id, "god_bird", channel, guild_id=guild_id))

        if 0 < total_birds < 10:
            total_value = 0
            for b_name, count in inv_dict.items():
                for bird_obj in self.bot.birds:
                    if bird_obj["name"].lower() == b_name.lower():
                        total_value += bird_obj.get("value", 0) * count
                        break
            if total_value >= 50:
                self.bot.loop.create_task(self.unlock_achievement(user_id, "rich_bird", channel, guild_id=guild_id))

        if caught_bird_name and self.bot.birds:
            valid_birds = [b for b in self.bot.birds if "weight" in b]
            if valid_birds:
                rarest_bird = min(valid_birds, key=lambda x: float(x["weight"]))
                if rarest_bird["name"].lower() == caught_bird_name.lower():
                    self.bot.loop.create_task(self.unlock_achievement(user_id, "rarest", channel, guild_id=guild_id))

    @discord.app_commands.command(name="achievements", description="View your unlocked achievements")
    @discord.app_commands.allowed_installs(guilds=True, users=True)
    @discord.app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def achievements_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id if interaction.guild else 0
        user_id = interaction.user.id

        cursor = self.bot.db_cursor
        cursor.execute("SELECT achievements FROM achievements WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        row = cursor.fetchone()
        user_achievements = json.loads(row[0]) if row and row[0] else []

        description = ""
        for ach_id, info in self.ACHIEVEMENTS_LIST.items():
            if ach_id in user_achievements:
                description += f"✅ **{info['name']}** - {info['desc']}\n"
            else:
                description += f"🔒 *{info['name']}* - {info['desc']}\n"

        embed = discord.Embed(
            title=f"🏆 {interaction.user.name}'s Achievements",
            description=description or "No achievements unlocked yet!",
            color=discord.Color.gold()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

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

        if self.bot.user in message.mentions:
            await self.unlock_achievement(
                message.author.id,
                "why_ping",
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

        guild_id = interaction.guild.id if interaction.guild else None
        target_channel = interaction.channel

        if guild_id:
            cursor = self.bot.db_cursor
            cursor.execute("SELECT channel_id FROM guild_settings WHERE guild_id = ?", (guild_id,))
            row = cursor.fetchone()
            if row and row[0]:
                ch = self.bot.get_channel(row[0])
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

        user_id = interaction.user.id
        guild_id = interaction.guild.id

        cursor = self.bot.db_cursor
        conn = self.bot.db_conn

        cursor.execute("SELECT claimed FROM pip_claims WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        row = cursor.fetchone()
        already_claimed = bool(row[0]) if row else False

        if already_claimed:
            await self.unlock_achievement(interaction.user.id, "not_again", interaction.channel, guild_id=interaction.guild.id)
            await self.unlock_achievement(interaction.user.id, "pip", interaction.channel, guild_id=interaction.guild.id)
            
            embed = discord.Embed(
                title="❌ Already Claimed",
                description="You have already claimed this secret reward in this server!",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        cursor.execute("SELECT birds FROM inventories WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        inv_row = cursor.fetchone()
        user_birds = json.loads(inv_row[0]) if inv_row and inv_row[0] else []
        
        user_birds.extend(["Good Bird", "Good Bird"])

        cursor.execute("""
            INSERT OR REPLACE INTO inventories (guild_id, user_id, birds) 
            VALUES (?, ?, ?)
        """, (guild_id, user_id, json.dumps(user_birds)))

        cursor.execute("""
            INSERT OR REPLACE INTO pip_claims (guild_id, user_id, claimed) 
            VALUES (?, ?, 1)
        """, (guild_id, user_id))
        conn.commit()

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
    @discord.app_commands.describe(bird_name="The name of the bird", amount="Amount to gamble, or type 'all'")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def gamble(self, interaction: discord.Interaction, bird_name: str, amount: str):
        await interaction.response.defer(ephemeral=False)
        try:
            if not interaction.guild:
                await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
                return

            matched_bird_name = None
            for bird in self.bot.birds:
                if bird["name"].lower() == bird_name.lower():
                    matched_bird_name = bird["name"]
                    break

            if not matched_bird_name:
                await interaction.followup.send(f"❌ Bird '{bird_name}' not found!", ephemeral=True)
                return

            guild_id = interaction.guild.id
            user_id = interaction.user.id

            cursor = self.bot.db_cursor
            conn = self.bot.db_conn

            cursor.execute("SELECT birds FROM inventories WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
            row = cursor.fetchone()
            user_birds = json.loads(row[0]) if row and row[0] else []

            current_count = user_birds.count(matched_bird_name)
            if current_count <= 0:
                await self.unlock_achievement(user_id, "broke_gambler", interaction.channel, guild_id)
                await interaction.followup.send(f"❌ You don't own any **{matched_bird_name}** to gamble!", ephemeral=True)
                return

            is_all = False
            if amount.lower() == "all":
                number = current_count
                is_all = True
            else:
                try:
                    number = int(amount)
                except ValueError:
                    await interaction.followup.send("❌ Please enter a valid number or 'all' for the amount.", ephemeral=True)
                    return

            if number <= 0 or number > current_count:
                await interaction.followup.send(f"❌ Invalid amount! You have `{current_count}` of this bird.", ephemeral=True)
                return

            await self.unlock_achievement(user_id, "lets_go_gambling", interaction.channel, guild_id)

            valid_birds = [b for b in self.bot.birds if "weight" in b]
            if valid_birds:
                rarest_bird = min(valid_birds, key=lambda x: float(x["weight"]))
                if rarest_bird["name"].lower() == matched_bird_name.lower() and number == current_count:
                    await self.unlock_achievement(user_id, "big_bet", interaction.channel, guild_id)

            won = random.choice([True, False])

            if won:
                for _ in range(number):
                    user_birds.append(matched_bird_name)
                
                cursor.execute("""
                    INSERT OR REPLACE INTO inventories (guild_id, user_id, birds) 
                    VALUES (?, ?, ?)
                """, (guild_id, user_id, json.dumps(user_birds)))
                conn.commit()

                if is_all:
                    await self.unlock_achievement(user_id, "oh_my_god", interaction.channel, guild_id)

                self.check_stat_achievements(interaction.user.id, interaction.guild.id, interaction.channel)

                embed = discord.Embed(
                    title="🎰 Gamble Successful!",
                    description=f"🎉 **{interaction.user.mention}** won the gamble and doubled **{number}x {matched_bird_name}**!",
                    color=discord.Color.green()
                )
                await interaction.followup.send(embed=embed)
            else:
                for _ in range(number):
                    user_birds.remove(matched_bird_name)
                
                cursor.execute("""
                    INSERT OR REPLACE INTO inventories (guild_id, user_id, birds) 
                    VALUES (?, ?, ?)
                """, (guild_id, user_id, json.dumps(user_birds)))
                conn.commit()

                await self.unlock_achievement(user_id, "aww_dang_it", interaction.channel, guild_id)
                if is_all:
                    await self.unlock_achievement(user_id, "its_over", interaction.channel, guild_id)

                embed = discord.Embed(
                    title="🎰 Gamble Lost!",
                    description=f"💀 **{interaction.user.mention}** lost the gamble and their **{number}x {matched_bird_name}** vanished...",
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
            guild_id = interaction.guild.id
            sender_id = interaction.user.id
            receiver_id = member.id

            cursor = self.bot.db_cursor
            conn = self.bot.db_conn

            cursor.execute("SELECT birds FROM inventories WHERE guild_id = ? AND user_id = ?", (guild_id, receiver_id))
            receiver_row = cursor.fetchone()
            receiver_birds = json.loads(receiver_row[0]) if receiver_row and receiver_row[0] else []

            if len(receiver_birds) == 0:
                await self.unlock_achievement(sender_id, "nice_guy", interaction.channel, guild_id)

            cursor.execute("SELECT birds FROM inventories WHERE guild_id = ? AND user_id = ?", (guild_id, sender_id))
            sender_row = cursor.fetchone()
            sender_birds = json.loads(sender_row[0]) if sender_row and sender_row[0] else []

            current_count = sender_birds.count(matched_bird_name)
            if current_count < number:
                await interaction.followup.send(f"❌ You don't have enough **{matched_bird_name}**! You have `{current_count}`.", ephemeral=True)
                return

            for _ in range(number):
                sender_birds.remove(matched_bird_name)

            cursor.execute("""
                INSERT OR REPLACE INTO inventories (guild_id, user_id, birds) 
                VALUES (?, ?, ?)
            """, (guild_id, sender_id, json.dumps(sender_birds)))

            for _ in range(number):
                receiver_birds.append(matched_bird_name)

            cursor.execute("""
                INSERT OR REPLACE INTO inventories (guild_id, user_id, birds) 
                VALUES (?, ?, ?)
            """, (guild_id, receiver_id, json.dumps(receiver_birds)))
            conn.commit()

            self.check_stat_achievements(member.id, interaction.guild.id, interaction.channel)

            bird_value = matched_bird.get("value", 0)
            if bird_value > 13:
                await self.unlock_achievement(interaction.user.id, "giveaway", interaction.channel, guild_id=interaction.guild.id)

            valid_birds = [b for b in self.bot.birds if "weight" in b]
            if valid_birds:
                rarest_bird = min(valid_birds, key=lambda x: float(x["weight"]))
                if rarest_bird["name"].lower() == matched_bird_name.lower():
                    await self.unlock_achievement(interaction.user.id, "generous_rare", interaction.channel, guild_id)

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