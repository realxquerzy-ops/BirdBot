from collections import Counter

import discord
from discord.ext import commands


class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_inventory_value(self, user_birds):
        return sum(self.bot.bird_values.get(bird, 1) for bird in user_birds)

    @discord.app_commands.command(name="droprates", description="View the spawn chance percentages and values of each bird")
    @discord.app_commands.allowed_installs(guilds=True, users=True)
    @discord.app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def droprates(self, interaction: discord.Interaction):
        await interaction.response.defer()
        total_weight = sum(float(bird["weight"]) for bird in self.bot.birds)
        rates_text = ""

        for bird in self.bot.birds:
            percentage = (float(bird["weight"]) / total_weight) * 100 if total_weight > 0 else 0.0
            rates_text += f"• **{bird['name']}** (Value: `{bird['value']}`): `{percentage:.2f}%`\n"

        embed = discord.Embed(
            title="📊 Bird Spawn Drop Rates & Values",
            description=rates_text,
            color=discord.Color.blue()
        )
        embed.set_footer(text="Higher rarity means higher value and lower drop rate!")
        await interaction.followup.send(embed=embed)

    @discord.app_commands.command(name="inventory", description="View your caught birds inventory for this server")
    @discord.app_commands.describe(member="View another user's inventory")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def inventory(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server!")
            return

        guild_id = interaction.guild.id
        target = member or interaction.user

        if target.id == self.bot.user.id:
            BIRDBOT_COUNT = 2**31 - 1
            bird_counts = {bird["name"]: BIRDBOT_COUNT for bird in self.bot.birds}
            total_val = sum(self.bot.bird_values.get(name, 1) * count for name, count in bird_counts.items())
            total_birds = sum(bird_counts.values())
            inventory_text = "\n".join([
                f"• **{bird}** (Value: {self.bot.bird_values.get(bird, 1)}): `{count:,}x`"
                for bird, count in bird_counts.items()
            ])
            embed = discord.Embed(
                title=f"📦 {target.name}'s Server Bird Inventory",
                description=inventory_text + f"\n\n💎 **Total Inventory Value:** `{total_val:,}` points",
                color=discord.Color.green()
            )
            embed.set_footer(text=f"Total Birds Caught Here: {total_birds:,}")
            await interaction.followup.send(embed=embed)
            return

        user_birds = self.bot.db.get_inventory(guild_id, target.id)

        if not user_birds:
            embed = discord.Embed(
                title=f"📦 {target.name}'s Server Inventory",
                description=f"{'You have' if target == interaction.user else target.name + ' has'} no birds in this server yet!",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            return

        bird_counts = Counter(user_birds)
        total_val = self.get_inventory_value(user_birds)
        inventory_text = "\n".join([f"• **{bird}** (Value: {self.bot.bird_values.get(bird, 1)}): `{count}x`" for bird, count in bird_counts.items()])

        embed = discord.Embed(
            title=f"📦 {target.name}'s Server Bird Inventory",
            description=inventory_text + f"\n\n💎 **Total Inventory Value:** `{total_val}` points",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Total Birds Caught Here: {len(user_birds)}")
        await interaction.followup.send(embed=embed)

    @discord.app_commands.command(name="leaderboard", description="View the top bird value leaderboard for this server")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server!")
            return

        guild_id = interaction.guild.id
        rows = self.bot.db.fetchall(
            "SELECT user_id, birds FROM inventories WHERE guild_id = %s", (guild_id,)
        )

        if not rows:
            embed = discord.Embed(
                title="🏆 Server Bird Value Leaderboard",
                description="No birds have been caught in this server yet!",
                color=discord.Color.orange()
            )
            await interaction.followup.send(embed=embed)
            return

        user_totals = []
        for row in rows:
            user_id = row[0]
            if int(user_id) == self.bot.user.id:
                continue
            birds = self.bot.db._loads_json(row[1])
            user_totals.append((user_id, self.get_inventory_value(birds), len(birds)))

        user_totals.sort(key=lambda x: x[1], reverse=True)
        top_users = user_totals[:10]

        lb_text = ""
        for index, (user_id, total_val, total_count) in enumerate(top_users, start=1):
            try:
                user = await self.bot.fetch_user(int(user_id))
                username = user.name
            except Exception:
                username = f"User_{user_id}"

            medal = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else f"`#{index}`"
            lb_text += f"{medal} **{username}** — `{total_val}` points *({total_count} birds)*\n"

        embed = discord.Embed(
            title="🏆 Server Bird Value Leaderboard (Top 10)",
            description=lb_text,
            color=discord.Color.gold()
        )
        await interaction.followup.send(embed=embed)

        if top_users:
            top_id = top_users[0][0]
            games_cog = self.bot.get_cog("GamesCog")
            if games_cog and top_users[0][1] > 0:
                games_cog.bot.loop.create_task(
                    games_cog.unlock_achievement(top_id, "top_1", interaction.channel, guild_id=guild_id)
                )

    def merge_recipes(self):
        birds = [b["name"] for b in self.bot.birds]
        merge_cost = {}
        merge_next = {}
        for i in range(len(birds) - 2):
            src = birds[i]
            merge_cost[src] = 2 + i // 2
            merge_next[src] = birds[i + 1]
        return merge_cost, merge_next

    @discord.app_commands.command(name="merge", description="Merge birds into rarer birds (e.g. 2 Bird → 1 Good Bird)")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def merge(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
            return

        guild_id = interaction.guild.id
        counts = Counter(self.bot.db.get_inventory(guild_id, interaction.user.id))
        merge_cost, merge_next = self.merge_recipes()

        view = MergeView(self.bot, guild_id, merge_cost, merge_next)
        msg = await interaction.followup.send(
            embed=MergeView.build_chart(merge_cost, merge_next, counts),
            view=view,
            ephemeral=True
        )
        view._msg = msg


class MergeSelect(discord.ui.Select):
    def __init__(self, bot, merge_cost, merge_next):
        options = []
        for src in merge_cost:
            options.append(discord.SelectOption(
                label=f"{src} → {merge_next[src]}",
                value=src,
                description=f"{merge_cost[src]}x {src} = 1x {merge_next[src]}"
            ))
        super().__init__(placeholder="Which bird do you want to merge?", options=options[:25], row=0)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        src = self.values[0]
        counts = Counter(view.bot.db.get_inventory(int(view.guild_id), interaction.user.id))
        cost = view.merge_cost[src]
        max_merges = counts.get(src, 0) // cost
        if max_merges < 1:
            await interaction.response.send_message("❌ You don't have enough of that bird anymore!", ephemeral=True)
            return
        await interaction.response.send_modal(MergeModal(view, src, view.merge_next[src], cost, max_merges))


class MergeModal(discord.ui.Modal):
    def __init__(self, view, src, nxt, cost, max_merges):
        super().__init__(title=f"🔀 Merge {src} ×{cost} → {nxt}")
        self.view = view
        self.src = src
        self.nxt = nxt
        self.cost = cost
        self.max_merges = max_merges
        self.count_input = discord.ui.TextInput(
            label=f"How many merges? (1-{max_merges})",
            placeholder="Enter a number...",
            min_length=1,
            max_length=4,
            default="1"
        )
        self.add_item(self.count_input)

    async def on_submit(self, interaction):
        try:
            n = int(self.count_input.value)
            if n < 1 or n > self.max_merges:
                raise ValueError()
        except ValueError:
            await interaction.response.send_message(f"❌ Enter a number between 1 and {self.max_merges}!", ephemeral=True)
            return

        await interaction.response.defer()
        guild_id = int(self.view.guild_id)
        inv = self.view.bot.db.get_inventory(guild_id, interaction.user.id)
        counts = Counter(inv)
        need = self.cost * n
        if counts.get(self.src, 0) < need:
            await interaction.followup.send("❌ You don't have enough birds anymore!", ephemeral=True)
            return

        removed = 0
        new_inv = []
        for b in inv:
            if b == self.src and removed < need:
                removed += 1
                continue
            new_inv.append(b)
        new_inv.extend([self.nxt] * n)
        self.view.bot.db.save_inventory(guild_id, interaction.user.id, new_inv)

        try:
            await self.view._msg.edit(embed=MergeView.build_chart(
                self.view.merge_cost, self.view.merge_next, Counter(new_inv)
            ), view=self.view)
        except Exception:
            pass

        embed = discord.Embed(
            title="🔀 Merge Complete!",
            description=f"**{self.src}** ×{self.cost} → **{self.nxt}**\nYou merged **{n}** time{'s' if n != 1 else ''} and now own **{n}x {self.nxt}**.",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


class MergeView(discord.ui.View):
    def __init__(self, bot, guild_id, merge_cost, merge_next):
        super().__init__(timeout=120)
        self.bot = bot
        self.guild_id = str(guild_id)
        self.merge_cost = merge_cost
        self.merge_next = merge_next
        self._msg = None
        self.add_item(MergeSelect(bot, merge_cost, merge_next))

    @staticmethod
    def build_chart(merge_cost, merge_next, counts=None):
        lines = []
        for src, cost in merge_cost.items():
            nxt = merge_next[src]
            has = counts.get(src, 0) if counts else 0
            poss = has // cost if counts else 0
            lines.append(f"• **{src}** ×{cost} → **{nxt}**" + (f" `({poss} possible)`" if counts else ""))
        embed = discord.Embed(
            title="🔀 Merge Birds",
            description="\n".join(lines) + "\n\n⚡ **Caseoh Bird** cannot be merged.",
            color=discord.Color.purple()
        )
        embed.set_footer(text="Pick a bird below to merge it into a rarer bird.")
        return embed


async def setup(bot):
    await bot.add_cog(EconomyCog(bot))