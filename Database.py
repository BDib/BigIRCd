import sqlite3, sys
from typing import Optional, Tuple, List
from Utils import data_path
    
class DatabaseManager:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or data_path("bigircd.db")
        self._conn = None

    def __enter__(self):
        self._conn = sqlite3.connect(self.db_path)
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
            self._conn.close()
            self._conn = None

    def _query(self, sql: str, params: tuple = ()) -> List[Tuple]:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(sql, params).fetchall()

    def _execute(self, sql: str, params: tuple = ()):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(sql, params)
            conn.commit()

    def get_channel_registration(self, name: str) -> Optional[Tuple]:
        """Returns (owner, is_invite_only, topic)"""
        res = self._query("SELECT owner_nick, is_invite_only, topic FROM registered_channels WHERE name = ?", (name,))
        return res[0] if res else None

    def get_user_level(self, channel: str, nickname: str) -> str:
        """Checks channel_access for specific levels (INVITE, MOD, etc)"""
        res = self._query("SELECT level FROM channel_access WHERE channel = ? AND mask = ?", (channel, nickname))
        return res[0][0] if res else "user"

    def update_channel_topic(self, name: str, topic: str):
        self._execute("UPDATE registered_channels SET topic = ? WHERE name = ?", (topic, name))