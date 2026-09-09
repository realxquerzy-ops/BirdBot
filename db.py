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