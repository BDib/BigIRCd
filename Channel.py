from typing import Any, Dict, Optional, Set, TYPE_CHECKING, List
if TYPE_CHECKING:
    from Client import Client
    from Server import Server

class Channel:
    def __init__(self, server: "Server", name: bytes, owner_nick: Optional[str] = None, is_invite_only: int = 0, topic: str = "No topic set") -> None:
        self.server = server
        self.name = name
        
        # Values from database / Admin Panel
        self.registered_owner = owner_nick
        self._invite_only_flag = bool(int(is_invite_only))
        self._topic = topic
        
        # Active State
        self.members: Set["Client"] = set()
        self.user_levels: Dict["Client", str] = {}
        self.is_registered = False
        
        # Initialize
        self._load_registration()

    def add_member(self, client: "Client") -> None:
        """Adds a client to the channel."""
        self.members.add(client)

    def remove_client(self, client: "Client") -> None:
        """Removes client and cleans up channel if empty."""
        self.members.discard(client)
        if client in self.user_levels:
            del self.user_levels[client]
        
        if not self.members:
            self.server.remove_channel(self)

    def _load_registration(self) -> None:
        """Loads registration details, including the new Admin Panel columns."""
        from Client import irc_lower
        with self.server.get_db() as conn:
            # Updated query to grab the new columns we added to the DB
            row = conn.execute(
                "SELECT owner_nick, is_invite_only, topic FROM registered_channels WHERE name = ?", 
                (irc_lower(self.name).decode(),)
            ).fetchone()
            
            if row:
                self.is_registered = True
                self.registered_owner = row[0]
                self._invite_only_flag = bool(int(row[1]))
                self._topic = row[2]

    def is_invite_only(self) -> bool:
        """Checks if the channel is currently in +i mode."""
        return self._invite_only_flag

    def get_topic(self) -> str:
        """Returns the current channel topic."""
        return self._topic

    # --- Keep your existing ACL/Permission Logic ---

    def is_banned(self, nickname: bytes) -> bool:
        from Client import irc_lower
        with self.server.get_db() as conn:
            row = conn.execute("SELECT 1 FROM channel_bans WHERE channel_name = ? AND mask = ?", 
                               (irc_lower(self.name).decode(), irc_lower(nickname).decode())).fetchone()
            return row is not None

    def has_invite(self, nickname: bytes) -> bool:
        from Client import irc_lower
        with self.server.get_db() as conn:
            row = conn.execute("SELECT 1 FROM channel_access WHERE channel = ? AND mask = ? AND level = 'INVITE'", 
                               (irc_lower(self.name).decode(), irc_lower(nickname).decode())).fetchone()
            return row is not None

    def get_user_level(self, client_or_nick: Any) -> str:
        from Client import irc_lower, Client
        if isinstance(client_or_nick, Client):
            nick_str = irc_lower(client_or_nick.nickname).decode()
        else:
            nick_str = irc_lower(client_or_nick).decode()

        if self.is_registered and nick_str == self.registered_owner: 
            return "owner"
            
        with self.server.get_db() as conn:
            row = conn.execute("SELECT level FROM channel_access WHERE channel = ? AND mask = ?", 
                               (irc_lower(self.name).decode(), nick_str)).fetchone()
            if row: return row[0]
        
        if isinstance(client_or_nick, Client):
            return self.user_levels.get(client_or_nick, "user")
        return "user"