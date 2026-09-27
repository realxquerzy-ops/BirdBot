import json
import time
from urllib.parse import urlparse

import psycopg2
from psycopg2.pool import ThreadedConnectionPool


class Database:
    def __init__(self, database_url):
        host = urlparse(database_url).hostname or ""
        self._is_neon_pooler = "-pooler." in host
        kwargs = dict(
            connect_timeout=5,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=3,
            application_name="birdbot",
        )
        # Neon poolers reject the startup `options` parameter - only send it on
        # direct (unpooled) connections. sslmode etc. are preserved from the URL
        # by passing the full DSN to psycopg2.
        if not self._is_neon_pooler:
            kwargs["options"] = "-c statement_timeout=5000 -c lock_timeout=3000"
        self._pool = ThreadedConnectionPool(2, 6, database_url, **kwargs)

    def close(self):
        self._pool.closeall()

    def _get_conn(self):
        return self._pool.getconn()

    def _put_conn(self, conn):
        self._pool.putconn(conn)

    def fetchone(self, sql, params=None):
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
            conn.commit()
            return row
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def fetchall(self, sql, params=None):
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
            conn.commit()
            return rows
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def execute(self, sql, params=None):
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    @staticmethod
    def _loads_json(value):
        return json.loads(value) if value else []

    def get_inventory(self, guild_id, user_id):
        row = self.fetchone(
            "SELECT birds FROM inventories WHERE guild_id = %s AND user_id = %s",
            (guild_id, user_id),
        )
        return self._loads_json(row[0]) if row else []

    def save_inventory(self, guild_id, user_id, birds):
        self.execute(
            """
            INSERT INTO inventories (guild_id, user_id, birds) VALUES (%s, %s, %s)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET birds = EXCLUDED.birds
            """,
            (guild_id, user_id, json.dumps(birds)),
        )

    def get_achievements(self, guild_id, user_id):
        row = self.fetchone(
            "SELECT achievements FROM achievements WHERE guild_id = %s AND user_id = %s",
            (guild_id, user_id),
        )
        return self._loads_json(row[0]) if row else []

    def save_achievements(self, guild_id, user_id, achievements):
        self.execute(
            """
            INSERT INTO achievements (guild_id, user_id, achievements) VALUES (%s, %s, %s)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET achievements = EXCLUDED.achievements
            """,
            (guild_id, user_id, json.dumps(achievements)),
        )

    def get_all_birds(self):
        rows = self.fetchall("SELECT name, sticker_id, weight, value FROM birds_data ORDER BY weight DESC")
        return [
            {"name": r[0], "sticker_id": r[1], "weight": r[2], "value": r[3]}
            for r in rows
        ]

    def get_server_settings(self):
        rows = self.fetchall("SELECT guild_id, channel_id FROM guild_settings")
        return {str(row[0]): row[1] for row in rows}

    def get_server_channel(self, guild_id):
        row = self.fetchone(
            "SELECT channel_id FROM guild_settings WHERE guild_id = %s", (guild_id,)
        )
        return row[0] if row else None

    def set_server_channel(self, guild_id, channel_id):
        self.execute(
            """
            INSERT INTO guild_settings (guild_id, channel_id) VALUES (%s, %s)
            ON CONFLICT (guild_id) DO UPDATE SET channel_id = EXCLUDED.channel_id
            """,
            (guild_id, channel_id),
        )

    def get_pip_claim(self, guild_id, user_id):
        row = self.fetchone(
            "SELECT claimed FROM pip_claims WHERE guild_id = %s AND user_id = %s",
            (guild_id, user_id),
        )
        return bool(row[0]) if row else False

    def set_pip_claim(self, guild_id, user_id):
        self.execute(
            """
            INSERT INTO pip_claims (guild_id, user_id, claimed) VALUES (%s, %s, TRUE)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET claimed = EXCLUDED.claimed
            """,
            (guild_id, user_id),
        )

    def get_birdpass(self, guild_id, user_id):
        row = self.fetchone(
            "SELECT xp, claimed_level, week_xp, week_start FROM birdpass WHERE guild_id = %s AND user_id = %s",
            (guild_id, user_id),
        )
        if row:
            week_xp = float(row[2]) if row[2] is not None else 0.0
            return float(row[0]), int(row[1]), week_xp, row[3]
        return 0.0, 1, 0.0, None

    def save_birdpass(self, guild_id, user_id, xp, claimed_level, week_xp=None, week_start=None):
        self.execute(
            """
            INSERT INTO birdpass (guild_id, user_id, xp, claimed_level, week_xp, week_start)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET
                xp = EXCLUDED.xp,
                claimed_level = EXCLUDED.claimed_level,
                week_xp = EXCLUDED.week_xp,
                week_start = EXCLUDED.week_start
            """,
            (guild_id, user_id, xp, claimed_level, week_xp, week_start),
        )

    def get_weekly_top(self, guild_id, week_start, limit=3):
        rows = self.fetchall(
            """
            SELECT user_id, week_xp FROM birdpass
            WHERE guild_id = %s AND week_start = %s AND week_xp > 0
            ORDER BY week_xp DESC, user_id ASC
            LIMIT %s
            """,
            (guild_id, week_start, int(limit)),
        )
        return [(int(r[0]), float(r[1])) for r in rows]

    def get_last_gamble(self, guild_id, user_id):
        row = self.fetchone(
            "SELECT last_gamble FROM gamble_cooldowns WHERE guild_id = %s AND user_id = %s",
            (guild_id, user_id),
        )
        return int(row[0]) if row and row[0] is not None else 0

    def set_last_gamble(self, guild_id, user_id, ts):
        self.execute(
            """
            INSERT INTO gamble_cooldowns (guild_id, user_id, last_gamble) VALUES (%s, %s, %s)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET last_gamble = EXCLUDED.last_gamble
            """,
            (guild_id, user_id, int(ts)),
        )

    def get_last_daily_claim(self, guild_id, user_id):
        row = self.fetchone(
            "SELECT last_claim FROM daily_claims WHERE guild_id = %s AND user_id = %s",
            (guild_id, user_id),
        )
        if row and row[0] is not None:
            return row[0].isoformat()
        return None

    def set_daily_claim(self, guild_id, user_id, date_iso):
        self.execute(
            """
            INSERT INTO daily_claims (guild_id, user_id, last_claim) VALUES (%s, %s, %s)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET last_claim = EXCLUDED.last_claim
            """,
            (guild_id, user_id, date_iso),
        )

    def get_powerups(self, guild_id, user_id):
        rows = self.fetchall(
            "SELECT powerup, qty FROM powerups WHERE guild_id = %s AND user_id = %s",
            (guild_id, user_id),
        )
        return {r[0]: r[1] for r in rows}

    def add_powerup(self, guild_id, user_id, powerup, qty=1):
        self.execute(
            """
            INSERT INTO powerups (guild_id, user_id, powerup, qty) VALUES (%s, %s, %s, %s)
            ON CONFLICT (guild_id, user_id, powerup) DO UPDATE SET qty = powerups.qty + EXCLUDED.qty
            """,
            (guild_id, user_id, powerup, qty),
        )

    def remove_powerup(self, guild_id, user_id, powerup, qty=1):
        self.execute(
            "UPDATE powerups SET qty = GREATEST(qty - %s, 0) WHERE guild_id = %s AND user_id = %s AND powerup = %s",
            (qty, guild_id, user_id, powerup),
        )
        self.execute("DELETE FROM powerups WHERE qty <= 0")

    def get_birdcoin(self, guild_id, user_id):
        row = self.fetchone(
            "SELECT balance FROM birdcoin WHERE guild_id = %s AND user_id = %s",
            (guild_id, user_id),
        )
        return float(row[0]) if row and row[0] is not None else 0.0

    def get_autodefend(self, guild_id, user_id):
        row = self.fetchone(
            "SELECT birds FROM autodefend WHERE guild_id = %s AND user_id = %s",
            (int(guild_id), int(user_id)),
        )
        if not row or row[0] is None:
            return {}
        val = row[0]
        if isinstance(val, dict):
            return val
        if isinstance(val, str):
            return json.loads(val)
        return {}

    def set_autodefend(self, guild_id, user_id, birds):
        birds = dict(birds) if birds else {}
        if not birds:
            self.execute(
                "DELETE FROM autodefend WHERE guild_id = %s AND user_id = %s",
                (int(guild_id), int(user_id)),
            )
            return
        self.execute(
            """
            INSERT INTO autodefend (guild_id, user_id, birds) VALUES (%s, %s, %s)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET birds = EXCLUDED.birds
            """,
            (int(guild_id), int(user_id), json.dumps(birds)),
        )

    def add_birdcoin(self, guild_id, user_id, amount):
        self.execute(
            """
            INSERT INTO birdcoin (guild_id, user_id, balance) VALUES (%s, %s, %s)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET balance = birdcoin.balance + EXCLUDED.balance
            """,
            (guild_id, user_id, amount),
        )

    def set_birdcoin(self, guild_id, user_id, amount):
        self.execute(
            """
            INSERT INTO birdcoin (guild_id, user_id, balance) VALUES (%s, %s, %s)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET balance = EXCLUDED.balance
            """,
            (int(guild_id), int(user_id), amount),
        )

    def ban_birdbot(self, guild_id, user_id):
        self.execute(
            "INSERT INTO birdbot_bans (guild_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (int(guild_id), int(user_id)),
        )

    def unban_birdbot(self, guild_id, user_id):
        self.execute(
            "DELETE FROM birdbot_bans WHERE guild_id = %s AND user_id = %s",
            (int(guild_id), int(user_id)),
        )

    def unban_birdbot_global(self, user_id):
        self.execute(
            "DELETE FROM birdbot_bans WHERE user_id = %s",
            (int(user_id),),
        )

    def is_user_banned(self, guild_id, user_id):
        row = self.fetchone(
            "SELECT 1 FROM birdbot_bans WHERE user_id = %s AND (guild_id = 0 OR guild_id = %s) LIMIT 1",
            (int(user_id), int(guild_id)),
        )
        return row is not None

    def get_banned_user_ids(self, guild_id):
        """Return set of user IDs banned in this guild or globally."""
        rows = self.fetchall(
            "SELECT DISTINCT user_id FROM birdbot_bans WHERE guild_id = %s OR guild_id = 0",
            (int(guild_id),),
        )
        return {int(r[0]) for r in rows}

    def get_globally_banned_user_ids(self):
        """Return set of user IDs that are globally banned."""
        rows = self.fetchall(
            "SELECT DISTINCT user_id FROM birdbot_bans WHERE guild_id = 0",
        )
        return {int(r[0]) for r in rows}

    def get_all_bans_map(self):
        """Return (global_set, {guild_id: {user_id, ...}}) for all bans."""
        rows = self.fetchall("SELECT guild_id, user_id FROM birdbot_bans")
        global_set = set()
        guild_map = {}
        for g, u in rows:
            g, u = int(g), int(u)
            if g == 0:
                global_set.add(u)
            else:
                guild_map.setdefault(g, set()).add(u)
        return global_set, guild_map

    def get_bans(self, guild_id, user_id=None):
        if user_id is not None:
            rows = self.fetchall(
                "SELECT guild_id FROM birdbot_bans WHERE user_id = %s",
                (int(user_id),),
            )
        else:
            rows = self.fetchall(
                "SELECT DISTINCT user_id FROM birdbot_bans WHERE guild_id = %s OR guild_id = 0",
                (int(guild_id),),
            )
        return rows

    def spend_birdcoin(self, guild_id, user_id, amount):
        """Atomically deduct BirdCoin, refusing overdrafts. Returns success."""
        amount = max(0.0, float(amount or 0))
        if amount <= 0:
            return True
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                coins = self._lock_coins(cur, guild_id, [user_id])
                if coins[user_id] < amount:
                    conn.rollback()
                    return False
                coins[user_id] -= amount
                cur.execute(
                    "UPDATE birdcoin SET balance = %s WHERE guild_id = %s AND user_id = %s",
                    (coins[user_id], guild_id, user_id),
                )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    # --- Atomic economy helpers (SELECT ... FOR UPDATE transactions) ---
    # These serialize every read-modify-write on inventories / birdcoin so
    # concurrent commands cannot duplicate coins or birds.

    def _lock_inventories(self, cur, guild_id, user_ids):
        users = sorted({int(u) for u in user_ids})
        birds = {}
        for uid in users:
            cur.execute(
                "INSERT INTO inventories (guild_id, user_id, birds) VALUES (%s, %s, '[]') "
                "ON CONFLICT (guild_id, user_id) DO UPDATE SET birds = inventories.birds",
                (guild_id, uid),
            )
            cur.execute(
                "SELECT birds FROM inventories WHERE guild_id = %s AND user_id = %s FOR UPDATE",
                (guild_id, uid),
            )
            row = cur.fetchone()
            birds[uid] = self._loads_json(row[0]) if row else []
        return birds

    def _lock_coins(self, cur, guild_id, user_ids):
        users = sorted({int(u) for u in user_ids})
        coins = {}
        for uid in users:
            cur.execute(
                "INSERT INTO birdcoin (guild_id, user_id, balance) VALUES (%s, %s, 0) "
                "ON CONFLICT (guild_id, user_id) DO UPDATE SET balance = birdcoin.balance",
                (guild_id, uid),
            )
            cur.execute(
                "SELECT balance FROM birdcoin WHERE guild_id = %s AND user_id = %s FOR UPDATE",
                (guild_id, uid),
            )
            row = cur.fetchone()
            coins[uid] = float(row[0]) if row and row[0] is not None else 0.0
        return coins

    def sell_birds(self, guild_id, user_id, canon, n):
        """Atomically sell up to n birds of `canon`. Returns (sold, remaining_after)."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                birds = self._lock_inventories(cur, guild_id, [user_id])[user_id]
                counts = {}
                for b in birds:
                    counts[b] = counts.get(b, 0) + 1
                owned = counts.get(canon, 0)
                n = max(0, min(int(n) if n is not None else 0, owned))
                if n == 0:
                    conn.rollback()
                    return 0, owned
                new_list = []
                removed = 0
                for b in birds:
                    if b == canon and removed < n:
                        removed += 1
                    else:
                        new_list.append(b)
                cur.execute(
                    "UPDATE inventories SET birds = %s WHERE guild_id = %s AND user_id = %s",
                    (json.dumps(new_list), guild_id, user_id),
                )
            conn.commit()
            return removed, owned - removed
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def transfer_birds(self, guild_id, from_user, to_user, birds_list):
        """Atomically move birds from one inventory to another. Returns the birds moved."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                birds = self._lock_inventories(cur, guild_id, [from_user, to_user])
                moved = []
                for b in birds_list or []:
                    if b in birds[from_user]:
                        birds[from_user].remove(b)
                        birds[to_user].append(b)
                        moved.append(b)
                if moved:
                    for uid in (from_user, to_user):
                        cur.execute(
                            "UPDATE inventories SET birds = %s WHERE guild_id = %s AND user_id = %s",
                            (json.dumps(birds[uid]), guild_id, uid),
                        )
            conn.commit()
            return moved
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def deduct_birds(self, guild_id, user_id, birds_list):
        """Atomically remove birds from an inventory. Returns the birds removed."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                birds = self._lock_inventories(cur, guild_id, [user_id])
                removed = []
                for b in birds_list or []:
                    if b in birds[user_id]:
                        birds[user_id].remove(b)
                        removed.append(b)
                if removed:
                    cur.execute(
                        "UPDATE inventories SET birds = %s WHERE guild_id = %s AND user_id = %s",
                        (json.dumps(birds[user_id]), guild_id, user_id),
                    )
            conn.commit()
            return removed
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def transfer_coins(self, guild_id, from_user, to_user, amount):
        """Atomically move BirdCoin between users. Refuses overdrafts. Returns success."""
        amount = max(0.0, float(amount or 0))
        if amount <= 0:
            return False
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                coins = self._lock_coins(cur, guild_id, [from_user, to_user])
                if coins[from_user] < amount:
                    conn.rollback()
                    return False
                coins[from_user] -= amount
                coins[to_user] += amount
                for uid in (from_user, to_user):
                    cur.execute(
                        "UPDATE birdcoin SET balance = %s WHERE guild_id = %s AND user_id = %s",
                        (coins[uid], guild_id, uid),
                    )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def trade(self, guild_id, user_a, user_b, coins_a_to_b, birds_a_to_b, coins_b_to_a, birds_b_to_a):
        """Atomically settle a trade. Returns (ok, reason). Locks rows in ascending user order."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                a, b = int(user_a), int(user_b)
                birds = self._lock_inventories(cur, guild_id, [a, b])
                coins = self._lock_coins(cur, guild_id, [a, b])
                coins_a_to_b = max(0, int(coins_a_to_b or 0))
                coins_b_to_a = max(0, int(coins_b_to_a or 0))
                birds_a = {k: int(v) for k, v in (birds_a_to_b or {}).items() if int(v or 0) > 0}
                birds_b = {k: int(v) for k, v in (birds_b_to_a or {}).items() if int(v or 0) > 0}
                if coins_a_to_b == 0 and coins_b_to_a == 0 and not birds_a and not birds_b:
                    conn.rollback()
                    return False, "Nothing to trade."
                if coins[a] < coins_a_to_b:
                    conn.rollback()
                    return False, "One of the users no longer has enough BirdCoin."
                if coins[b] < coins_b_to_a:
                    conn.rollback()
                    return False, "One of the users no longer has enough BirdCoin."
                cnt_a = {}
                for x in birds[a]:
                    cnt_a[x] = cnt_a.get(x, 0) + 1
                cnt_b = {}
                for x in birds[b]:
                    cnt_b[x] = cnt_b.get(x, 0) + 1
                for bird, need in birds_a.items():
                    if cnt_a.get(bird, 0) < need:
                        conn.rollback()
                        return False, "One of the users no longer has enough birds."
                for bird, need in birds_b.items():
                    if cnt_b.get(bird, 0) < need:
                        conn.rollback()
                        return False, "One of the users no longer has enough birds."
                for bird, need in birds_a.items():
                    for _ in range(need):
                        birds[a].remove(bird)
                        birds[b].append(bird)
                for bird, need in birds_b.items():
                    for _ in range(need):
                        birds[b].remove(bird)
                        birds[a].append(bird)
                coins[a] = coins[a] - coins_a_to_b + coins_b_to_a
                coins[b] = coins[b] - coins_b_to_a + coins_a_to_b
                for uid in (a, b):
                    cur.execute(
                        "UPDATE inventories SET birds = %s WHERE guild_id = %s AND user_id = %s",
                        (json.dumps(birds[uid]), guild_id, uid),
                    )
                    cur.execute(
                        "UPDATE birdcoin SET balance = %s WHERE guild_id = %s AND user_id = %s",
                        (coins[uid], guild_id, uid),
                    )
            conn.commit()
            return True, None
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def get_guild_boost(self, guild_id):
        row = self.fetchone(
            "SELECT boosts FROM guild_boosts WHERE guild_id = %s",
            (int(guild_id),),
        )
        return int(row[0]) if row and row[0] is not None else 0

    def set_guild_boost(self, guild_id, boosts):
        self.execute(
            """
            INSERT INTO guild_boosts (guild_id, boosts) VALUES (%s, %s)
            ON CONFLICT (guild_id) DO UPDATE SET boosts = EXCLUDED.boosts
            """,
            (int(guild_id), int(boosts)),
        )

    def increment_guild_boost(self, guild_id, user_id, max_level=20):
        """Atomically buy one boost level from a payer. Returns (ok, cost, new_level)."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                gid = int(guild_id)
                uid = int(user_id)
                cur.execute(
                    "INSERT INTO guild_boosts (guild_id, boosts) VALUES (%s, 0) "
                    "ON CONFLICT (guild_id) DO UPDATE SET boosts = guild_boosts.boosts",
                    (gid,),
                )
                cur.execute(
                    "SELECT boosts FROM guild_boosts WHERE guild_id = %s FOR UPDATE",
                    (gid,),
                )
                row = cur.fetchone()
                current = int(row[0]) if row and row[0] is not None else 0
                if current >= max_level:
                    conn.rollback()
                    return False, 0, current
                cost = (current + 1) * 1000
                coins = self._lock_coins(cur, gid, [uid])
                if coins[uid] < cost:
                    conn.rollback()
                    return False, cost, current
                coins[uid] -= cost
                cur.execute(
                    "UPDATE birdcoin SET balance = %s WHERE guild_id = %s AND user_id = %s",
                    (coins[uid], gid, uid),
                )
                cur.execute(
                    "UPDATE guild_boosts SET boosts = %s WHERE guild_id = %s",
                    (current + 1, gid),
                )
            conn.commit()
            return True, cost, current + 1
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def log_battle(self, guild_id, attacker_id, defender_id, winner_id, attacker_birds, defender_birds, stolen_birds):
        self.execute(
            """
            INSERT INTO battle_log (guild_id, attacker_id, defender_id, winner_id, attacker_birds, defender_birds, stolen_birds)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (guild_id, attacker_id, defender_id, winner_id, json.dumps(attacker_birds), json.dumps(defender_birds), json.dumps(stolen_birds)),
        )

    def get_battle_log(self, guild_id, user_id, limit=10):
        rows = self.fetchall(
            """
            SELECT attacker_id, defender_id, winner_id, attacker_birds, defender_birds, stolen_birds, created_at
            FROM battle_log
            WHERE guild_id = %s AND (attacker_id = %s OR defender_id = %s)
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (guild_id, user_id, user_id, limit),
        )
        return rows

    def add_redeem_code(self, code, uses_left, rewards, unlimited=True):
        self.execute(
            """
            INSERT INTO redeem_codes (code, uses_left, rewards, unlimited) VALUES (%s, %s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET
                uses_left = EXCLUDED.uses_left,
                rewards = EXCLUDED.rewards,
                unlimited = EXCLUDED.unlimited
            """,
            (code.lower(), int(uses_left), json.dumps(rewards), bool(unlimited)),
        )

    def get_redeem_code(self, code):
        return self.fetchone(
            "SELECT uses_left, rewards, unlimited FROM redeem_codes WHERE code = %s",
            (code.lower(),),
        )

    def claim_redeem(self, guild_id, user_id, code):
        """Atomically claim a redeem code. Returns (status, rewards, uses_left_remaining).
        status: 'ok' | 'used' | 'empty' | 'invalid'.
        uses_left_remaining is None when the code is unlimited."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT uses_left, rewards, unlimited FROM redeem_codes WHERE code = %s FOR UPDATE", (code.lower(),))
                row = cur.fetchone()
                if not row:
                    conn.commit()
                    return "invalid", {}, 0
                uses_left, rewards_raw, unlimited = row
                if not unlimited and uses_left <= 0:
                    conn.commit()
                    return "empty", {}, 0
                cur.execute(
                    "SELECT 1 FROM redeem_claims WHERE code = %s AND user_id = %s",
                    (code.lower(), int(user_id)),
                )
                if cur.fetchone():
                    conn.commit()
                    return "used", {}, 0
                if not unlimited:
                    cur.execute(
                        "UPDATE redeem_codes SET uses_left = uses_left - 1 WHERE code = %s AND uses_left > 0",
                        (code.lower(),),
                    )
                    if cur.rowcount == 0:
                        conn.commit()
                        return "empty", {}, 0
                cur.execute(
                    "INSERT INTO redeem_claims (code, user_id, guild_id) VALUES (%s, %s, %s)",
                    (code.lower(), int(user_id), int(guild_id)),
                )
                conn.commit()
                rewards = self._loads_json(rewards_raw) if rewards_raw else {}
                remaining = None if unlimited else uses_left - 1
                return "ok", rewards, remaining
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def get_winrate(self, guild_id, user_id):
        row = self.fetchone(
            """
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE winner_id = %s) as wins
            FROM battle_log
            WHERE guild_id = %s AND (attacker_id = %s OR defender_id = %s)
            """,
            (user_id, guild_id, user_id, user_id),
        )
        if row and row[0] > 0:
            return {"total": row[0], "wins": row[1], "rate": row[1] / row[0] * 100}
        return {"total": 0, "wins": 0, "rate": 0}

    def get_birdcage(self, guild_id, user_id):
        row = self.fetchone(
            "SELECT birds, level, accumulated FROM birdcage WHERE guild_id = %s AND user_id = %s",
            (guild_id, user_id),
        )
        if row:
            return {"birds": self._loads_json(row[0]), "level": int(row[1]), "accumulated": float(row[2])}
        return {"birds": [], "level": 1, "accumulated": 0.0}

    def save_birdcage(self, guild_id, user_id, birds, level, accumulated):
        self.execute(
            """
            INSERT INTO birdcage (guild_id, user_id, birds, level, accumulated) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET birds = EXCLUDED.birds, level = EXCLUDED.level, accumulated = EXCLUDED.accumulated
            """,
            (guild_id, user_id, json.dumps(birds), int(level), float(accumulated)),
        )

    def get_all_birdcages(self):
        rows = self.fetchall(
            "SELECT guild_id, user_id, birds, level, accumulated FROM birdcage WHERE birds != '[]'"
        )
        return [
            {"guild_id": int(r[0]), "user_id": int(r[1]), "birds": self._loads_json(r[2]), "level": int(r[3]), "accumulated": float(r[4])}
            for r in rows
        ]

    def get_catch_stats(self, user_id):
        row = self.fetchone(
            "SELECT catches, total_duration, instant, hist FROM catch_stats WHERE user_id = %s",
            (int(user_id),),
        )
        if not row:
            return {"catches": 0, "total_duration": 0.0, "instant": 0, "hist": []}
        return {
            "catches": int(row[0]),
            "total_duration": float(row[1]),
            "instant": int(row[2]),
            "hist": self._loads_json(row[3]),
        }

    def add_catch(self, user_id, duration, max_hist=20):
        stats = self.get_catch_stats(user_id)
        hist = stats["hist"][-max_hist:] + [float(duration)]
        self.execute(
            """
            INSERT INTO catch_stats (user_id, catches, total_duration, instant, hist)
            VALUES (%s, 1, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                catches = catch_stats.catches + 1,
                total_duration = catch_stats.total_duration + EXCLUDED.total_duration,
                instant = catch_stats.instant + EXCLUDED.instant,
                hist = EXCLUDED.hist
            """,
            (
                int(user_id),
                float(duration),
                1 if float(duration) < 1.0 else 0,
                json.dumps(hist),
            ),
        )
        return {
            "catches": stats["catches"] + 1,
            "total_duration": stats["total_duration"] + float(duration),
            "instant": stats["instant"] + (1 if float(duration) < 1.0 else 0),
            "hist": hist,
        }

    def reset_catch_stats(self, user_id):
        self.execute("DELETE FROM catch_stats WHERE user_id = %s", (int(user_id),))

    def get_server_mods(self, guild_id):
        row = self.fetchone(
            "SELECT mods FROM server_mods WHERE guild_id = %s", (int(guild_id),)
        )
        if not row or row[0] is None:
            return {}
        val = row[0]
        if isinstance(val, dict):
            return val
        if isinstance(val, str):
            return json.loads(val)
        return {}

    def set_server_mods(self, guild_id, mods):
        if mods:
            self.execute(
                """
                INSERT INTO server_mods (guild_id, mods) VALUES (%s, %s)
                ON CONFLICT (guild_id) DO UPDATE SET mods = EXCLUDED.mods
                """,
                (int(guild_id), json.dumps(mods)),
            )
        else:
            self.execute("DELETE FROM server_mods WHERE guild_id = %s", (int(guild_id),))

    def get_all_server_mods(self):
        rows = self.fetchall("SELECT guild_id, mods FROM server_mods")
        result = {}
        for g, m in rows:
            if m is None:
                continue
            val = m if isinstance(m, dict) else json.loads(m)
            result[int(g)] = val
        return result

    def save_web_session(self, token, user_id, username, manageable, expires, refresh_token=None, last_valid=None):
        if refresh_token is None:
            refresh_token = ""
        if last_valid is None:
            last_valid = 0
        self.execute(
            "INSERT INTO web_sessions (token, user_id, username, manageable, expires, refresh_token, last_valid) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (token) DO UPDATE SET user_id = EXCLUDED.user_id, "
            "username = EXCLUDED.username, manageable = EXCLUDED.manageable, "
            "expires = EXCLUDED.expires, refresh_token = EXCLUDED.refresh_token, "
            "last_valid = EXCLUDED.last_valid",
            (token, user_id, username, json.dumps(manageable), int(expires), refresh_token, int(last_valid)),
        )

    def get_web_session(self, token):
        row = self.fetchone(
            "SELECT user_id, username, manageable, expires, refresh_token, last_valid FROM web_sessions WHERE token = %s",
            (token,),
        )
        if not row:
            return None
        return {
            "user": {"id": row[0], "username": row[1]},
            "manageable": json.loads(row[2] or "{}"),
            "exp": float(row[3]),
            "refresh": row[4] or None,
            "last_valid": float(row[5] or 0),
        }

    def delete_web_session(self, token):
        self.execute("DELETE FROM web_sessions WHERE token = %s", (token,))

    def cleanup_web_sessions(self):
        self.execute("DELETE FROM web_sessions WHERE expires < %s", (int(time.time()),))