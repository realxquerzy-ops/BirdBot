import asyncio
import random
import re
import time
from collections import Counter

import discord
from discord.ext import commands


from commands._safe import log_error, safe_ack
from mods import get_mods


def commit_value(bot, commit):
    return sum(bot.bird_values.get(b, 1) * n for b, n in commit.items())


def fmt_commit(commit):
    if not commit:
        return "None yet"
    return ", ".join(f"{n}x {b}" for b, n in sorted(commit.items()))


def parse_bird_counts(bot, text, inventory_counts):
    text = " ".join(text.split())
    if not text:
        return None
    names = sorted({b["name"] for b in bot.birds}, key=len, reverse=True)
    result = Counter()
    remaining = text
    for name in names:
        pat = re.compile(re.escape(name) + r"\s+(\d+)", re.IGNORECASE)
        while True:
            m = pat.search(remaining)
            if not m:
                break
            result[name] += int(m.group(1))
            remaining = (remaining[:m.start()] + " " + remaining[m.end():]).strip()
    if not result:
        return None
    for name, n in result.items():
        if n < 1:
            return None
        if n > inventory_counts.get(name, 0):
            return "insufficient"
    return dict(result)


def _make_fake_interaction(message):
    class _FakeResponse:
        async def edit_message(self, **kwargs):
            try:
                await message.edit(**kwargs)
            except:
                pass

        def is_done(self):
            return True

    class _FakeFollowup:
        async def edit_message(self, message_id=None, **kwargs):
            try:
                await message.edit(**kwargs)
            except:
                pass

        async def send(self, *args, **kwargs):
            return message

    class _FakeInteraction:
        def __init__(self):
            self.message = message
            self.response = _FakeResponse()
            self.followup = _FakeFollowup()
            self.channel = message.channel

        async def edit_original_response(self, **kwargs):
            try:
                await message.edit(**kwargs)
            except:
                pass

    return _FakeInteraction()


def transfer_birds(bot, guild_id, from_user, to_user, birds_list):
    src = bot.db.get_inventory(guild_id, from_user)
    dst = bot.db.get_inventory(guild_id, to_user)
    moved = []
    for b in birds_list:
        if b in src:
            src.remove(b)
            dst.append(b)
            moved.append(b)
    if moved:
        bot.db.save_inventory(guild_id, from_user, src)
        bot.db.save_inventory(guild_id, to_user, dst)
    return moved


def weighted_pick(inventory, k, bot):
    counts = Counter(inventory)
    birds = list(counts.keys())
    if not birds:
        return []

    weights = [1.0 / max(bot.bird_values.get(b, 1), 0.001) for b in birds]
    chosen = []
    remaining = list(birds)
    rem_w = list(weights)

    for _ in range(min(k, len(remaining))):
        idx = random.choices(range(len(remaining)), weights=rem_w, k=1)[0]
        chosen.append(remaining[idx])
        remaining.pop(idx)
        rem_w.pop(idx)
    return chosen


def deduct_birds(bot, guild_id, user_id, birds_list):
    inv = bot.db.get_inventory(guild_id, user_id)
    removed = []
    for b in birds_list:
        if b in inv:
            inv.remove(b)
            removed.append(b)
    if removed:
        bot.db.save_inventory(guild_id, user_id, inv)
    return removed


def survival_rate(elapsed):
    return max(0.25, 1.0 - elapsed / 60.0)


STATUS_TEXT = {
    discord.Status.online: "🟢 online",
    discord.Status.idle: "🌙 idle (AFK)",
    discord.Status.dnd: "🔴 do not disturb",
    discord.Status.offline: "⚫ offline",
    discord.Status.invisible: "⚫ invisible",
}


def is_active(bot, member):
    # Use real-time presence cache first, fall back to member.status
    cached_status = bot.presence_cache.get(member.id)
    status = cached_status if cached_status is not None else member.status
    print(f"[fight-check] {member} (ID: {member.id}) -> cache: {cached_status} | member.status: {member.status} | using: {status} | active: {status in (discord.Status.online, discord.Status.dnd) or time.time() - bot.last_active.get(member.id, 0) <= 120}")
    if status in (discord.Status.online, discord.Status.dnd):
        return True
    return time.time() - bot.last_active.get(member.id, 0) <= 120


def attack_roll(bot, atk_commit):
    total = commit_value(bot, atk_commit)
    chance = min(0.75, 0.20 + total / 60.0)
    steal_num = 1 + (1 if total >= 8 else 0) + (1 if total >= 40 else 0)
    return chance, min(steal_num, 3)


def fight_coin_reward(bot, atk_val, def_val):
    total = atk_val + def_val
    return int(5 + total * 0.4)


async def award_winner_rewards(bot, guild_id_int, winner, atk_val, def_val, channel=None):
    if getattr(winner, "id", None) == bot.user.id:
        return ""
    lines = []

    coins = fight_coin_reward(bot, atk_val, def_val)
    if coins > 0:
        try:
            bot.db.add_birdcoin(guild_id_int, winner.id, coins)
            lines.append(f"🪙 **{winner.name}** earned **{coins} BirdCoin**!")
        except Exception as e:
            print(f"[fight-reward] birdcoin error: {e}")

    birdpass_cog = bot.get_cog("BirdPassCog")
    if birdpass_cog:
        try:
            xp = int(10 + (atk_val + def_val) * 2)
            await birdpass_cog.award_battle_xp(guild_id_int, winner.id, channel, xp)
            lines.append(f"⚡ **{winner.name}** earned **{xp} BirdPass XP**!")
        except Exception as e:
            print(f"[fight-reward] birdpass error: {e}")

    return "\n".join(lines)


class FightAddModal(discord.ui.Modal):
    def __init__(self, select_item, view_instance):
        super().__init__(title="Send Birds to Battle")
        self.select_item = select_item
        self.view_instance = view_instance
        self.count_input = discord.ui.TextInput(
            label="How many?",
            placeholder="Enter a number...",
            min_length=1,
            max_length=3,
            default="1"
        )
        self.add_item(self.count_input)

    async def on_submit(self, interaction: discord.Interaction):
        view = self.view_instance
        owner_id = self.select_item.owner_id
        if interaction.user.id != owner_id:
            await interaction.response.send_message("❌ You cannot send the other player's birds!", ephemeral=True)
            return

        bird = self.select_item.selected_bird
        if not bird:
            await interaction.response.send_message("❌ Select a bird first!", ephemeral=True)
            return

        committed = view.commit[owner_id]
        pool = view.max_pool[owner_id]
        max_allowed = pool.get(bird, 0) - committed.get(bird, 0)

        try:
            val = int((self.count_input.value or "").strip())
            if val < 1 or val > max_allowed:
                raise ValueError()
        except ValueError:
            await interaction.response.send_message(
                f"❌ You can send up to `{max_allowed}` of this bird.", ephemeral=True
            )
            return

        committed[bird] = committed.get(bird, 0) + val
        try:
            await interaction.response.defer()
            await interaction.edit_original_response(content=None, embed=view.build_embed(), view=view)
        except Exception as e:
            import traceback
            print(f"[fight-modal] edit failed: {e}")
            traceback.print_exc()
            try:
                await interaction.response.edit_message(content=None, embed=view.build_embed(), view=view)
            except Exception:
                try:
                    await interaction.followup.send(content=None, embed=view.build_embed(), view=view)
                except Exception:
                    pass


class FightAddSelect(discord.ui.Select):
    def __init__(self, user_birds, owner_id, bird_values, placeholder, row=0, auto_battle=False):
        self.owner_id = owner_id
        self.auto_battle = auto_battle
        counts = Counter(user_birds)

        options = [
            discord.SelectOption(
                label=bird,
                description=f"Value: {bird_values.get(bird.lower(), 1)} | Owned: {counts[bird]}"
            )
            for bird in list(counts.keys())[:25]
        ]

        if not options:
            options = [discord.SelectOption(label="No birds available", description="You have no birds")]

        super().__init__(placeholder=placeholder, options=options, row=row)
        self.selected_bird = None

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ You cannot send the other player's birds!", ephemeral=True)
            return

        if self.values[0] == "No birds available":
            await interaction.response.send_message("❌ You don't have any birds to send!", ephemeral=True)
            return

        self.selected_bird = self.values[0]
        if self.auto_battle:
            view = self.view
            counts = Counter(view.def_inv)
            committed = view.def_commit.get(self.selected_bird, 0)
            remaining = counts.get(self.selected_bird, 0) - committed
            if remaining < 1:
                await interaction.response.send_message("❌ You already sent all of that bird!", ephemeral=True)
                return
            await interaction.response.send_modal(AutoBattleModal(view, self.selected_bird, remaining))
        else:
            await interaction.response.send_modal(FightAddModal(self, self.view))


