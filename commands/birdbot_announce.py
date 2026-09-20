import discord
from discord.ext import commands


class BirdBotAnnounceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Send the announcement message to the resource guild
        guild_id = 1511406716749611171
        channel_id = 1550550681767645244

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return

        channel = guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception:
                return

        # Send the announcement message
        msg = await channel.send(
            "React with :bird: for Announcements Ping or :black_bird: for Hall of Bird Ping"
        )

        # Add reactions
        try:
            await msg.add_reaction("🐦")
        except Exception:
            pass

        try:
            await msg.add_reaction("🖤")
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        # Ignore bot reactions
        if user.bot:
            return

        # Check if the reaction is on our message in the resource guild
        if reaction.message.guild.id != 1511406716749611171:
            return

        # Get the announcements/role channel
        guild = reaction.message.guild
        role_id = 1550550942724915272
        role = guild.get_role(role_id)

        # Check for :bird: reaction - Announcements Ping role
        if str(reaction.emoji) == "🐦":
            if role and user.id != guild.me.id:
                try:
                    await user.add_roles(role)
                    embed = discord.Embed(
                        title="📢 Announcements Ping",
                        description=f"<@!{user.id}> has been pings for announcements!",
                        color=discord.Color.green(),
                    )
                    # Send confirmation to the same channel
                    channel = guild.get_channel(1550550681767645244)
                    if channel:
                        await channel.send(embed=embed, delete_after=5)
                except Exception as e:
                    print(f"Error adding announcements role: {e}")

        # Check for :black_bird: reaction - Hall of Bird role
        if str(reaction.emoji) == "🖤":
            # Try to get Hall of Bird role (same ID or try to find another)
            hall_role_id = 1550550942724915272  # Using same ID, adjust if needed
            hall_role = guild.get_role(hall_role_id)
            if hall_role and user.id != guild.me.id:
                try:
                    await user.add_roles(hall_role)
                    embed = discord.Embed(
                        title="🏆 Hall of Bird",
                        description=f"<@!{user.id}> has entered the Hall of Bird!",
                        color=discord.Color.gold(),
                    )
                    # Send confirmation to the same channel
                    channel = guild.get_channel(1550550681767645244)
                    if channel:
                        await channel.send(embed=embed, delete_after=5)
                except Exception as e:
                    print(f"Error adding Hall of Bird role: {e}")


async def setup(bot):
    await bot.add_cog(BirdBotAnnounceCog(bot))