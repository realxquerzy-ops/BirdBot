import json
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

    def remove_birdcoin(self, guild_id, user_id, amount):
        self.execute(
            "UPDATE birdcoin SET balance = GREATEST(balance - %s, 0) WHERE guild_id = %s AND user_id = %s",
            (amount, guild_id, user_id),
        )

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

    def add_redeem_code(self, code, uses_left, rewards):
        self.execute(
            """
            INSERT INTO redeem_codes (code, uses_left, rewards) VALUES (%s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET uses_left = EXCLUDED.uses_left, rewards = EXCLUDED.rewards
            """,
            (code.lower(), int(uses_left), json.dumps(rewards)),
        )

    def get_redeem_code(self, code):
        return self.fetchone(
            "SELECT uses_left, rewards FROM redeem_codes WHERE code = %s",
            (code.lower(),),
        )

    def claim_redeem(self, guild_id, user_id, code):
        """Atomically claim a redeem code. Returns (status, rewards, uses_left_remaining).
        status: 'ok' | 'used' | 'empty' | 'invalid'."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT uses_left, rewards FROM redeem_codes WHERE code = %s FOR UPDATE", (code.lower(),))
                row = cur.fetchone()
                if not row:
                    conn.commit()
                    return "invalid", {}, 0
                uses_left, rewards_raw = row
                if uses_left <= 0:
                    conn.commit()
                    return "empty", {}, 0
                cur.execute(
                    "SELECT 1 FROM redeem_claims WHERE code = %s AND user_id = %s",
                    (code.lower(), int(user_id)),
                )
                if cur.fetchone():
                    conn.commit()
                    return "used", {}, 0
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
                return "ok", rewards, uses_left - 1
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