class FightSetupView(discord.ui.View):
    def __init__(self, bot, attacker, target, guild_id, is_boss=False, friendly=False):
        super().__init__(timeout=60)
        self.bot = bot
        self.attacker = attacker
        self.target = target
        self.guild_id = str(guild_id)
        self.is_boss = is_boss
        self.friendly = friendly

        inv = bot.db.get_inventory(int(guild_id), attacker.id)
        self.max_pool = {attacker.id: Counter(inv)}
        self.commit = {attacker.id: Counter()}

        bird_values = {bird["name"].lower(): bird.get("value", 1) for bird in bot.birds}
        self.add_select = FightAddSelect(inv, attacker.id, bird_values, f"{attacker.name}: Send birds to battle", row=0)
        self.add_item(self.add_select)

    def build_embed(self):
        commit = self.commit[self.attacker.id]
        val = commit_value(self.bot, commit)
        friendly_line = "\n✨ **Friendly battle** — no birds lost, no powerups!" if self.friendly else ""
        embed = discord.Embed(
            title="⚔️ Friendly Challenge Setup" if self.friendly else "⚔️ Challenge Setup",
            description=(
                f"🔵 **{self.attacker.name}** commits to battle: **{fmt_commit(commit)}**\n"
                f"💪 Total battle power: `{int(val)}`\n\n"
                f"Select birds to send for the fight, then press **⚔️ Challenge!**"
                f"{friendly_line}"
            ),
            color=discord.Color.green() if self.friendly else discord.Color.blurple()
        )
        embed.set_footer(text="You can only send birds you actually own.")
        return embed

    @discord.ui.button(label="⚔️ Challenge!", style=discord.ButtonStyle.green, row=2)
    async def challenge(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.attacker.id:
            await interaction.response.send_message("❌ Only the challenger can send the challenge!", ephemeral=True)
            return

        if not self.commit[self.attacker.id]:
            await interaction.response.send_message("❌ Send at least one bird to battle first!", ephemeral=True)
            return

        await interaction.response.defer()

        if self.is_boss:
            view = BirdBotAutoBattleView(self.bot, self.attacker, self.target, self.guild_id, dict(self.commit[self.attacker.id]), friendly=self.friendly)
            view._expiry_msg = interaction.message
            await interaction.edit_original_response(content=None, embed=view.build_embed(), view=view)
            self.stop()
            return

        if self.target.id != self.bot.user.id:
            auto = self.bot.db.get_autodefend(int(self.guild_id), self.target.id)
            if auto:
                counts = Counter(self.bot.db.get_inventory(int(self.guild_id), self.target.id))
                if all(counts.get(b, 0) >= n for b, n in auto.items()):
                    def_inv = self.bot.db.get_inventory(int(self.guild_id), self.target.id)
                    view = AutoBattleView(
                        self.bot, self.attacker, self.target, self.guild_id,
                        dict(self.commit[self.attacker.id]), def_inv, friendly=self.friendly
                    )
                    view.autodefend = dict(auto)
                    view._turns = 2
                    view._expiry_msg = await interaction.channel.send(
                        content=f"🛡️ **{self.target.mention}** auto-defended against **{self.attacker.mention}**'s attack!",
                        embed=view.build_embed(),
                        view=view
                    )
                    await view.auto_defend_round(_make_fake_interaction(view._expiry_msg))
                    await interaction.edit_original_response(embed=discord.Embed(
                        title="📨 Auto-Defense Engaged!",
                        description=f"**{self.target.name}** is automatically fighting back against **{self.attacker.name}**!",
                        color=discord.Color.green()
                    ), view=None)
                    self.stop()
                    return

        view = FightChallengeView(self.bot, self.attacker, self.target, self.guild_id, dict(self.commit[self.attacker.id]), friendly=self.friendly)
        remaining = view._deadline - time.time()
        view._expiry_msg = await interaction.channel.send(
            content=f"⚔️ **{self.attacker.mention}** has challenged **{self.target.mention}** to a battle!",
            embed=view.build_embed(remaining),
            view=view
        )
        await interaction.edit_original_response(embed=discord.Embed(
            title="📨 Challenge Sent!",
            description=f"**{self.attacker.name}** sent a battle challenge to **{self.target.name}**!",
            color=discord.Color.green()
        ), view=None)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, row=2)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.attacker.id:
            await interaction.response.send_message("❌ Only the challenger can cancel!", ephemeral=True)
            return
        await interaction.response.edit_message(content="❌ Challenge cancelled.", embed=None, view=None)
        self.stop()

    async def on_timeout(self):
        msg = getattr(self, "_expiry_msg", None) or self.message
        if msg:
            try:
                await msg.edit(content="⏰ Challenge setup expired.", embed=None, view=None)
            except Exception:
                pass


