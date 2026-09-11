import random
import time
from collections import Counter

import discord
from discord.ext import commands


class GamesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        valid_birds = [bird for bird in self.bot.birds if "weight" in bird]
        self.rarest_bird = min(valid_birds, key=lambda x: float(x["weight"])) if valid_birds else None
        self.catch_streaks = {}
        self.gamble_losses = {}

    ACHIEVEMENTS_LIST = {
        "it_begins": {"name": "It begins...", "desc": "Catch your first bird", "hidden": False},
        "likes_birds": {"name": "Likes Birds", "desc": "Catch 10 birds", "hidden": False},
        "is_a_bird": {"name": "IS a bird", "desc": "Catch 100 birds", "hidden": False},
        "a_trade": {"name": "A Trade", "desc": "Complete your first trade", "hidden": False},
        "too_fast": {"name": "Too fast", "desc": "Catch a bird in under 3 seconds", "hidden": False},
        "pip": {"name": "Pip?", "desc": "???", "hidden": True},
        "just_why": {"name": "Just why?", "desc": "DM the BirdBot 'no pip'", "hidden": False},
        "perfect": {"name": "Perfect", "desc": "Catch a bird in exactly 1 second (?.00s)", "hidden": False},
        "scammer": {"name": "Scammer", "desc": "Scam someone in a trade", "hidden": False},
        "scammed": {"name": "Scammed", "desc": "Get scammed in a trade", "hidden": False},
        "not_again": {"name": "Not again bud", "desc": "Try to use the /pip command a second time", "hidden": False},
        "top_1": {"name": "Top 1", "desc": "Be top 1 in the leaderboards", "hidden": False},
        "milk": {"name": "milk", "desc": "???", "hidden": True},
        "luck": {"name": "Luck", "desc": "Catch the exact same bird 3 times in a row", "hidden": False},
        "rich_bird": {"name": "Rich Bird", "desc": "Have an inventory value of 50+ points with fewer than 10 birds", "hidden": False},
        "giveaway": {"name": "Giveaway", "desc": "Give away a valuable bird for free in a trade", "hidden": False},
        "a_real_bird": {"name": "A Real Bird", "desc": "Get 100% on the /birdrate command", "hidden": False},
        "rarest": {"name": "Rarest", "desc": "Catch the rarest bird", "hidden": False},
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
        "god_bird": {"name": "GOD BIRD", "desc": "Have every type of bird x25 in your inventory", "hidden": False},
        "fight_birdbot": {"name": "Brave Fool", "desc": "Challenge BirdBot to a battle", "hidden": False},
        "sell_first": {"name": "Cash Out", "desc": "Sell your first bird for BirdCoin", "hidden": False},
        "shop_broke": {"name": "Broke", "desc": "Try to buy something you can't afford at the shop", "hidden": False}
    }

    async def unlock_achievement(self, user_id, ach_id, channel=None, guild_id=None):
        if not guild_id and channel and getattr(channel, "guild", None):
            guild_id = channel.guild.id

        user_id_val = int(user_id)
        guild_id_db = int(guild_id) if guild_id else 0

        user_achievements = self.bot.db.get_achievements(guild_id_db, user_id_val)

        if ach_id not in user_achievements:
            user_achievements.append(ach_id)
            self.bot.db.save_achievements(guild_id_db, user_id_val, user_achievements)

            ach_info = self.ACHIEVEMENTS_LIST.get(ach_id)
            if ach_info and channel:
                try:
                    embed = discord.Embed(
                        title="🏆 Achievement Unlocked!",
                        description=f"<@{user_id}> has successfully unlocked:\n**{ach_info['name']}** — *{ach_info['desc']}*",
                        color=discord.Color.gold()
                    )
                    await channel.send(embed=embed)
                except Exception as e:
                    print(f"Could not send achievement notification: {e}")

    def check_stat_achievements(self, user_id, guild_id, channel=None, caught_bird_name=None):
        if not guild_id:
            return

        user_birds = self.bot.db.get_inventory(int(guild_id), int(user_id))
        total_birds = len(user_birds)
        inv_dict = Counter(user_birds)

        unlocks = []

        if total_birds >= 1:
            unlocks.append("it_begins")
        if total_birds >= 10:
            unlocks.append("likes_birds")
        if total_birds >= 100:
            unlocks.append("is_a_bird")

        if self.bot.birds:
            all_bird_names = [bird["name"] for bird in self.bot.birds]
            if all(inv_dict.get(name, 0) >= 1 for name in all_bird_names):
                unlocks.append("collector")
            if all(inv_dict.get(name, 0) >= 5 for name in all_bird_names):
                unlocks.append("ultra_bird")
            if all(inv_dict.get(name, 0) >= 25 for name in all_bird_names):
                unlocks.append("god_bird")

        if 0 < total_birds < 10:
            total_value = sum(
                self.bot.bird_values_lower.get(name.lower(), 0) * count
                for name, count in inv_dict.items()
            )
            if total_value >= 50:
                unlocks.append("rich_bird")

        if caught_bird_name and self.rarest_bird:
            if self.rarest_bird["name"].lower() == caught_bird_name.lower():
                unlocks.append("rarest")

        for ach_id in unlocks:
            self.bot.loop.create_task(self.unlock_achievement(user_id, ach_id, channel, guild_id=guild_id))

    def check_luck_streak(self, user_id, guild_id, channel, bird_name):
        key = (str(guild_id), str(user_id))
        last_bird, count = self.catch_streaks.get(key, (None, 0))
        if last_bird == bird_name:
            count += 1
        else:
            last_bird, count = bird_name, 1
        self.catch_streaks[key] = (last_bird, count)
        if count >= 3:
            self.bot.loop.create_task(self.unlock_achievement(user_id, "luck", channel, guild_id=guild_id))

    @discord.app_commands.command(name="achievements", description="View your (or someone else's) unlocked achievements")
    @discord.app_commands.describe(member="View another user's achievements")
    @discord.app_commands.allowed_installs(guilds=True, users=True)
    @discord.app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def achievements_command(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        guild_id = interaction.guild.id if interaction.guild else 0
        target = member or interaction.user

        if target.id == self.bot.user.id:
            user_achievements = list(self.ACHIEVEMENTS_LIST.keys())
        else:
            user_achievements = self.bot.db.get_achievements(guild_id, target.id)

        description = ""
        for ach_id, info in self.ACHIEVEMENTS_LIST.items():
            if ach_id in user_achievements:
                description += f"✅ **{info['name']}** — *{info['desc']}*\n"
            elif not info.get("hidden", False):
                description += f"❌ **{info['name']}** — *{info['desc']}*\n"
            else:
                description += f"❌ *???*\n"

        embed = discord.Embed(
            title=f"🏆 {target.name}'s Achievements",
            description=description or "No achievements unlocked yet!",
            color=discord.Color.gold()
        )
        await interaction.followup.send(embed=embed)

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
            channel_id = self.bot.db.get_server_channel(guild_id)
            if channel_id:
                ch = self.bot.get_channel(channel_id)
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

    @discord.app_commands.command(name="spawn", description="Spawn a real catchable bird (whitelist only)")
    @discord.app_commands.describe(bird_name="Specific bird to spawn (leave empty for random)")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def spawn_command(self, interaction: discord.Interaction, bird_name: str = None):
        if interaction.user.id not in self.bot.whitelisted_users:
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        state = self.bot.spawn_states.get(guild_id)
        if state is None:
            state = {"active": False, "name": None, "spawn_time": None, "msg_obj": None}
            self.bot.spawn_states[guild_id] = state
        if state["active"]:
            await interaction.followup.send("❌ A bird is already active! Wait for it to be caught first.", ephemeral=True)
            return

        channel_id = self.bot.db.get_server_channel(interaction.guild.id)
        if not channel_id:
            await interaction.followup.send("❌ No bird channel set for this server!", ephemeral=True)
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception:
                await interaction.followup.send("❌ Could not find the bird channel!", ephemeral=True)
                return

        if bird_name:
            matched = None
            for bird in self.bot.birds:
                if bird["name"].lower() == bird_name.lower():
                    matched = bird
                    break
            if not matched:
                available = ", ".join(b["name"] for b in self.bot.birds)
                await interaction.followup.send(f"❌ Bird '{bird_name}' not found!\n**Available:** {available}", ephemeral=True)
                return
        else:
            core_cog = self.bot.get_cog("CoreCog")
            weights = core_cog.spawn_weights if core_cog else [float(b.get("weight", 1)) for b in self.bot.birds]
            matched = random.choices(self.bot.birds, weights=weights, k=1)[0]

        state["active"] = True
        state["spawn_time"] = time.time()
        state["name"] = matched["name"]

        sticker = None
        try:
            sticker = await self.bot.fetch_sticker(matched["sticker_id"])
        except Exception:
            pass

        content_text = f"A wild **{matched['name']}** appeared! Type **bird** to catch it!"
        msg = None
        if sticker and isinstance(channel, discord.TextChannel):
            try:
                msg = await channel.send(content=content_text, stickers=[sticker])
            except discord.HTTPException:
                msg = await channel.send(content=content_text)
        else:
            msg = await channel.send(content=content_text)

        state["msg_obj"] = msg
        await interaction.followup.send(f"✅ Spawned **{matched['name']}** in {channel.mention}! (real, catchable)", ephemeral=True)

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

        already_claimed = self.bot.db.get_pip_claim(guild_id, user_id)

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

        user_birds = self.bot.db.get_inventory(guild_id, user_id)
        user_birds.extend(["Good Bird", "Good Bird"])

        self.bot.db.save_inventory(guild_id, user_id, user_birds)
        self.bot.db.set_pip_claim(guild_id, user_id)

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

            user_birds = self.bot.db.get_inventory(guild_id, user_id)
            current_count = user_birds.count(matched_bird_name)

            if current_count <= 0:
                await self.unlock_achievement(user_id, "broke_gambler", interaction.channel, guild_id)
                await interaction.followup.send(f"❌ You don't own any **{matched_bird_name}** to gamble!", ephemeral=True)
                return

            is_all = False
            if amount.lower() == "all":
                number = min(current_count, 100)
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

            if number > 100:
                number = 100

            await self.unlock_achievement(user_id, "lets_go_gambling", interaction.channel, guild_id)

            if self.rarest_bird:
                if self.rarest_bird["name"].lower() == matched_bird_name.lower() and number == current_count:
                    await self.unlock_achievement(user_id, "big_bet", interaction.channel, guild_id)

            won = random.choice([True, False])
            key = (str(guild_id), str(user_id))

            if won:
                self.gamble_losses.pop(key, None)
                if number > 8:
                    won_amount = round(number * 1.5) - number
                    mult_txt = f"only gained **{round(number * 1.5)}x total** (1.5x multiplier)"
                else:
                    won_amount = number
                    mult_txt = f"doubled it to **{number * 2}x**!"
                user_birds.extend([matched_bird_name] * won_amount)
                self.bot.db.save_inventory(guild_id, user_id, user_birds)

                if is_all:
                    await self.unlock_achievement(user_id, "oh_my_god", interaction.channel, guild_id)

                self.check_stat_achievements(interaction.user.id, interaction.guild.id, interaction.channel)

                embed = discord.Embed(
                    title="🎰 Gamble Successful!",
                    description=f"🎉 **{interaction.user.mention}** won the gamble and {mult_txt} (**{number}x {matched_bird_name}**)",
                    color=discord.Color.green()
                )
                await interaction.followup.send(embed=embed)
            else:
                powerups_cog = self.bot.get_cog("PowerupsCog")
                shield_saved = False
                if powerups_cog and powerups_cog.consume_shield(guild_id, user_id):
                    shield_saved = True
                else:
                    remaining = []
                    removed = 0
                    for bird in user_birds:
                        if bird == matched_bird_name and removed < number:
                            removed += 1
                        else:
                            remaining.append(bird)
                    user_birds = remaining
                    self.bot.db.save_inventory(guild_id, user_id, user_birds)

                self.gamble_losses[key] = self.gamble_losses.get(key, 0) + 1
                if self.gamble_losses[key] >= 3:
                    await self.unlock_achievement(user_id, "triple_loss", interaction.channel, guild_id)
                    self.gamble_losses[key] = 0

                if not shield_saved:
                    bird_value = self.bot.bird_values.get(matched_bird_name, 0)
                    if number * bird_value >= 20:
                        await self.unlock_achievement(user_id, "skill_issue", interaction.channel, guild_id)

                await self.unlock_achievement(user_id, "aww_dang_it", interaction.channel, guild_id)
                if is_all:
                    await self.unlock_achievement(user_id, "its_over", interaction.channel, guild_id)

                description = f"💀 **{interaction.user.mention}** lost the gamble and their **{number}x {matched_bird_name}** vanished..."
                if shield_saved:
                    description += "\n🛡️ **Your Shield protected your birds!**"

                embed = discord.Embed(
                    title="🎰 Gamble Lost!",
                    description=description,
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

            receiver_birds = self.bot.db.get_inventory(guild_id, receiver_id)
            if len(receiver_birds) == 0:
                await self.unlock_achievement(sender_id, "nice_guy", interaction.channel, guild_id)

            sender_birds = self.bot.db.get_inventory(guild_id, sender_id)
            current_count = sender_birds.count(matched_bird_name)

            if current_count < number:
                await interaction.followup.send(f"❌ You don't have enough **{matched_bird_name}**! You have `{current_count}`.", ephemeral=True)
                return

            remaining = []
            removed = 0
            for bird in sender_birds:
                if bird == matched_bird_name and removed < number:
                    removed += 1
                else:
                    remaining.append(bird)
            sender_birds = remaining
            self.bot.db.save_inventory(guild_id, sender_id, sender_birds)

            receiver_birds.extend([matched_bird_name] * number)
            self.bot.db.save_inventory(guild_id, receiver_id, receiver_birds)

            self.check_stat_achievements(member.id, interaction.guild.id, interaction.channel)

            bird_value = matched_bird.get("value", 0)
            if bird_value > 13:
                await self.unlock_achievement(interaction.user.id, "giveaway", interaction.channel, guild_id=interaction.guild.id)

            if self.rarest_bird:
                if self.rarest_bird["name"].lower() == matched_bird_name.lower():
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