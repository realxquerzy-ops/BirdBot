from collections import Counter

import discord
from discord.ext import commands

from commands._safe import log_error, safe_ack


class RedeemCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _apply_rewards(self, guild_id, user_id, rewards):
        lines = []
        coins = int(rewards.get("coins", 0) or 0)
        birds = rewards.get("birds", []) or []
        powerups = rewards.get("powerups", {}) or {}

        if coins > 0:
            self.bot.db.add_birdcoin(guild_id, user_id, coins)
            lines.append(f"🪙 **{coins} BirdCoin**")

        if birds:
            names = {b["name"]: b["name"] for b in self.bot.birds}
            inventory = self.bot.db.get_inventory(guild_id, user_id)
            gained = []
            for bird in birds:
                if isinstance(bird, dict):
                    name = bird.get("name", "")
                    count = int(bird.get("count", 1) or 1)
                else:
                    name = str(bird)
                    count = 1
                if name not in names:
                    continue
                inventory.extend([name] * count)
                gained.append(f"{count}x {name}")
            if gained:
                self.bot.db.save_inventory(guild_id, user_id, inventory)
                lines.append("🐦 " + ", ".join(gained))

        if powerups:
            powerups_cog = self.bot.get_cog("PowerupsCog")
            add = self.bot.db.add_powerup
            gained = []
            for key, qty in powerups.items():
                qty = int(qty or 1)
                name = (powerups_cog.POWERUPS.get(key, {}).get("name") if powerups_cog else None) or key
                add(guild_id, user_id, key, qty)
                gained.append(f"{qty}x {name}")
            if gained:
                lines.append("✨ " + ", ".join(gained))

        return lines

    @discord.app_commands.command(name="redeem", description="Redeem a code for a reward!")
    @discord.app_commands.describe(code="The redeem code (e.g. bird012)")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def redeem(self, interaction: discord.Interaction, code: str):
        await interaction.response.defer()
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
            return

        guild_id = interaction.guild.id
        user_id = interaction.user.id
        code = code.strip().lower()

        try:
            status, rewards, remaining = self.bot.db.claim_redeem(guild_id, user_id, code)
        except Exception:
            log_error()
            await safe_ack(interaction, "❌ Something went wrong while redeeming. Please try again!")
            return

        if status == "invalid":
            await interaction.followup.send("❌ That redeem code doesn't exist. Check for typos!", ephemeral=True)
            return
        if status == "empty":
            await interaction.followup.send("❌ That code has already been fully redeemed!", ephemeral=True)
            return
        if status == "used":
            await interaction.followup.send("❌ You already redeemed this code!", ephemeral=True)
            return

        lines = self._apply_rewards(guild_id, user_id, rewards)
        if not lines:
            lines = ["Nothing (empty reward)"]

        embed = discord.Embed(
            title="🎟️ Code Redeemed!",
            description=f"**{interaction.user.mention}** redeemed `{code.upper()}` and got:\n" + "\n".join(f"• {l}" for l in lines),
            color=discord.Color.green()
        )
        embed.set_footer(text=f"{remaining} redemption{'s' if remaining != 1 else ''} left on this code.")
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(RedeemCog(bot))