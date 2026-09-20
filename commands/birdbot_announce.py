import discord
from discord.ext import commands

RESOURCE_GUILD_ID = 1511406716749611171
ANNOUNCE_CHANNEL_ID = 1550550681767645244
BOOST_CHANNEL_ID = 1550211298447466606
ANNOUNCE_ROLE_ID = 1550550942724915272

BOOST_THRESHOLDS = {0: 2, 1: 7, 2: 14}
BOOST_COLORS = {
    0: discord.Color.light_gray(),
    1: discord.Color.green(),
    2: discord.Color.blue(),
    3: discord.Color.purple(),
}


class BirdBotAnnounceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._last_boost_count = None
        self._started = False
        self._ensure_tables()

    def _ensure_tables(self):
        self.bot.db.execute("""
            CREATE TABLE IF NOT EXISTS bot_messages (
                guild_id BIGINT,
                kind TEXT,
                channel_id BIGINT,
                message_id BIGINT,
                PRIMARY KEY (guild_id, kind)
            )
        """)

    async def _get_tracked_msg(self, guild_id, kind):
        row = self.bot.db.fetchone(
            "SELECT channel_id, message_id FROM bot_messages WHERE guild_id = %s AND kind = %s",
            (guild_id, kind),
        )
        if not row:
            return None, None
        return row[0], row[1]

    async def _set_tracked_msg(self, guild_id, kind, channel_id, message_id):
        self.bot.db.execute(
            """
            INSERT INTO bot_messages (guild_id, kind, channel_id, message_id) VALUES (%s, %s, %s, %s)
            ON CONFLICT (guild_id, kind) DO UPDATE SET channel_id = EXCLUDED.channel_id, message_id = EXCLUDED.message_id
            """,
            (guild_id, kind, channel_id, message_id),
        )

    async def _send_or_update(self, guild_id, kind, channel_id, embed):
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return None

        channel = guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception:
                return None

        stored_ch, msg_id = await self._get_tracked_msg(guild_id, kind)
        if msg_id:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(embed=embed)
                return msg
            except Exception:
                pass

        msg = await channel.send(embed=embed)
        await self._set_tracked_msg(guild_id, kind, channel.id, msg.id)
        return msg

    def _announce_embed(self):
        return discord.Embed(
            title="🐦 BirdBot Announcements",
            description=(
                "**React with :bird: for Announcements Ping** or "
                "**react with :black_bird: for Hall of Bird Ping**"
            ),
            color=discord.Color.blue(),
        )

    def _boost_embed(self, guild):
        tier = guild.premium_tier
        boosts = guild.premium_subscription_count
        color = BOOST_COLORS.get(tier, discord.Color.default())

        embed = discord.Embed(
            title=f"🚀 Server Boosts — {guild.name}",
            color=color,
        )
        embed.add_field(name="Tier", value=f"{tier}/3", inline=True)
        embed.add_field(name="Active Boosts", value=str(boosts), inline=True)

        target = BOOST_THRESHOLDS.get(tier)
        if target is not None:
            needed = max(target - boosts, 0)
            bar = "🟩" * min(boosts, target) + "⬜" * min(needed, target)
            embed.add_field(
                name=f"Next Tier (Tier {tier + 1})",
                value=f"{bar}\n**{boosts}/{target}** boosts ({needed} more needed)",
                inline=False,
            )
        else:
            embed.add_field(name="Next Tier", value="Max tier reached! 🏆", inline=False)

        embed.set_footer(text="Updates automatically on every boost/unboost.")
        return embed

    @commands.Cog.listener()
    async def on_ready(self):
        if self._started:
            return
        self._started = True

        # Announcement message (sticky embed) for the resource guild
        await self._send_or_update(
            RESOURCE_GUILD_ID, "announce", ANNOUNCE_CHANNEL_ID, self._announce_embed()
        )

        # Try to add reactions to the announce message if missing
        try:
            _, msg_id = await self._get_tracked_msg(RESOURCE_GUILD_ID, "announce")
            if msg_id:
                channel = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)
                if channel:
                    msg = await channel.fetch_message(msg_id)
                    for emoji in ("🐦", "🖤"):
                        try:
                            await msg.add_reaction(emoji)
                        except Exception:
                            pass
        except Exception:
            pass

        # Boost info (single embed, updated on boost/unboost)
        guild = self.bot.get_guild(RESOURCE_GUILD_ID)
        if guild:
            self._last_boost_count = guild.premium_subscription_count
            await self._send_or_update(
                RESOURCE_GUILD_ID, "boost", BOOST_CHANNEL_ID, self._boost_embed(guild)
            )

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        if after.id != RESOURCE_GUILD_ID:
            return
        if (
            before.premium_subscription_count != after.premium_subscription_count
            or before.premium_tier != after.premium_tier
        ):
            if self._last_boost_count == after.premium_subscription_count:
                return
            self._last_boost_count = after.premium_subscription_count
            await self._send_or_update(
                RESOURCE_GUILD_ID, "boost", BOOST_CHANNEL_ID, self._boost_embed(after)
            )

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.guild.id != RESOURCE_GUILD_ID:
            return
        if before.premium_since != after.premium_since:
            guild = self.bot.get_guild(RESOURCE_GUILD_ID)
            if guild and self._last_boost_count != guild.premium_subscription_count:
                self._last_boost_count = guild.premium_subscription_count
                await self._send_or_update(
                    RESOURCE_GUILD_ID, "boost", BOOST_CHANNEL_ID, self._boost_embed(guild)
                )

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot:
            return

        if reaction.message.guild.id != RESOURCE_GUILD_ID:
            return

        guild = reaction.message.guild
        role = guild.get_role(ANNOUNCE_ROLE_ID)
        if role is None or user.id == guild.me.id:
            return

        channel = guild.get_channel(ANNOUNCE_CHANNEL_ID)
        if str(reaction.emoji) == "🐦":
            try:
                await user.add_roles(role)
                if channel:
                    embed = discord.Embed(
                        title="📢 Announcements Ping",
                        description=f"<@!{user.id}> has been pings for announcements!",
                        color=discord.Color.green(),
                    )
                    await channel.send(embed=embed, delete_after=5)
            except Exception as e:
                print(f"Error adding announcements role: {e}")

        elif str(reaction.emoji) == "🖤":
            try:
                await user.add_roles(role)
                if channel:
                    embed = discord.Embed(
                        title="🏆 Hall of Bird",
                        description=f"<@!{user.id}> has entered the Hall of Bird!",
                        color=discord.Color.gold(),
                    )
                    await channel.send(embed=embed, delete_after=5)
            except Exception as e:
                print(f"Error adding Hall of Bird role: {e}")


async def setup(bot):
    await bot.add_cog(BirdBotAnnounceCog(bot))