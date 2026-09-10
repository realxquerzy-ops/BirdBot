import random

import discord
from discord.ext import commands


class PowerupsCog(commands.Cog):
    POWERUPS = {
        "shield": {"name": "🛡️ Shield", "desc": "Protects your birds from one gamble or fight loss", "type": "self"},
        "double_xp": {"name": "⚡ Double XP", "desc": "2x BirdPass XP for your next 5 catches", "type": "self"},
        "double_catch": {"name": "🍀 Lucky Net", "desc": "20% chance to double your bird for the next 5 catches", "type": "self"},
        "sab_miss": {"name": "🪃 Distraction", "desc": "Makes a player's next catch fail (bird escapes)", "type": "sabotage"},
        "sab_half_xp": {"name": "📉 Demotivate", "desc": "Halves a player's BirdPass XP for their next 3 catches", "type": "sabotage"},
        "sab_steal": {"name": "🕵️ Pocket", "desc": "Instantly steal 1 random bird from a player", "type": "sabotage"},
    }

    DROP_WEIGHTS = {
        "shield": 20,
        "double_xp": 25,
        "double_catch": 15,
        "sab_miss": 15,
        "sab_half_xp": 15,
        "sab_steal": 10,
    }

    def __init__(self, bot):
        self.bot = bot
        self.effects = {}
        self.sabo = {}

    def _self_entry(self, guild_id, user_id):
        key = (int(guild_id), int(user_id))
        return self.effects.setdefault(key, {})

    def _sabo_entry(self, guild_id, user_id):
        key = (int(guild_id), int(user_id))
        return self.sabo.setdefault(key, {})

    def random_drop(self):
        return random.choices(
            list(self.DROP_WEIGHTS),
            weights=list(self.DROP_WEIGHTS.values()),
            k=1,
        )[0]

    def catch_effects(self, guild_id, user_id):
        entry = self._self_entry(guild_id, user_id)
        xp_mult = 1.0
        if entry.get("double_xp", 0) > 0:
            xp_mult = 2.0
            entry["double_xp"] -= 1
            if entry.get("double_xp", 0) <= 0:
                entry.pop("double_xp", None)
        double_catch = False
        if entry.get("double_catch", 0) > 0:
            double_catch = True
            entry["double_catch"] -= 1
            if entry.get("double_catch", 0) <= 0:
                entry.pop("double_catch", None)
        return xp_mult, double_catch

    def consume_miss(self, guild_id, user_id):
        entry = self._sabo_entry(guild_id, user_id)
        if entry.get("miss", False):
            entry["miss"] = False
            return True
        return False

    def consume_half_xp(self, guild_id, user_id):
        entry = self._sabo_entry(guild_id, user_id)
        if entry.get("half_xp", 0) > 0:
            entry["half_xp"] -= 1
            if entry.get("half_xp", 0) <= 0:
                entry.pop("half_xp", None)
            return True
        return False

    def has_shield(self, guild_id, user_id):
        return self._self_entry(guild_id, user_id).get("shield", 0) > 0

    def consume_shield(self, guild_id, user_id):
        entry = self._self_entry(guild_id, user_id)
        if entry.get("shield", 0) > 0:
            entry["shield"] -= 1
            if entry.get("shield", 0) <= 0:
                entry.pop("shield", None)
            return True
        return False

    def active_self_text(self, guild_id, user_id):
        entry = self._self_entry(guild_id, user_id)
        parts = []
        if entry.get("shield", 0) > 0:
            parts.append(f"🛡️ Shield: `{entry['shield']}`")
        if entry.get("double_xp", 0) > 0:
            parts.append(f"⚡ Double XP: `{entry['double_xp']}` catches left")
        if entry.get("double_catch", 0) > 0:
            parts.append(f"🍀 Lucky Net: `{entry['double_catch']}` catches left")
        return " | ".join(parts) if parts else None

    @discord.app_commands.command(name="powerups", description="View your powerups and active effects")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def powerups_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
            return

        guild_id = interaction.guild.id
        user_id = interaction.user.id

        owned = self.bot.db.get_powerups(guild_id, user_id)
        lines = []
        for powerup in sorted(self.POWERUPS):
            qty = owned.get(powerup, 0)
            if qty > 0:
                info = self.POWERUPS[powerup]
                lines.append(f"{info['name']} — `{qty}x`\n└ *{info['desc']}*")

        active = self.active_self_text(guild_id, user_id)
        if lines:
            inventory_text = "\n".join(lines)
        else:
            inventory_text = "Nothing yet! Win fights to earn powerups."

        embed = discord.Embed(
            title=f"🎒 {interaction.user.name}'s Powerups",
            description=inventory_text + (f"\n\n✨ **Active:** {active}" if active else ""),
            color=discord.Color.purple()
        )
        embed.set_footer(text="Use powerups with /use. Sabotage powerups target other players!")
        await interaction.followup.send(embed=embed)

    @discord.app_commands.command(name="use", description="Use a self powerup or sabotage another player")
    @discord.app_commands.describe(powerup="Which powerup to use", member="Target player (required for sabotage powerups)")
    @discord.app_commands.choices(powerup=[
        discord.app_commands.Choice(name="🛡️ Shield", value="shield"),
        discord.app_commands.Choice(name="⚡ Double XP", value="double_xp"),
        discord.app_commands.Choice(name="🍀 Lucky Net", value="double_catch"),
        discord.app_commands.Choice(name="🪃 Distraction", value="sab_miss"),
        discord.app_commands.Choice(name="📉 Demotivate", value="sab_half_xp"),
        discord.app_commands.Choice(name="🕵️ Pocket", value="sab_steal"),
    ])
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def use(self, interaction: discord.Interaction, powerup: str, member: discord.Member = None):
        await interaction.response.defer()
        try:
            if not interaction.guild:
                await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
                return

            guild_id = interaction.guild.id
            user_id = interaction.user.id
            info = self.POWERUPS.get(powerup)
            if not info:
                await interaction.followup.send("❌ Unknown powerup!", ephemeral=True)
                return

            if info["type"] == "self":
                if member is not None:
                    await interaction.followup.send("❌ Self powerups can only be used on yourself!", ephemeral=True)
                    return
            else:
                if member is None:
                    await interaction.followup.send("❌ You must choose a target for this powerup!", ephemeral=True)
                    return
                if member.bot or member.id == user_id:
                    await interaction.followup.send("❌ You cannot sabotage bots or yourself!", ephemeral=True)
                    return

            owned = self.bot.db.get_powerups(guild_id, user_id)
            if owned.get(powerup, 0) <= 0:
                await interaction.followup.send(f"❌ You don't have a **{info['name']}**! Win fights to earn one.", ephemeral=True)
                return

            if powerup == "sab_steal":
                target_inv = self.bot.db.get_inventory(guild_id, member.id)
                if not target_inv:
                    await interaction.followup.send("❌ That player has no birds to steal!", ephemeral=True)
                    return

            self.bot.db.remove_powerup(guild_id, user_id, powerup, 1)

            if powerup == "shield":
                entry = self._self_entry(guild_id, user_id)
                entry["shield"] = entry.get("shield", 0) + 1
                desc = f"🛡️ **{interaction.user.mention}** equipped a Shield! Their birds are safe from the next loss."

            elif powerup == "double_xp":
                entry = self._self_entry(guild_id, user_id)
                entry["double_xp"] = 5
                desc = f"⚡ **{interaction.user.mention}** activated Double XP! +2x BirdPass XP for the next 5 catches."

            elif powerup == "double_catch":
                entry = self._self_entry(guild_id, user_id)
                entry["double_catch"] = 5
                desc = f"🍀 **{interaction.user.mention}** activated Lucky Net! 20% chance to double your bird for the next 5 catches."

            elif powerup == "sab_miss":
                entry = self._sabo_entry(guild_id, member.id)
                entry["miss"] = True
                desc = f"🪃 **{interaction.user.mention}** distracted **{member.mention}**! Their next catch will fail."

            elif powerup == "sab_half_xp":
                entry = self._sabo_entry(guild_id, member.id)
                entry["half_xp"] = entry.get("half_xp", 0) + 3
                desc = f"📉 **{interaction.user.mention}** demotivated **{member.mention}**! Half BirdPass XP for their next 3 catches."

            elif powerup == "sab_steal":
                stolen = random.choice(target_inv)
                target_inv.remove(stolen)
                self.bot.db.save_inventory(guild_id, member.id, target_inv)
                my_inv = self.bot.db.get_inventory(guild_id, user_id)
                my_inv.append(stolen)
                self.bot.db.save_inventory(guild_id, user_id, my_inv)
                desc = f"🕵️ **{interaction.user.mention}** pickpocketed **{member.mention}** and stole **1x {stolen}**!"

            embed = discord.Embed(
                title=f"🎒 {info['name']} Used!",
                description=desc,
                color=discord.Color.purple()
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            print(f"Error in use command: {e}")
            await interaction.followup.send("❌ An error occurred while executing this command.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(PowerupsCog(bot))