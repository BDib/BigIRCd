import socket
import select
import ssl
import os
from typing import Dict, List, Optional, Any
from Database import DatabaseManager
from Utils import irc_lower, data_path

class Server:
    def __init__(self, name: str) -> None:
        self.name = name.encode()
        self.clients: Dict[socket.socket, Any] = {}
        self.channels: Dict[bytes, Any] = {}
        self.nicknames: Dict[bytes, Any] = {}
        
        # Centralized Database Management
        self.db = DatabaseManager(None)
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
        
        
        low_name = irc_lower(name)
        if low_name not in self.channels:
            # Channel class now handles its own DB loading on init
            self.channels[low_name] = Channel(self, name)
        return self.channels[low_name]

    def remove_channel(self, channel: Any) -> None:
        """Cleans up a channel from memory."""
        
        low_chan = irc_lower(channel.name)
        if low_chan in self.channels:
            del self.channels[low_chan]

    def has_channel(self, name: bytes) -> bool:
        
        return irc_lower(name) in self.channels

    def get_client(self, nickname: bytes) -> Optional[Any]:
        
        return self.nicknames.get(irc_lower(nickname))

    def client_changed_nickname(self, client: Any, old_nick: Optional[bytes]) -> None:
        
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
        
        low_name = irc_lower(chan_name)
        if low_name in self.channels:
            for client in self.channels[low_name].members:
                # Assuming client.message() handles the low-level socket send
                client.message(msg)

    def remove_client(self, client: Any, msg: bytes) -> None:
        """Handles client disconnection and cleanup."""
        
        if client.socket in self.clients:
            del self.clients[client.socket]
        
        if client.nickname:
            low_nick = irc_lower(client.nickname)
            if low_nick in self.nicknames:
                del self.nicknames[low_nick]

    def run(self, ports: List[int]) -> None:
        serv_socks: List[socket.socket] = []
        ssl_ports = [6697, 7000]
        
        # 1. SSL Setup
        context: Optional[ssl.SSLContext] = None
        try:
            cert_file = data_path("cert.pem")
            key_file = data_path("key.pem")
            if os.path.exists(cert_file) and os.path.exists(key_file):
                context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                context.load_cert_chain(certfile=cert_file, keyfile=key_file)
                print("[*] SSL Context loaded successfully.")
            else:
                print("[!] SSL certificates not found. Running in plain-text mode only.")
        except Exception as e:
            print(f"[!] SSL initialization failed: {e}")
            context = None

        # 2. Bind Sockets
        for p in ports:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.setblocking(False)
                s.bind(("", p))
                s.listen(5)
                serv_socks.append(s)
                status = "(SSL ENABLED)" if p in ssl_ports and context else ""
                print(f"[*] BigIRCd listening on {p} {status}")
            except Exception as e:
                print(f"[!] Bind failed on {p}: {e}")

        try:
            while True:
                # 3. Build Select Lists
                # We need to monitor ALL clients for reading, 
                # but only those with data for writing.
                read_list = serv_socks + list(self.clients.keys())
                write_list = [s for s, c in self.clients.items() if c.write_queue_size() > 0]
                
                try:
                    readable, writable, _ = select.select(read_list, write_list, [], 0.5)
                except OSError:
                    continue

                # 4. Handle Incoming Data / New Connections
                for s in readable:
                    if s in serv_socks:
                        conn, addr = s.accept()
                        server_port = s.getsockname()[1]
                        conn.setblocking(False)

                        if server_port in ssl_ports and context is not None:
                            try:
                                # Wrap the socket
                                conn = context.wrap_socket(conn, server_side=True, do_handshake_on_connect=False)
                                # Force initiate the handshake
                                try:
                                    conn.do_handshake()
                                except (ssl.SSLWantReadError, ssl.SSLWantWriteError):
                                    pass # Normal for non-blocking
                                print(f"[*] Secure connection handshake initiated: {addr[0]}")
                            except Exception as e:
                                print(f"[!] SSL Wrap Error: {e}")
                                conn.close()
                                continue
                        else:
                            print(f"[*] Plain connection: {addr[0]}")

                        from Client import Client
                        self.clients[conn] = Client(self, conn)
                    
                    else:
                        # Existing Client Reading
                        client = self.clients.get(s)
                        if client:
                            # If it's SSL, the recv() might actually be part of a handshake
                            try:
                                client.socket_readable_notification()
                            except (ssl.SSLWantReadError, ssl.SSLWantWriteError):
                                continue
                            except Exception as e:
                                print(f"[*] Client disconnected: {e}")
                                client.disconnect("Connection Reset")

                # 5. Handle Outgoing Data (The fix for 10053 and hanging)
                for s in writable:
                    client = self.clients.get(s)
                    if client:
                        try:
                            client.socket_writable_notification()
                        except (ssl.SSLWantReadError, ssl.SSLWantWriteError):
                            continue
                        except Exception:
                            client.disconnect("Write Error")

        except KeyboardInterrupt:
            print("\n[*] Shutting down...")
        finally:
            for s in serv_socks: s.close()
            for s in list(self.clients.keys()): s.close()