class FightChallengeView(discord.ui.View):
    def __init__(self, bot, attacker, defender, guild_id, atk_commit, friendly=False):
        super().__init__(timeout=None)
        self.bot = bot
        self.attacker = attacker
        self.defender = defender
        self.guild_id = str(guild_id)
        self.atk_commit = atk_commit
        self.friendly = friendly
        self._resolving = False
        self._deadline = time.time() + max(5, int(get_mods(bot, guild_id).get("fight_ignore_sec", 60)))
        self._timer_task = asyncio.create_task(self._countdown())

    def stop(self):
        if getattr(self, "_resolving", False):
            super().stop()
            return
        task = getattr(self, "_timer_task", None)
        if task and not task.done():
            task.cancel()
        super().stop()

    def build_embed(self, remaining=None):
        val = commit_value(self.bot, self.atk_commit)
        timer_line = ""
        if remaining is not None:
            timer_line = (
                f"\n⏳ **{self.defender.name}** has `{max(0, int(remaining))}s` to respond!\n"
                f"💤 If time runs out, it counts as **Ignore** and the attacker may strike!"
            )
        friendly_line = "\n\n✨ **Friendly battle** — no birds lost, no powerups!" if self.friendly else ""
        return discord.Embed(
            title="⚔️ Friendly Battle Challenge!" if self.friendly else "⚔️ Battle Challenge!",
            description=(
                f"🔵 **{self.attacker.name}** is attacking with: **{fmt_commit(self.atk_commit)}**\n"
                f"💪 Total battle power: `{int(val)}`\n\n"
                f"**{self.defender.name}**, choose:\n"
                f"⚔️ **Fight Back** — send your own birds into battle\n"
                f"🕶️ **Ignore** — refuse the fight (the attacker may still strike!)"
                f"{timer_line}{friendly_line}"
            ),
            color=discord.Color.green() if self.friendly else discord.Color.blurple()
        )

    async def _countdown(self):
        try:
            while not self.is_finished():
                remaining = self._deadline - time.time()
                if remaining <= 0:
                    self._resolving = True
                    try:
                        await self._resolve_ignore()
                    except Exception as e:
                        print(f"[fight] auto-ignore error: {e}")
                        import traceback
                        traceback.print_exc()
                        msg = getattr(self, "_expiry_msg", None) or self.message
                        if msg:
                            try:
                                embed = discord.Embed(
                                    title="🕶️ Attack Missed!",
                                    description="**{0}** tried to attack **{1}** but the attack failed!".format(self.attacker.name, self.defender.name),
                                    color=discord.Color.greyple()
                                )
                                await msg.edit(content=None, embed=embed, view=None)
                            except Exception:
                                pass
                    self.stop()
                    return
                msg = getattr(self, "_expiry_msg", None) or self.message
                if msg:
                    try:
                        await msg.edit(embed=self.build_embed(remaining))
                    except Exception:
                        pass
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[fight] countdown error: {e}")
            import traceback
            traceback.print_exc()

    async def _resolve_ignore(self, interaction=None):
        if self.friendly:
            embed = discord.Embed(
                title="✨ Friendly Battle Cancelled!",
                description=f"**{self.defender.name}** declined the friendly battle — nothing happened, no birds lost.",
                color=discord.Color.greyple()
            )
            await self._finish(embed, interaction)
            return
        chance, steal_num = attack_roll(self.bot, self.atk_commit)
        guild_id_int = int(self.guild_id)

        if random.random() > chance:
            embed = discord.Embed(
                title="🕶️ Attack Missed!",
                description=(
                    f"**{self.attacker.name}** tried to strike **{self.defender.name}** "
                    f"but they dodged the attack! Nothing was stolen."
                ),
                color=discord.Color.greyple()
            )
            # Log: attacker lost
            try:
                self.bot.db.log_battle(guild_id_int, self.attacker.id, self.defender.id, self.defender.id,
                    dict(self.atk_commit), {}, {})
            except Exception as e:
                print(f"[battle-log] Failed to log battle: {e}")
            await self._finish(embed, interaction)
            return

        def_inv = self.bot.db.get_inventory(guild_id_int, self.defender.id)
        stolen = weighted_pick(def_inv, steal_num, self.bot)

        if not stolen:
            embed = discord.Embed(
                title="🕶️ Attack Missed!",
                description=f"**{self.attacker.name}** attacked but **{self.defender.name}** had no birds to steal!",
                color=discord.Color.greyple()
            )
            # Log: attacker lost (no birds to steal)
            try:
                self.bot.db.log_battle(guild_id_int, self.attacker.id, self.defender.id, self.defender.id,
                    dict(self.atk_commit), {}, {})
            except Exception as e:
                print(f"[battle-log] Failed to log battle: {e}")
            await self._finish(embed, interaction)
            return

        moved = transfer_birds(self.bot, guild_id_int, self.defender.id, self.attacker.id, stolen)

        if moved:
            atk_val = commit_value(self.bot, self.atk_commit)
            payout = await award_winner_rewards(
                self.bot, guild_id_int, self.attacker, atk_val, atk_val,
                getattr(self._expiry_msg, "channel", None)
            )
            embed = discord.Embed(
                title="⚔️ Raid Successful!",
                description=(
                    f"**{self.attacker.name}** ignored their refusal and raided **{self.defender.name}**!\n"
                    f"🕵️ Stolen: **{fmt_commit(Counter(moved))}**"
                    + (f"\n{payout}" if payout else "")
                ),
                color=discord.Color.orange()
            )
        else:
            embed = discord.Embed(
                title="🕶️ Attack Missed!",
                description=f"**{self.attacker.name}** attacked but found nothing left to steal!",
                color=discord.Color.greyple()
            )
        
        # Log: attacker won
        try:
            self.bot.db.log_battle(guild_id_int, self.attacker.id, self.defender.id, self.attacker.id,
                dict(self.atk_commit), {}, dict(Counter(moved)))
        except Exception as e:
            print(f"[battle-log] Failed to log battle: {e}")
        await self._finish(embed, interaction)

    async def _finish(self, embed, interaction=None):
        if interaction is not None and not interaction.response.is_done():
            try:
                await interaction.response.edit_message(content=None, embed=embed, view=None)
                self.stop()
                return
            except Exception:
                pass
        msg = getattr(self, "_expiry_msg", None) or self.message
        if msg:
            try:
                await msg.edit(content=None, embed=embed, view=None)
            except Exception:
                pass
        self.stop()

    @discord.ui.button(label="⚔️ Fight Back", style=discord.ButtonStyle.green, row=0)
    async def fight_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.defender.id:
            await interaction.response.send_message("❌ Only the challenged player can respond!", ephemeral=True)
            return

        await interaction.response.defer()

        try:
            def_inv = self.bot.db.get_inventory(int(self.guild_id), self.defender.id)
            if not def_inv:
                await interaction.followup.send("❌ You don't have any birds to fight with!", ephemeral=True)
                return

            view = AutoBattleView(self.bot, self.attacker, self.defender, self.guild_id, dict(self.atk_commit), def_inv, friendly=self.friendly)
            view._expiry_msg = interaction.message
            await interaction.edit_original_response(content=None, embed=view.build_embed(), view=view)
            self.stop()
        except Exception:
            log_error()
            await safe_ack(interaction)

    @discord.ui.button(label="🕶️ Ignore", style=discord.ButtonStyle.grey, row=1)
    async def ignore(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.defender.id:
            await interaction.response.send_message("❌ Only the challenged player can respond!", ephemeral=True)
            return
        await interaction.response.defer()
        await self._resolve_ignore(interaction)


class AutoBattleView(discord.ui.View):
    def __init__(self, bot, attacker, defender, guild_id, atk_commit, def_inv, friendly=False):
        super().__init__(timeout=None)
        self.bot = bot
        self.attacker = attacker
        self.defender = defender
        self.guild_id = str(guild_id)
        self.atk_commit = Counter(atk_commit)
        self.def_commit = Counter()
        self.def_inv = def_inv
        self.friendly = friendly
        self.phase = "waiting"  # waiting, battling, extension
        self._timer_task = None
        self._deadline = time.time() + 30
        self._resolving = False
        self.autodefend = None
        self._turns = None
        
        bird_values = {bird["name"].lower(): bird.get("value", 1) for bird in bot.birds}
        self.def_select = FightAddSelect(def_inv, defender.id, bird_values, f"{defender.name}: Send birds to defend!", row=0, auto_battle=True)
        self.add_item(self.def_select)
        
        self._timer_task = asyncio.create_task(self._countdown())

    def stop(self):
        if getattr(self, "_resolving", False):
            super().stop()
            return
        task = getattr(self, "_timer_task", None)
        if task and not task.done():
            task.cancel()
        super().stop()

    def build_embed(self, remaining=None):
        atk_val = commit_value(self.bot, self.atk_commit)
        def_val = commit_value(self.bot, self.def_commit)
        friendly_note = "\n✨ **Friendly battle** — nothing is lost!" if self.friendly else ""
        
        if self.phase == "waiting":
            timer_line = f"\n⏳ **{self.defender.name}** has `{max(0, int(remaining))}s` to send birds!" if remaining is not None else ""
            return discord.Embed(
                title="⚔️ Friendly Battle Started!" if self.friendly else "⚔️ Battle Started!",
                description=(
                    f"🔵 **{self.attacker.name}** attacks with: **{fmt_commit(self.atk_commit)}** (power `{int(atk_val)}`)\n"
                    f"🟢 **{self.defender.name}** must send birds to defend!\n"
                    f"{timer_line}\n\n"
                    f"💡 If no birds are sent, the round ends."
                    f"{friendly_note}"
                ),
                color=discord.Color.green() if self.friendly else discord.Color.orange()
            )
        elif self.phase == "battling":
            total = atk_val + def_val
            p_atk = atk_val / total if total > 0 else 0.5
            pct_atk = max(0.01, min(99.99, p_atk * 100))
            pct_def = max(0.01, min(99.99, 100 - pct_atk))
            atk_blocks = round(10 * pct_atk / 100)
            bar = "🔵" * atk_blocks + "🟢" * (10 - atk_blocks)
            return discord.Embed(
                title="⚔️ Battle Resolving...",
                description=(
                    f"🔵 **{self.attacker.name}**: **{fmt_commit(self.atk_commit)}** (power `{int(atk_val)}`)\n"
                    f"🟢 **{self.defender.name}**: **{fmt_commit(self.def_commit)}** (power `{int(def_val)}`)\n\n"
                    f"🎲 {bar} `{pct_atk:.2f}%` vs `{pct_def:.2f}%`\n\n"
                    f"⚔️ Calculating winner..."
                ),
                color=discord.Color.dark_red()
            )
        elif self.phase == "extension":
            timer_line = f"\n⏳ **{self.defender.name}** has `{max(0, int(remaining))}s` to send more birds!" if remaining is not None else ""
            return discord.Embed(
                title="⚔️ Attacker Won Round 1!",
                description=(
                    f"🔵 **{self.attacker.name}** defeated your birds!\n"
                    f"🟢 **{self.defender.name}** has one last chance — send more birds!\n"
                    f"{timer_line}\n\n"
                    f"💡 If no birds are sent, the battle ends."
                    f"{friendly_note}"
                ),
                color=discord.Color.red()
            )

    async def _countdown(self):
        try:
            while not self.is_finished():
                remaining = self._deadline - time.time()
                if remaining <= 0:
                    try:
                        if self.phase == "waiting":
                            await self._resolve_timeout()
                        elif self.phase == "extension":
                            await self._resolve_extension_timeout()
                    except Exception as e:
                        print(f"[fight] timeout resolve error: {e}")
                        import traceback
                        traceback.print_exc()
                        try:
                            await self._finish(discord.Embed(
                                title="⚔️ Battle Over!",
                                description="The battle timed out but couldn't be resolved automatically.",
                                color=discord.Color.greyple(),
                            ))
                        except Exception:
                            pass
                    return
                msg = getattr(self, "_expiry_msg", None) or self.message
                if msg:
                    try:
                        await msg.edit(embed=self.build_embed(remaining))
                    except Exception:
                        pass
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def _resolve_timeout(self):
        self._resolving = True
        if not self.def_commit:
            embed = discord.Embed(
                title="⚔️ Battle Over!",
                description=(
                    f"🔵 **{self.attacker.name}** attacked **{self.defender.name}**!\n"
                    f"🟢 **{self.defender.name}** sent no birds.\n"
                    f"💥 **{self.attacker.mention}** wins!"
                ),
                color=discord.Color.green()
            )
            await self._finish(embed)
        else:
            # Resolve battle with whatever birds were sent
            fake_interaction = _make_fake_interaction(self._expiry_msg or self.message)
            await self._resolve_battle(fake_interaction)

    async def _resolve_extension_timeout(self):
        self._resolving = True
        embed = discord.Embed(
            title="⚔️ Battle Over!",
            description=(
                f"🟢 **{self.defender.name}** sent no more birds.\n"
                f"💥 **{self.attacker.mention}** wins!"
            ),
            color=discord.Color.green()
        )
        await self._finish(embed)

    async def _finish(self, embed):
        msg = getattr(self, "_expiry_msg", None) or self.message
        if msg:
            try:
                await msg.edit(content=None, embed=embed, view=None)
            except Exception:
                pass
        self.stop()

    async def send_birds(self, interaction: discord.Interaction):
        if interaction.user.id != self.defender.id:
            await interaction.response.send_message("❌ Only the defender can send birds!", ephemeral=True)
            return
        
        if not self.def_select.values or self.def_select.values[0] == "No birds available":
            await interaction.response.send_message("❌ You don't have any birds to send!", ephemeral=True)
            return
        
        bird = self.def_select.selected_bird
        if not bird:
            await interaction.response.send_message("❌ Select a bird first!", ephemeral=True)
            return
        
        counts = Counter(self.def_inv)
        committed = self.def_commit.get(bird, 0)
        remaining = counts.get(bird, 0) - committed
        if remaining < 1:
            await interaction.response.send_message("❌ You already sent all of that bird!", ephemeral=True)
            return

        await interaction.response.send_modal(AutoBattleModal(self, bird, remaining))

    async def resolve_now(self, interaction: discord.Interaction):
        if interaction.user.id != self.defender.id:
            await interaction.response.send_message("❌ Only the defender can start the fight!", ephemeral=True)
            return
        if not self.def_commit:
            await interaction.response.send_message("❌ Send at least one bird first!", ephemeral=True)
            return
        try:
            await self._resolve_battle(interaction)
        except Exception:
            log_error()
            await safe_ack(interaction, "⚔️ The battle was resolved. Check your inventory!")
            try:
                await self._finish(
                    discord.Embed(
                        title="⚔️ Battle Over!",
                        description="The battle ended (resolved below).",
                        color=discord.Color.blurple(),
                    )
                )
            except Exception:
                pass

    async def _resolve_battle(self, interaction):
        self.phase = "battling"
        self._timer_task.cancel()
        
        # Handle both real and fake interactions
        is_fake = not hasattr(interaction, 'response') or not hasattr(interaction.response, 'edit_message')
        
        if not is_fake:
            await interaction.response.edit_message(embed=self.build_embed(), view=None)
        else:
            try:
                await interaction.message.edit(embed=self.build_embed(), view=None)
            except:
                pass
        
        guild_id_int = int(self.guild_id)
        winner, attacker_wins, taken = await self._resolve_battle_internal(
            interaction, self.atk_commit, self.def_commit, 
            self.attacker, self.defender, guild_id_int
        )
        
        if attacker_wins:
            if getattr(self, "autodefend", None) is not None:
                if getattr(self, "_turns", 1) <= 1:
                    self.stop()
                else:
                    self._turns -= 1
                    await self._start_extension_phase(interaction)
            elif not is_fake:
                await self._start_extension_phase(interaction)
            else:
                # For timeout resolution, defender lost - attacker wins
                self.stop()
        else:
            self.stop()

    async def _resolve_battle_internal(self, interaction, attacker_commit, defender_commit, attacker, defender, guild_id_int):
        atk_val = commit_value(self.bot, attacker_commit)
        def_val = commit_value(self.bot, defender_commit)
        total = atk_val + def_val
        p_atk = atk_val / total if total > 0 else 0.5

        attacker_wins = random.random() < p_atk
        winner = attacker if attacker_wins else defender
        loser = defender if attacker_wins else attacker
        loser_commit = dict(attacker_commit if attacker_wins else defender_commit)

        pct_atk = max(0.01, min(99.99, p_atk * 100))
        pct_def = max(0.01, min(99.99, 100 - pct_atk))
        atk_blocks = round(10 * pct_atk / 100)
        bar = "🔵" * atk_blocks + "🟢" * (10 - atk_blocks)

        powerups_cog = self.bot.get_cog("PowerupsCog")
        shield_saved = False
        shield_broke = False
        taken = []

        if not self.friendly:
            if powerups_cog and powerups_cog.has_shield(guild_id_int, loser.id):
                shield_saved = powerups_cog.consume_shield(guild_id_int, loser.id)
                shield_broke = not shield_saved
            if not shield_saved:
                expanded = []
                for bird, n in loser_commit.items():
                    expanded.extend([bird] * n)
                random.shuffle(expanded)
                half = expanded[: len(expanded) // 2] if expanded else []
                taken = transfer_birds(self.bot, guild_id_int, loser.id, winner.id, half)

        loot = ""
        if not self.friendly and powerups_cog and not shield_saved:
            drop = powerups_cog.random_drop()
            if drop:
                powerups_cog.bot.db.add_powerup(guild_id_int, winner.id, drop, 1)
                loot = f"\n🎁 **{winner.name}** looted: {powerups_cog.POWERUPS[drop]['name']}!"

        reward_payout = ""
        if not self.friendly and not shield_saved:
            reward_payout = await award_winner_rewards(
                self.bot, guild_id_int, winner, atk_val, def_val,
                getattr(getattr(self, "_expiry_msg", None), "channel", None)
            )

        result_lines = []
        if attacker_wins:
            result_lines.append(
                f"💥 **{attacker.name}** wins the battle against **{defender.name}**!"
            )
        else:
            result_lines.append(
                f"🛡️ **{defender.name}** defends and wins the battle against **{attacker.name}**!"
            )
        if self.friendly:
            result_lines.append("✨ Friendly battle — no birds were lost and no powerups were used!")
        elif shield_saved:
            result_lines.append(f"🛡️ **{loser.name}**'s Shield protected their birds!")
        else:
            if shield_broke:
                result_lines.append(f"💔 **{loser.name}**'s Shield shattered and couldn't protect them!")
            if taken:
                result_lines.append(f"💥 Took **{fmt_commit(Counter(taken))}**!")
                result_lines.append(f"🕊️ The surviving birds returned to **{loser.name}**.")
        if loot:
            result_lines.append(loot)
        if reward_payout:
            result_lines.append(reward_payout)

        embed = discord.Embed(
            title="⚔️ Battle Over!",
            description=(
                f"🎲 {bar} `{pct_atk:.2f}%` vs `{pct_def:.2f}%`\n\n"
                + "\n".join(result_lines)
            ),
            color=discord.Color.green() if winner == attacker else discord.Color.blurple()
        )
        is_fake = not hasattr(interaction, 'response') or not hasattr(interaction.response, 'edit_message')
        
        if not is_fake:
            await interaction.edit_original_response(embed=embed, view=None)
        else:
            try:
                await interaction.message.edit(embed=embed, view=None)
            except:
                pass
        
        # Log battle
        try:
            if not self.friendly:
                self.bot.db.log_battle(
                    guild_id_int, attacker.id, defender.id, winner.id,
                    dict(attacker_commit), dict(defender_commit), dict(Counter(taken))
                )
        except Exception as e:
            print(f"[battle-log] Failed to log battle: {e}")
        
        return winner, attacker_wins, taken

    async def _start_extension_phase(self, interaction):
        self.phase = "extension"
        self.def_commit = Counter()
        self._deadline = time.time() + 15
        self._timer_task = asyncio.create_task(self._countdown())
        
        new_def_inv = self.bot.db.get_inventory(int(self.guild_id), self.defender.id)
        self.def_inv = new_def_inv
        
        bird_values = {bird["name"].lower(): bird.get("value", 1) for bird in self.bot.birds}
        self.clear_items()
        self.def_select = FightAddSelect(new_def_inv, self.defender.id, bird_values, f"{self.defender.name}: Send more birds!", row=0, auto_battle=True)
        self.add_item(self.def_select)
        
        await interaction.followup.edit_message(
            interaction.message.id, 
            embed=self.build_embed(), 
            view=self
        )

        if getattr(self, "autodefend", None):
            await self.auto_defend_round(interaction)

    async def auto_defend_round(self, interaction):
        counts = Counter(self.bot.db.get_inventory(int(self.guild_id), self.defender.id))
        commit = Counter()
        for bird, n in (self.autodefend or {}).items():
            avail = counts.get(bird, 0)
            if n <= 0 or avail <= 0:
                continue
            commit[bird] = min(n, avail)
        self.def_commit = commit
        if not commit:
            await self._finish(discord.Embed(
                title="🕶️ Auto-Defense: Nothing to Fight With!",
                description=(f"**{self.attacker.name}** attacked **{self.defender.name}** "
                             f"but the auto-defense had no birds to commit."),
                color=discord.Color.greyple(),
            ))
            return
        await self._resolve_battle(interaction)


class AutoBattleModal(discord.ui.Modal):
    def __init__(self, view, bird, max_count):
        super().__init__(title=f"Send {bird} to Battle")
        self.view = view
        self.bird = bird
        self.max_count = max_count
        self.count_input = discord.ui.TextInput(
            label=f"How many {bird}? (Max: {max_count})",
            placeholder="Enter a number...",
            min_length=1,
            max_length=3,
            default="1"
        )
        self.add_item(self.count_input)

    async def on_submit(self, interaction: discord.Interaction):
        counts = Counter(self.view.def_inv)
        remaining = counts.get(self.bird, 0) - self.view.def_commit.get(self.bird, 0)
        try:
            val = int(self.count_input.value)
            if val < 1 or val > remaining:
                raise ValueError()
        except ValueError:
            await interaction.response.send_message(f"❌ Enter a valid number between 1 and {remaining}!", ephemeral=True)
            return

        self.view.def_commit[self.bird] = self.view.def_commit.get(self.bird, 0) + val
        
        # Add "Fight Now!" button if not already present
        if not hasattr(self.view, 'fight_now_btn') or self.view.fight_now_btn not in self.view.children:
            self.view.fight_now_btn = discord.ui.Button(label="⚔️ Fight Now!", style=discord.ButtonStyle.red, row=2)
            self.view.fight_now_btn.callback = self.view.resolve_now
            self.view.add_item(self.view.fight_now_btn)
        
        await interaction.response.edit_message(embed=self.view.build_embed(), view=self.view)


class FightLiveView(discord.ui.View):
    def __init__(self, bot, attacker, defender, guild_id, atk_commit):
        super().__init__(timeout=120)
        self.bot = bot
        self.attacker = attacker
        self.defender = defender
        self.guild_id = str(guild_id)
        self.confirmed_users = set()
        self.started_at = time.time()

        att_inv = bot.db.get_inventory(int(guild_id), attacker.id)
        def_inv = bot.db.get_inventory(int(guild_id), defender.id)

        self.max_pool = {attacker.id: Counter(att_inv), defender.id: Counter(def_inv)}
        self.commit = {attacker.id: Counter(atk_commit), defender.id: Counter()}

        bird_values = {bird["name"].lower(): bird.get("value", 1) for bird in bot.birds}
        self.att_select = FightAddSelect(att_inv, attacker.id, bird_values, f"{attacker.name}: Send more birds", row=0)
        self.def_select = FightAddSelect(def_inv, defender.id, bird_values, f"{defender.name}: Send birds to battle", row=1)
        self.add_item(self.att_select)
        self.add_item(self.def_select)

    def build_embed(self):
        atk_commit = self.commit[self.attacker.id]
        def_commit = self.commit[self.defender.id]
        atk_val = commit_value(self.bot, atk_commit)
        def_val = commit_value(self.bot, def_commit)

        total = atk_val + def_val
        p_atk = atk_val / total if total > 0 else 0.5
        pct_atk = max(0.01, min(99.99, p_atk * 100))
        pct_def = max(0.01, min(99.99, 100 - pct_atk))

        atk_blocks = round(10 * pct_atk / 100)
        def_blocks = 10 - atk_blocks
        bar = "🔵" * atk_blocks + "🟢" * def_blocks

        atk_check = "✅" if self.attacker.id in self.confirmed_users else "⏳"
        def_check = "✅" if self.defender.id in self.confirmed_users else "⏳"

        embed = discord.Embed(
            title="⚔️ Live Battle",
            description=(
                f"🔵 **{self.attacker.name}**: **{fmt_commit(atk_commit)}** (power `{int(atk_val)}`) *({atk_check})*\n"
                f"🟢 **{self.defender.name}**: **{fmt_commit(def_commit)}** (power `{int(def_val)}`) *({def_check})*\n\n"
                f"🎲 {bar} `{pct_atk:.2f}%` vs `{pct_def:.2f}%`\n\n"
                f"Send more birds from the menus, then **both players press ⚔️ Fight!** to battle.\n"
                f"Or press 🏃 to flee and cut your losses."
            ),
            color=discord.Color.dark_red()
        )
        return embed

    @discord.ui.button(label="⚔️ Fight! (Challenger)", style=discord.ButtonStyle.green, row=2)
    async def confirm_attacker(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.attacker:
            await interaction.response.send_message("❌ Only the challenger can confirm!", ephemeral=True)
            return
        self.confirmed_users.add(self.attacker.id)
        await self._after_confirm(interaction)

    @discord.ui.button(label="⚔️ Fight! (Defender)", style=discord.ButtonStyle.green, row=2)
    async def confirm_defender(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.defender:
            await interaction.response.send_message("❌ Only the defender can confirm!", ephemeral=True)
            return
        self.confirmed_users.add(self.defender.id)
        await self._after_confirm(interaction)

    async def _after_confirm(self, interaction: discord.Interaction):
        guild_id_int = int(self.guild_id)

        if not self.commit[self.attacker.id] or not self.commit[self.defender.id]:
            await interaction.response.send_message("❌ Both players must send at least one bird to battle!", ephemeral=True)
            return

        if len(self.confirmed_users) < 2:
            await interaction.response.edit_message(content=None, embed=self.build_embed(), view=self)
            return

        await self._resolve(interaction)

    async def _resolve_battle(self, interaction, attacker_commit, defender_commit, attacker, defender, guild_id_int):
        atk_val = commit_value(self.bot, attacker_commit)
        def_val = commit_value(self.bot, defender_commit)
        total = atk_val + def_val
        p_atk = atk_val / total if total > 0 else 0.5

        attacker_wins = random.random() < p_atk
        winner = attacker if attacker_wins else defender
        loser = defender if attacker_wins else attacker
        loser_commit = dict(attacker_commit if attacker_wins else defender_commit)

        pct_atk = max(0.01, min(99.99, p_atk * 100))
        pct_def = max(0.01, min(99.99, 100 - pct_atk))
        atk_blocks = round(10 * pct_atk / 100)
        bar = "🔵" * atk_blocks + "🟢" * (10 - atk_blocks)

        powerups_cog = self.bot.get_cog("PowerupsCog")
        shield_saved = False
        shield_broke = False
        taken = []

        if powerups_cog and powerups_cog.has_shield(guild_id_int, loser.id):
            shield_saved = powerups_cog.consume_shield(guild_id_int, loser.id)
            shield_broke = not shield_saved
        if not shield_saved:
            expanded = []
            for bird, n in loser_commit.items():
                expanded.extend([bird] * n)
            random.shuffle(expanded)
            half = expanded[: len(expanded) // 2] if expanded else []
            taken = transfer_birds(self.bot, guild_id_int, loser.id, winner.id, half)

        loot = ""
        if powerups_cog and not shield_saved:
            drop = powerups_cog.random_drop()
            if drop:
                powerups_cog.bot.db.add_powerup(guild_id_int, winner.id, drop, 1)
                loot = f"\n🎁 **{winner.name}** looted: {powerups_cog.POWERUPS[drop]['name']}!"

        reward_payout = ""
        if not shield_saved:
            reward_payout = await award_winner_rewards(
                self.bot, guild_id_int, winner, atk_val, def_val,
                getattr(getattr(self, "_expiry_msg", None), "channel", None)
            )

        result_lines = []
        if shield_saved:
            result_lines.append(f"🛡️ **{loser.name}**'s Shield protected their birds!")
        else:
            if shield_broke:
                result_lines.append(f"💔 **{loser.name}**'s Shield shattered and couldn't protect them!")
            if taken:
                result_lines.append(f"💥 **{winner.mention}** won the battle and took **{fmt_commit(Counter(taken))}**!")
                result_lines.append(f"🕊️ The surviving birds returned to **{loser.name}**.")
        if loot:
            result_lines.append(loot)
        if reward_payout:
            result_lines.append(reward_payout)

        embed = discord.Embed(
            title="⚔️ Battle Over!",
            description=(
                f"🔵 **{attacker.name}** (power `{int(atk_val)}`)  vs  🟢 **{defender.name}** (power `{int(def_val)}`)\n"
                f"🎲 {bar} `{pct_atk:.2f}%` vs `{pct_def:.2f}%`\n\n"
                + "\n".join(result_lines)
            ),
            color=discord.Color.green() if winner == attacker else discord.Color.blurple()
        )
        await interaction.response.edit_message(content=None, embed=embed, view=None)
        self.stop()
        return winner, attacker_wins, taken

    @discord.ui.button(label="🏃 Flee", style=discord.ButtonStyle.red, row=3)
    async def flee(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in [self.attacker, self.defender]:
            await interaction.response.send_message("❌ You cannot flee this battle!", ephemeral=True)
            return

        guild_id_int = int(self.guild_id)
        elapsed = time.time() - self.started_at
        p_survive = survival_rate(elapsed)

        results = {}
        for player in [self.attacker, self.defender]:
            commit = self.commit[player.id]
            expanded = []
            for bird, n in commit.items():
                expanded.extend([bird] * n)
            random.shuffle(expanded)

            survived = []
            lost = []
            for bird in expanded:
                if random.random() < p_survive:
                    survived.append(bird)
                else:
                    lost.append(bird)

            lost = deduct_birds(self.bot, guild_id_int, player.id, lost)
            results[player.id] = (survived, lost)

        seconds = max(1, int(elapsed))
        lines = []
        for player in [self.attacker, self.defender]:
            survived, lost = results[player.id]
            kept_line = f"🕊️ **{player.name}** kept **{fmt_commit(Counter(survived))}**" if survived else f"🕊️ **{player.name}** kept nothing"
            lost_line = f" — lost **{fmt_commit(Counter(lost))}**" if lost else ""
            lines.append(kept_line + lost_line)

        embed = discord.Embed(
            title="🏃 Battle Ended in Retreat!",
            description=(
                f"⏱️ The battle lasted `{seconds}s` — survival chance was `{p_survive * 100:.0f}%`.\n\n"
                + "\n".join(lines)
                + "\n\n🕊️ Survivors returned home; the fallen were claimed by the battle."
            ),
            color=discord.Color.greyple()
        )
        await interaction.response.edit_message(content=None, embed=embed, view=None)
        self.stop()

    async def on_timeout(self):
        msg = getattr(self, "_expiry_msg", None) or self.message
        if msg:
            try:
                await msg.edit(content="⏰ The battle came to a stalemate and ended.", embed=None, view=None)
            except Exception:
                pass


class FightCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="fight", description="Challenge another user to a bird battle!")
    @discord.app_commands.describe(member="The user you want to battle")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def fight(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer()
        try:
            if not interaction.guild:
                await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
                return

            if member == interaction.user:
                await interaction.followup.send("❌ You cannot battle yourself!", ephemeral=True)
                return

            # Special case: fight BirdBot
            if member.id == self.bot.user.id:
                return await self._fight_birdbot(interaction)
            
            if member.bot:
                await interaction.followup.send("❌ You cannot battle other bots!", ephemeral=True)
                return

            if not is_active(self.bot, member):
                # Use real-time cache for display
                real_status = self.bot.presence_cache.get(member.id, member.status)
                status_txt = STATUS_TEXT.get(real_status, real_status)
                await interaction.followup.send(
                    f"❌ **{member.display_name}** is **{status_txt}** and not active right now! "
                    f"You can only battle active users.",
                    ephemeral=True
                )
                return

            guild_id = interaction.guild.id
            user_birds = self.bot.db.get_inventory(guild_id, interaction.user.id)
            if not user_birds:
                await interaction.followup.send("❌ You don't have any birds to battle with!", ephemeral=True)
                return

            try:
                view = FightSetupView(self.bot, interaction.user, member, str(guild_id))
            except Exception as e:
                print(f"[fight] FightSetupView init error: {e}")
                import traceback
                traceback.print_exc()
                await interaction.followup.send(f"❌ Setup error: {e}", ephemeral=True)
                return
            
            try:
                msg = await interaction.followup.send(
                    content=f"⚔️ **{interaction.user.mention}** is preparing a battle against **{member.mention}**!",
                    embed=view.build_embed(),
                    view=view
                )
                view._expiry_msg = msg
            except Exception as e:
                print(f"[fight] followup send error: {e}")
                import traceback
                traceback.print_exc()
                await interaction.followup.send(f"❌ Send error: {e}", ephemeral=True)
                return
        except Exception as e:
            print(f"Error in fight command: {e}")
            await interaction.followup.send("❌ An error occurred while executing this command.", ephemeral=True)

    @discord.app_commands.command(name="friendlybattle", description="Challenge someone to a friendly battle (no birds lost, no powerups)")
    @discord.app_commands.describe(member="The user you want to battle")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def friendlybattle(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer()
        try:
            if not interaction.guild:
                await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
                return

            if member == interaction.user:
                await interaction.followup.send("❌ You cannot battle yourself!", ephemeral=True)
                return

            if member.id == self.bot.user.id:
                return await self._fight_birdbot(interaction, friendly=True)

            if member.bot:
                await interaction.followup.send("❌ You cannot battle other bots!", ephemeral=True)
                return

            if not is_active(self.bot, member):
                real_status = self.bot.presence_cache.get(member.id, member.status)
                status_txt = STATUS_TEXT.get(real_status, real_status)
                await interaction.followup.send(
                    f"❌ **{member.display_name}** is **{status_txt}** and not active right now! "
                    f"You can only battle active users.",
                    ephemeral=True
                )
                return

            guild_id = interaction.guild.id
            user_birds = self.bot.db.get_inventory(guild_id, interaction.user.id)
            if not user_birds:
                await interaction.followup.send("❌ You don't have any birds to battle with!", ephemeral=True)
                return

            try:
                view = FightSetupView(self.bot, interaction.user, member, str(guild_id), friendly=True)
            except Exception as e:
                print(f"[fight] FightSetupView init error: {e}")
                import traceback
                traceback.print_exc()
                await interaction.followup.send(f"❌ Setup error: {e}", ephemeral=True)
                return

            try:
                msg = await interaction.followup.send(
                    content=f"✨ **{interaction.user.mention}** challenges **{member.mention}** to a friendly battle!",
                    embed=view.build_embed(),
                    view=view
                )
                view._expiry_msg = msg
            except Exception as e:
                print(f"[fight] followup send error: {e}")
                import traceback
                traceback.print_exc()
                await interaction.followup.send(f"❌ Send error: {e}", ephemeral=True)
                return
        except Exception as e:
            print(f"Error in friendlybattle command: {e}")
            await interaction.followup.send("❌ An error occurred while executing this command.", ephemeral=True)

    @discord.app_commands.command(name="battlelog", description="View your recent battle history")
    @discord.app_commands.describe(member="User to check (defaults to yourself)")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def battlelog(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
            return
        
        target = member or interaction.user
        guild_id = interaction.guild.id
        
        battles = self.bot.db.get_battle_log(guild_id, target.id, limit=10)
        
        if not battles:
            await interaction.followup.send(f"📜 **{target.display_name}** has no battle history yet.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"⚔️ Battle Log — {target.display_name}",
            color=discord.Color.dark_red()
        )
        
        for i, row in enumerate(battles, 1):
            attacker_id, defender_id, winner_id, atk_birds_json, def_birds_json, stolen_birds_json, created_at = row
            import json
            atk_birds = json.loads(atk_birds_json) if atk_birds_json else {}
            def_birds = json.loads(def_birds_json) if def_birds_json else {}
            stolen_birds = json.loads(stolen_birds_json) if stolen_birds_json else {}
            
            is_attacker = attacker_id == target.id
            opponent_id = defender_id if is_attacker else attacker_id
            won = winner_id == target.id
            
            try:
                opponent = interaction.guild.get_member(opponent_id)
                opponent_name = opponent.display_name if opponent else f"User {opponent_id}"
            except:
                opponent_name = f"User {opponent_id}"
            
            role = "Attacker" if is_attacker else "Defender"
            result = "🟢 **WON**" if won else "🔴 **LOST**"
            birds_str = fmt_commit(atk_birds) if is_attacker else fmt_commit(def_birds)
            stolen_str = fmt_commit(stolen_birds) if stolen_birds else "None"
            
            embed.add_field(
                name=f"{i}. vs {opponent_name} ({role}) — {result}",
                value=f"Your birds: {birds_str}\nStolen: {stolen_str}\n{created_at.strftime('%Y-%m-%d %H:%M')}",
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.app_commands.command(name="winrate", description="View your battle win rate")
    @discord.app_commands.describe(member="User to check (defaults to yourself)")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def winrate(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
            return
        
        target = member or interaction.user
        guild_id = interaction.guild.id
        
        stats = self.bot.db.get_winrate(guild_id, target.id)
        
        if stats["total"] == 0:
            await interaction.followup.send(f"📊 **{target.display_name}** has no battles recorded yet.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"📊 Win Rate — {target.display_name}",
            color=discord.Color.gold()
        )
        embed.add_field(name="Total Battles", value=str(stats["total"]), inline=True)
        embed.add_field(name="Wins", value=str(stats["wins"]), inline=True)
        embed.add_field(name="Losses", value=str(stats["total"] - stats["wins"]), inline=True)
        embed.add_field(name="Win Rate", value=f"{stats['rate']:.1f}%", inline=True)
        
        # Rank emoji based on winrate
        if stats["rate"] >= 70:
            rank = "🏆 Champion"
        elif stats["rate"] >= 55:
            rank = "🥇 Veteran"
        elif stats["rate"] >= 40:
            rank = "⚔️ Fighter"
        elif stats["rate"] >= 25:
            rank = "🛡️ Novice"
        else:
            rank = "🐣 Rookie"
        embed.add_field(name="Rank", value=rank, inline=True)
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    autodefend_group = discord.app_commands.Group(
        name="autodefend", description="Auto-defend when someone attacks you"
    )

    @autodefend_group.command(name="set", description="Set which birds to auto-defend with (e.g. Bird 3 Good Bird 2)")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def autodefend_set(self, interaction: discord.Interaction, birds: str):
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
            return
        guild_id = interaction.guild.id
        inv = Counter(self.bot.db.get_inventory(guild_id, interaction.user.id))
        parsed = parse_bird_counts(self.bot, birds, inv)
        if parsed is None:
            await interaction.followup.send(
                "❌ Couldn't parse that. Format: `/autodefend set <bird> <count> <bird> <count>...`\n"
                "Example: `/autodefend set Bird 3 Good Bird 2`",
                ephemeral=True
            )
            return
        if parsed == "insufficient":
            await interaction.followup.send(
                f"❌ You don't have enough of those birds! Your inventory: **{fmt_commit(inv)}**",
                ephemeral=True
            )
            return
        self.bot.db.set_autodefend(guild_id, interaction.user.id, parsed)
        await interaction.followup.send(
            f"🛡️ **Auto-Defense armed!** You'll automatically fight back with: **{fmt_commit(Counter(parsed))}**",
            ephemeral=True
        )

    @autodefend_group.command(name="remove", description="Remove birds from your auto-defense setup")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def autodefend_remove(self, interaction: discord.Interaction, birds: str):
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
            return
        guild_id = interaction.guild.id
        current = dict(self.bot.db.get_autodefend(guild_id, interaction.user.id))
        if not current:
            await interaction.followup.send("🛡️ You don't have any Auto-Defense set up.", ephemeral=True)
            return
        parsed = parse_bird_counts(self.bot, birds, current)
        if parsed is None:
            await interaction.followup.send(
                "❌ Couldn't parse that. Format: `/autodefend remove <bird> <count> <bird> <count>...`",
                ephemeral=True
            )
            return
        if parsed == "insufficient":
            await interaction.followup.send(
                f"❌ You're not auto-defending with that many. Current: **{fmt_commit(Counter(current))}**",
                ephemeral=True
            )
            return
        for bird, n in parsed.items():
            current[bird] = current.get(bird, 0) - n
            if current[bird] <= 0:
                current.pop(bird, None)
        self.bot.db.set_autodefend(guild_id, interaction.user.id, current)
        if not current:
            await interaction.followup.send("🛡️ **Auto-Defense turned off.**", ephemeral=True)
        else:
            await interaction.followup.send(
                f"🛡️ Removed. Now auto-defending with: **{fmt_commit(Counter(current))}**",
                ephemeral=True
            )

    @autodefend_group.command(name="check", description="View a user's auto-defense configuration")
    @discord.app_commands.allowed_installs(guilds=True, users=False)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def autodefend_check(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server!", ephemeral=True)
            return
        guild_id = interaction.guild.id
        target = member or interaction.user
        current = self.bot.db.get_autodefend(guild_id, target.id)
        if not current:
            await interaction.followup.send(
                f"🛡️ **{target.display_name}** has **no Auto-Defense** set up. "
                f"Use `/autodefend set <bird> <count>...`!",
                ephemeral=True
            )
            return
        inv = Counter(self.bot.db.get_inventory(guild_id, target.id))
        ready = all(inv.get(b, 0) >= n for b, n in current.items())
        status = "✅ armed" if ready else "⚠️ not armed (missing birds in inventory)"
        await interaction.followup.send(
            f"🛡️ **{target.display_name}**'s Auto-Defense: **{fmt_commit(Counter(current))}** — {status}",
            ephemeral=True
        )

    async def _fight_birdbot(self, interaction: discord.Interaction, friendly=False):
        """Normal fight flow — BirdBot instantly accepts and guards with 999 Radioactive Birds"""
        guild_id = interaction.guild.id
        user_birds = self.bot.db.get_inventory(guild_id, interaction.user.id)
        if not user_birds:
            await interaction.followup.send("❌ You don't have any birds to battle with!", ephemeral=True)
            return

        try:
            view = FightSetupView(self.bot, interaction.user, self.bot.user, str(guild_id), is_boss=True, friendly=friendly)
            msg = await interaction.followup.send(
                content=f"⚔️ **{interaction.user.mention}** is preparing a battle against **{self.bot.user.mention}**!",
                embed=view.build_embed(),
                view=view
            )
            view._expiry_msg = msg
            games_cog = self.bot.get_cog("GamesCog")
            if games_cog:
                await games_cog.unlock_achievement(interaction.user.id, "fight_birdbot", interaction.channel, guild_id=guild_id)
        except Exception as e:
            print(f"[fight] fight_birdbot setup error: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"❌ Setup error: {e}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(FightCog(bot))


class BirdBotAutoBattleView(discord.ui.View):
    BOSS_BIRD = "Radioactive Bird"

    def __init__(self, bot, attacker, defender, guild_id, atk_commit, friendly=False):
        super().__init__(timeout=None)
        self.bot = bot
        self.attacker = attacker
        self.defender = defender
        self.guild_id = str(guild_id)
        self.atk_commit = Counter(atk_commit)
        self.def_commit = Counter({BirdBotAutoBattleView.BOSS_BIRD: 999})
        self.friendly = friendly
        self._resolving = False
        self._deadline = time.time() + 60
        self._timer_task = asyncio.create_task(self._countdown())

    def stop(self):
        task = getattr(self, "_timer_task", None)
        if task and not task.done():
            task.cancel()
        super().stop()

    def build_embed(self, remaining=None):
        atk_val = commit_value(self.bot, self.atk_commit)
        def_val = commit_value(self.bot, self.def_commit)
        total = atk_val + def_val
        p_atk = atk_val / total if total > 0 else 0.5
        pct_atk = max(0.01, min(99.99, p_atk * 100))
        pct_def = max(0.01, min(99.99, 100 - pct_atk))
        blocks = round(10 * pct_atk / 100)
        bar = "🔵" * blocks + "🟢" * (10 - blocks)
        timer_line = ""
        if remaining is not None:
            timer_line = (
                f"\n⏳ Battle auto-resolves in `{max(0, int(remaining))}s` "
                f"if **⚔️ Fight!** isn't pressed!"
            )
        return discord.Embed(
            title="⚔️ Friendly Battle Started!" if self.friendly else "⚔️ Battle Started!",
            description=(
                f"🔵 **{self.attacker.name}**: **{fmt_commit(self.atk_commit)}** (power `{int(atk_val)}`)\n"
                f"🟢 **{self.defender.name}**: **{fmt_commit(self.def_commit)}** (power `{int(def_val)}`)\n\n"
                f"🎲 {bar} `{pct_atk:.2f}%` vs `{pct_def:.2f}%`\n\n"
                f"**{self.defender.name}** instantly readies **999x Radioactive Bird**!\n"
                f"Press **⚔️ Fight!** to start the battle.{timer_line}"
            ),
            color=discord.Color.green() if self.friendly else discord.Color.dark_red()
        )

    async def _countdown(self):
        try:
            while not self.is_finished():
                remaining = self._deadline - time.time()
                if remaining <= 0:
                    if self._resolving:
                        return
                    self._resolving = True
                    try:
                        await resolve_battle(
                            self.bot, self, self.guild_id, self.attacker, self.defender,
                            self.atk_commit, self.def_commit
                        )
                    except Exception as e:
                        print(f"[birdbot] auto-resolve error: {e}")
                    self.stop()
                    return
                msg = getattr(self, "_expiry_msg", None) or self.message
                if msg:
                    try:
                        await msg.edit(embed=self.build_embed(remaining))
                    except Exception:
                        pass
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    @discord.ui.button(label="⚔️ Fight!", style=discord.ButtonStyle.green, row=2)
    async def fight(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.attacker.id:
            await interaction.response.send_message("❌ Only the challenger can start the battle!", ephemeral=True)
            return

        atk_val = commit_value(self.bot, self.atk_commit)
        def_val = commit_value(self.bot, self.def_commit)
        total = atk_val + def_val
        p_atk = atk_val / total if total > 0 else 0.5
        pct_atk = max(0.01, min(99.99, p_atk * 100))
        blocks = round(10 * pct_atk / 100)
        bar = "🔵" * blocks + "🟢" * (10 - blocks)

        battling = discord.Embed(
            title="⚔️ Battle Resolving...",
            description=f"🎲 {bar} `{pct_atk:.2f}%` vs `{max(0.01, min(99.99, 100 - pct_atk)):.2f}%`\n\n⚔️ Calculating winner...",
            color=discord.Color.dark_red()
        )
        await interaction.response.edit_message(content=None, embed=battling, view=None)
        await asyncio.sleep(1.5)

        if self._resolving:
            return
        self._resolving = True

        try:
            await resolve_battle(
                self.bot, self, self.guild_id, self.attacker, self.defender,
                self.atk_commit, self.def_commit
            )
        except Exception as e:
            print(f"[birdbot] resolve error: {e}")
            import traceback
            traceback.print_exc()
            try:
                await interaction.edit_original_response(
                    content="⚔️ The battle was resolved. Check the battle log!",
                    embed=None, view=None
                )
            except Exception:
                pass
        self.stop()


async def resolve_battle(bot, view, guild_id, attacker, defender, attacker_commit, defender_commit):
    guild_id_int = int(guild_id)
    friendly = getattr(view, "friendly", False)
    atk_val = commit_value(bot, attacker_commit)
    def_val = commit_value(bot, defender_commit)
    total = atk_val + def_val
    p_atk = atk_val / total if total > 0 else 0.5

    attacker_wins = random.random() < p_atk
    winner = attacker if attacker_wins else defender
    loser = defender if attacker_wins else attacker
    loser_commit = dict(attacker_commit if attacker_wins else defender_commit)

    pct_atk = max(0.01, min(99.99, p_atk * 100))
    pct_def = max(0.01, min(99.99, 100 - pct_atk))
    atk_blocks = round(10 * pct_atk / 100)
    bar = "🔵" * atk_blocks + "🟢" * (10 - atk_blocks)

    powerups_cog = bot.get_cog("PowerupsCog")
    shield_saved = False
    shield_broke = False
    taken = []

    if not friendly:
        if powerups_cog and powerups_cog.has_shield(guild_id_int, loser.id):
            shield_saved = powerups_cog.consume_shield(guild_id_int, loser.id)
            shield_broke = not shield_saved
        if not shield_saved:
            if loser.id == bot.user.id:
                taken = []
            else:
                expanded = []
                for bird, n in loser_commit.items():
                    expanded.extend([bird] * n)
                random.shuffle(expanded)
                half = expanded[: len(expanded) // 2] if expanded else []
                taken = transfer_birds(bot, guild_id_int, loser.id, winner.id, half)

    loot = ""
    if not friendly and powerups_cog and not shield_saved and winner.id != bot.user.id:
        drop = powerups_cog.random_drop()
        if drop:
            powerups_cog.bot.db.add_powerup(guild_id_int, winner.id, drop, 1)
            loot = f"\n🎁 **{winner.name}** looted: {powerups_cog.POWERUPS[drop]['name']}!"

    reward_payout = ""
    if not friendly and not shield_saved:
        reward_payout = await award_winner_rewards(
            bot, guild_id_int, winner, atk_val, def_val,
            getattr(getattr(view, "_expiry_msg", None), "channel", None)
        )

    result_lines = []
    if attacker_wins:
        result_lines.append(
            f"💥 **{attacker.name}** wins the battle against **{defender.name}**!"
        )
    else:
        result_lines.append(
            f"🛡️ **{defender.name}** defends and wins the battle against **{attacker.name}**!"
        )
    if friendly:
        result_lines.append("✨ Friendly battle — no birds were lost and no powerups were used!")
    elif shield_saved:
        result_lines.append(f"🛡️ **{loser.name}**'s Shield protected their birds!")
    elif shield_broke:
        result_lines.append(f"💔 **{loser.name}**'s Shield shattered and couldn't protect them!")
    if not shield_saved and taken:
        result_lines.append(f"💥 Took **{fmt_commit(Counter(taken))}**!")
        result_lines.append(f"🕊️ The surviving birds returned to **{loser.name}**.")
    if loot:
        result_lines.append(loot)
    if reward_payout:
        result_lines.append(reward_payout)

    msg = getattr(view, "_expiry_msg", None) or view.message

    if not friendly and attacker_wins and defender.id == bot.user.id:
        try:
            games_cog = bot.get_cog("GamesCog")
            if games_cog:
                await games_cog.unlock_achievement(
                    attacker.id, "what?????", getattr(msg, "channel", None), guild_id=guild_id_int
                )
        except Exception as e:
            print(f"[birdbot] achievement error: {e}")
        try:
            guild = getattr(msg, "guild", None)
            if guild:
                role = discord.utils.get(guild.roles, name="What?????")
                if role is None:
                    role = await guild.create_role(name="What?????", color=discord.Color.gold())
                member = guild.get_member(attacker.id)
                if member and role not in member.roles:
                    await member.add_roles(role)
                result_lines.append(f"🏅 **{attacker.name}** earned the **What?????** role!")
        except Exception as e:
            print(f"[birdbot] role error: {e}")

    embed = discord.Embed(
        title="⚔️ Battle Over!",
        description=(
            f"🎲 {bar} `{pct_atk:.2f}%` vs `{pct_def:.2f}%`\n\n"
            + "\n".join(result_lines)
        ),
        color=discord.Color.green() if winner == attacker else discord.Color.blurple()
    )

    try:
        if not friendly:
            bot.db.log_battle(guild_id_int, attacker.id, defender.id, winner.id,
                dict(attacker_commit), dict(defender_commit), dict(Counter(taken)))
    except Exception as e:
        print(f"[battle-log] Failed to log battle: {e}")

    if msg:
        try:
            await msg.edit(content=None, embed=embed)
        except Exception:
            pass