import json
from urllib.parse import urlparse

import psycopg2
from psycopg2.pool import ThreadedConnectionPool


class Database:
    def __init__(self, database_url):
        parsed = urlparse(database_url)
        self._pool = ThreadedConnectionPool(
            1, 10,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password,
            host=parsed.hostname,
            port=parsed.port,
        )

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
        rows = self.fetchall("SELECT name, sticker_id, weight, value FROM birds_data")
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
            "SELECT xp, claimed_level FROM birdpass WHERE guild_id = %s AND user_id = %s",
            (guild_id, user_id),
        )
        if row:
            return float(row[0]), int(row[1])
        return 0.0, 1

    def save_birdpass(self, guild_id, user_id, xp, claimed_level):
        self.execute(
            """
            INSERT INTO birdpass (guild_id, user_id, xp, claimed_level) VALUES (%s, %s, %s, %s)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET xp = EXCLUDED.xp, claimed_level = EXCLUDED.claimed_level
            """,
            (guild_id, user_id, xp, claimed_level),
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

    def add_birdcoin(self, guild_id, user_id, amount):
        self.execute(
            """
            INSERT INTO birdcoin (guild_id, user_id, balance) VALUES (%s, %s, %s)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET balance = birdcoin.balance + EXCLUDED.balance
            """,
            (guild_id, user_id, amount),
        )

    def remove_birdcoin(self, guild_id, user_id, amount):
        self.execute(
            "UPDATE birdcoin SET balance = GREATEST(balance - %s, 0) WHERE guild_id = %s AND user_id = %s",
            (amount, guild_id, user_id),
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