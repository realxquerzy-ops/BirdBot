import discord
from discord.ext import commands


class GlobalCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="glb", description="View global and advanced leaderboards with filters and fastest times")
    @discord.app_commands.describe(
        filter_by="Choose how to sort the leaderboard",
        server_id="Filter by specific server ID (leave empty for global)"
    )
    @discord.app_commands.choices(filter_by=[
        discord.app_commands.Choice(name="Total Value (Default)", value="value"),
        discord.app_commands.Choice(name="Bird Count", value="count"),
        discord.app_commands.Choice(name="Fastest Time", value="fastest_time"),
        discord.app_commands.Choice(name="Server Total Value", value="server_value"),
        discord.app_commands.Choice(name="Server Bird Count", value="server_count"),
        discord.app_commands.Choice(name="Server Fastest Time", value="server_fastest_time")
    ])
    @discord.app_commands.allowed_installs(guilds=True, users=True)
    @discord.app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def global_leaderboard(self, interaction: discord.Interaction, filter_by: str = "value", server_id: str = None):
        await interaction.response.defer(ephemeral=False)
        try:
            fastest_times = getattr(self.bot, "fastest_times", {})
            bird_values = self.bot.bird_values_lower

            # --- SUNUCU BAZLI FİLTRELER ---
            if filter_by in ["server_value", "server_count", "server_fastest_time"]:
                rows = self.bot.db.fetchall("SELECT guild_id, user_id, birds FROM inventories")

                if not rows:
                    await interaction.followup.send("❌ No inventory data found yet!", ephemeral=True)
                    return

                server_inventories_map = {}
                for row in rows:
                    g_id, u_id, birds_json = str(row[0]), str(row[1]), row[2]
                    server_inventories_map.setdefault(g_id, {})[u_id] = self.bot.db._loads_json(birds_json)

                server_stats = {}
                for g_id, users_dict in server_inventories_map.items():
                    try:
                        guild_obj = self.bot.get_guild(int(g_id))
                        g_name = guild_obj.name if guild_obj else f"Server ({g_id})"
                    except Exception:
                        g_name = f"Server ({g_id})"

                    total_v = 0
                    total_c = 0
                    server_best_time = float('inf')

                    for u_id, birds_list in users_dict.items():
                        total_c += len(birds_list)
                        total_v += sum(bird_values.get(b_name.lower(), 0) for b_name in birds_list)

                        if u_id in fastest_times and fastest_times[u_id] < server_best_time:
                            server_best_time = fastest_times[u_id]

                    if server_best_time == float('inf'):
                        server_best_time = 0.0

                    server_stats[g_name] = {"value": total_v, "count": total_c, "fastest_time": server_best_time}

                sort_map = {"server_value": "value", "server_count": "count", "server_fastest_time": "fastest_time"}
                sort_key = sort_map[filter_by]
                is_reverse = False if filter_by == "server_fastest_time" else True
                sorted_servers = sorted(server_stats.items(), key=lambda x: x[1][sort_key], reverse=is_reverse)[:10]

                embed = discord.Embed(
                    title=f"🌐 Global Server Leaderboard ({filter_by.replace('_', ' ').capitalize()})",
                    color=discord.Color.gold()
                )

                desc_lines = []
                for idx, (s_name, stats) in enumerate(sorted_servers, 1):
                    medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"`#{idx}`"
                    time_display = f"{stats['fastest_time']:.2f}s" if stats['fastest_time'] > 0 else "N/A"
                    desc_lines.append(f"{medal} **{s_name}** — Val: `{stats['value']}` | Birds: `{stats['count']}` | Time: `{time_display}`")

                embed.description = "\n".join(desc_lines) if desc_lines else "No data available."
                await interaction.followup.send(embed=embed)
                return

            # --- OYUNCU BAZLI FİLTRELER ---
            if server_id:
                rows = self.bot.db.fetchall(
                    "SELECT user_id, birds FROM inventories WHERE guild_id = %s", (int(server_id),)
                )
            else:
                rows = self.bot.db.fetchall("SELECT user_id, birds FROM inventories")

            if not rows:
                await interaction.followup.send("❌ No inventory data found yet!", ephemeral=True)
                return

            user_stats = {}
            for row in rows:
                u_id = str(row[0])
                birds_list = self.bot.db._loads_json(row[1])
                if u_id not in user_stats:
                    user_stats[u_id] = {
                        "value": 0,
                        "count": 0,
                        "fastest_time": fastest_times.get(u_id, 0.0)
                    }

                user_stats[u_id]["count"] += len(birds_list)
                user_stats[u_id]["value"] += sum(bird_values.get(b_name.lower(), 0) for b_name in birds_list)

            if not user_stats:
                await interaction.followup.send("❌ No data found for this filter/scope!", ephemeral=True)
                return

            if filter_by == "value":
                sort_key = "value"
                is_reverse = True
            elif filter_by == "count":
                sort_key = "count"
                is_reverse = True
            else:  # fastest_time
                sort_key = "fastest_time"
                user_stats = {k: v for k, v in user_stats.items() if v["fastest_time"] > 0}
                if not user_stats:
                    await interaction.followup.send("❌ No fastest time data available yet!", ephemeral=True)
                    return
                is_reverse = False

            sorted_users = sorted(user_stats.items(), key=lambda x: x[1][sort_key], reverse=is_reverse)[:10]

            scope_text = f" in Server ID `{server_id}`" if server_id else " (Global)"
            embed = discord.Embed(
                title=f"🌐 Leaderboard{scope_text} — {filter_by.replace('_', ' ').capitalize()}",
                color=discord.Color.blurple()
            )

            desc_lines = []
            for idx, (u_id, stats) in enumerate(sorted_users, 1):
                medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"`#{idx}`"
                time_display = f"{stats['fastest_time']:.2f}s" if stats['fastest_time'] > 0 else "N/A"
                desc_lines.append(f"{medal} <@{u_id}> — Val: `{stats['value']}` | Birds: `{stats['count']}` | Time: `{time_display}`")

            embed.description = "\n".join(desc_lines)
            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"Error in glb command: {e}")
            await interaction.followup.send("❌ An error occurred while generating the leaderboard.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(GlobalCog(bot))