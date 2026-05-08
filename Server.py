import socket
import select
from typing import Dict, List, Optional, Any
from Database import DatabaseManager

class Server:
    def __init__(self, name: str) -> None:
        self.name = name.encode()
        self.clients: Dict[socket.socket, Any] = {}
        self.channels: Dict[bytes, Any] = {}
        self.nicknames: Dict[bytes, Any] = {}
        
        # Centralized Database Management
        self.db = DatabaseManager("bigircd.db")
        self._init_db_schema()

    def _init_db_schema(self) -> None:
        """Ensures all necessary tables for the Admin Panel exist."""
        # Using the manager's execute helper to setup tables
        self.db._execute('''
            CREATE TABLE IF NOT EXISTS users 
            (nickname TEXT PRIMARY KEY, password_hash TEXT, salt TEXT)
        ''')
        self.db._execute('''
            CREATE TABLE IF NOT EXISTS registered_channels 
            (name TEXT PRIMARY KEY, owner_nick TEXT NOT NULL, is_invite_only INTEGER DEFAULT 0, topic TEXT)
        ''')
        self.db._execute('''
            CREATE TABLE IF NOT EXISTS channel_access 
            (channel TEXT, mask TEXT, level TEXT, PRIMARY KEY (channel, mask))
        ''')
        self.db._execute('''
            CREATE TABLE IF NOT EXISTS channel_bans 
            (channel_name TEXT, mask TEXT, PRIMARY KEY (channel_name, mask))
        ''')
        # Ensure INVITE level is used in channel_access instead of a separate table if needed,
        # but Channel.py already expects channel_access for invites.

    def get_channel(self, name: bytes) -> Any:
        """Retrieves an existing channel or creates a new one in memory."""
        from Channel import Channel
        from Client import irc_lower
        
        low_name = irc_lower(name)
        if low_name not in self.channels:
            # Channel class now handles its own DB loading on init
            self.channels[low_name] = Channel(self, name)
        return self.channels[low_name]

    def remove_channel(self, channel: Any) -> None:
        """Cleans up a channel from memory."""
        from Client import irc_lower
        low_chan = irc_lower(channel.name)
        if low_chan in self.channels:
            del self.channels[low_chan]

    def has_channel(self, name: bytes) -> bool:
        from Client import irc_lower
        return irc_lower(name) in self.channels

    def get_client(self, nickname: bytes) -> Optional[Any]:
        from Client import irc_lower
        return self.nicknames.get(irc_lower(nickname))

    def client_changed_nickname(self, client: Any, old_nick: Optional[bytes]) -> None:
        from Client import irc_lower
        if old_nick:
            low_old = irc_lower(old_nick)
            if self.nicknames.get(low_old) == client:
                del self.nicknames[low_old]
        
        if client.nickname:
            low_new = irc_lower(client.nickname)
            self.nicknames[low_new] = client

    def get_db(self):
        return self.db

    def broadcast(self, chan_name: bytes, msg: bytes) -> None:
        """Sends a message to every client currently joined to a channel."""
        from Client import irc_lower
        low_name = irc_lower(chan_name)
        if low_name in self.channels:
            for client in self.channels[low_name].members:
                # Assuming client.message() handles the low-level socket send
                client.message(msg)

    def remove_client(self, client: Any, msg: bytes) -> None:
        """Handles client disconnection and cleanup."""
        from Client import irc_lower
        if client.socket in self.clients:
            del self.clients[client.socket]
        
        if client.nickname:
            low_nick = irc_lower(client.nickname)
            if low_nick in self.nicknames:
                del self.nicknames[low_nick]

    def run(self, ports: List[int]) -> None:
        """Starts the server loop and listens for connections."""
        from Client import Client
        serv_socks = []
        
        for p in ports:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.setblocking(False)
            s.bind(("", p))
            s.listen(5)
            serv_socks.append(s)
            print(f"[*] BigIRCd listening on {p}")

        while True:
            # Select loop for handling multiple sockets
            read, write, _ = select.select(
                serv_socks + list(self.clients.keys()), 
                [c.socket for c in self.clients.values() if hasattr(c, 'write_queue_size') and c.write_queue_size() > 0], 
                [], 1
            )
            
            for s in read:
                if s in serv_socks:
                    # New connection
                    conn, addr = s.accept()
                    print(f"[*] New connection from {addr[0]}")
                    new_client = Client(self, conn)
                    self.clients[conn] = new_client
                else:
                    # Existing client data
                    client = self.clients.get(s)
                    if client:
                        client.socket_readable_notification()

            for s in write:
                client = self.clients.get(s)
                if client:
                    client.socket_writable_notification()