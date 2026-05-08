import threading
import random
import re, socket, hashlib, secrets, string
from typing import Dict, Sequence, TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from Server import Server
    from Channel import Channel

def irc_lower(s: bytes) -> bytes:
    trans = bytes.maketrans((string.ascii_lowercase.upper() + "[]\\^").encode(), (string.ascii_lowercase + "{}|~").encode())
    return s.translate(trans)

class Client:
    __linesep_regexp = re.compile(rb"\r?\n")
    HIERARCHY = {"owner": 4, "superop": 3, "op": 2, "voice": 1, "user": 0}
    PREFIXES = {"owner": b"~", "superop": b"&", "op": b"@", "voice": b"+", "user": b""}
    LVL_TO_MODE = {"superop": b"+a", "op": b"+o", "voice": b"+v"}

    def __init__(self, server: "Server", sock: socket.socket) -> None:
        self.server, self.socket = server, sock
        self.channels: Dict[bytes, "Channel"] = {}
        self.nickname, self.user = b"", b""
        self.authenticated = False
        self.host = sock.getpeername()[0].encode()
        self.is_identified = False
        self.needs_identification = False # New flag
        self.ident_timer: Optional[threading.Timer] = None
        self.__readbuffer, self.__writebuffer = b"", b""
        self.__handle_command: Callable[[bytes, Sequence[bytes]], None] = self.__registration_handler

    @property
    def prefix(self) -> bytes: return b"%s!%s@%s" % (self.nickname, self.user, self.host)
    def write_queue_size(self) -> int: return len(self.__writebuffer)
    def message(self, msg: bytes) -> None: self.__writebuffer += msg + b"\r\n"
    def reply(self, msg: bytes) -> None: self.message(b":%s %s" % (self.server.name, msg))
    
    def check_auth(self, password, stored_hash, stored_salt):
        input_hash = hashlib.sha256((password + stored_salt).encode()).hexdigest()
        if input_hash == stored_hash:
            self.authenticated = True
            return True
        return False

    def send_numeric(self, code, message):
        full_msg = f":bigircd {code} {self.nickname or '*'} {message}\r\n"
        self.socket.send(full_msg.encode())
    
    def __registration_handler(self, command: bytes, arguments: Sequence[bytes]) -> None:
        if command == b"CAP":
            if arguments and arguments[0] == b"LS": 
                self.reply(b"CAP * LS :")
        
        elif command == b"NICK" and arguments:
            new_nick = arguments[0]
            low_nick = irc_lower(new_nick).decode()
            
            # Check if nickname is registered in DB for the grace-period timer
            with self.server.get_db() as conn:
                row = conn.execute("SELECT 1 FROM users WHERE nickname=?", (low_nick,)).fetchone()
                if row:
                    self.needs_identification = True
                    self.reply(b"NOTICE AUTH :*** This nickname is registered. You have 30 seconds to /IDENTIFY.")
                    
                    # Start the enforcement timer
                    import threading
                    self.ident_timer = threading.Timer(30.0, self.enforce_guest_rename)
                    self.ident_timer.daemon = True
                    self.ident_timer.start()
            
            self.nickname = new_nick
            self.server.client_changed_nickname(self, None)

        elif command == b"USER" and len(arguments) >= 4:
            self.user = arguments[0]
        
        # Once both NICK and USER are received, finalize registration
        if self.nickname and self.user:
            # 1. Send the standard welcome burst
            self.reply(b"001 %s :Welcome to BigIRCd, %s" % (self.nickname, self.prefix))
            self.reply(b"002 %s :Your host is %s, version 1.0" % (self.nickname, self.server.name))
            self.reply(b"004 %s %s BigIRCd 1.0 aiov" % (self.nickname, self.server.name))
            
            # 2. Transition the handler so the client is "fully connected" before receiving the MOTD
            self.__handle_command = self.__command_handler
            
            # 3. Trigger the MOTD from the file
            self.send_motd()
            
    def enforce_guest_rename(self):
        """Timer callback to force rename if not identified."""
        if not self.is_identified and self.needs_identification:
            old_nick = self.nickname
            old_prefix = self.prefix
            # Generate GuestXXXXXX
            guest_num = random.randint(100000, 999999)
            new_nick = f"Guest{guest_num}".encode()
            
            self.nickname = new_nick
            self.needs_identification = False
            self.server.client_changed_nickname(self, old_nick)
            
            self.message(b":%s NICK %s" % (old_prefix, new_nick))
            self.reply(b"NOTICE %s :Identification timeout. You have been renamed." % new_nick)
            self.ident_timer = None # Clear the reference

    def send_motd(self):
        self.reply(b"375 %s :- %s MOTD -" % (self.nickname, self.server.name))
        
        try:
            # Encoding utf-8 for special ASCII characters
            with open("motd.txt", "r", encoding="utf-8") as f:
                for line in f:
                    # rstrip() removes the \n but leaves leading spaces for the art
                    clean_line = line.rstrip("\n").rstrip("\r")
                    self.reply(b"372 %s :- %s" % (self.nickname, clean_line.encode()))
        except FileNotFoundError:
            self.reply(b"372 %s :- (motd.txt not found)" % self.nickname)
        except Exception:
            self.reply(b"372 %s :- (Error reading MOTD)" % self.nickname)

        self.reply(b"376 %s :End of /MOTD" % self.nickname)

    def __command_handler(self, command: bytes, args: Sequence[bytes]) -> None:
        if self.needs_identification and not self.is_identified:
            if command not in [b"IDENTIFY", b"QUIT", b"PING", b"PONG"]:
                self.reply(b"451 %s :You must identify to use this command." % self.nickname)
                return
        cmd_map = {
            b"PING": self.handle_ping, b"JOIN": self.handle_join, b"PRIVMSG": self.handle_privmsg,
            b"TOPIC": self.handle_topic, b"MODE": self.handle_mode, b"QUIT": lambda a: self.disconnect("Quit"),
            b"WHOIS": self.handle_whois, b"LIST": self.handle_list, b"KICK": self.handle_kick,
            b"REGISTER": self.handle_register, b"IDENTIFY": self.handle_identify,
            b"REGISTERCHAN": self.handle_register_chan, b"ACCESS": self.handle_access, 
            b"DEACCESS": self.handle_deaccess, b"NAMES": self.handle_names,
            b"PART": self.handle_part, b"REJOIN": self.handle_rejoin,
            b"NICK": self.handle_nick
        }
        if command in cmd_map: cmd_map[command](args)
    
    def handle_nick(self, args: Sequence[bytes]) -> None:
        if not args: return
        new_nick = args[0]
        old_nick = self.nickname
        old_prefix = self.prefix

        # Check if the nickname is already taken
        if self.server.get_client(new_nick):
            self.reply(b"433 %s %s :Nickname is already in use" % (self.nickname or b"*", new_nick))
            return

        # Update the server's nickname mapping and local property
        self.nickname = new_nick
        self.server.client_changed_nickname(self, old_nick)

        # 1. Inform the user of their own change
        self.message(b":%s NICK %s" % (old_prefix, new_nick))

        # 2. Inform everyone in shared channels
        notified_clients = {self}
        for chan in self.channels.values():
            for member in chan.members:
                if member not in notified_clients:
                    member.message(b":%s NICK %s" % (old_prefix, new_nick))
                    notified_clients.add(member)
    
    def handle_part(self, args):
        if not args: return
        chan_name = irc_lower(args[0])
        if chan_name in self.channels:
            chan = self.channels[chan_name]
            reason = args[1] if len(args) > 1 else b"Leaving"
            self.message_channel(chan, b"PART", b"%s :%s" % (chan.name, reason), include_self=True)
            chan.remove_client(self)
            del self.channels[chan_name]

    def handle_rejoin(self, args):
        """Custom command to quickly cycle a channel."""
        if not args: return
        self.handle_part(args)
        self.handle_join(args)

    def handle_ping(self, args):
        payload = args[0] if args else self.server.name
        self.message(b":%s PONG %s :%s" % (self.server.name, self.server.name, payload))

    def handle_whois(self, args):
        if not args: return
        t = self.server.get_client(args[0])
        if not t: return self.reply(b"401 %s %s :No such nick" % (self.nickname, args[0]))
        self.reply(b"311 %s %s %s %s * :User" % (self.nickname, t.nickname, t.user, t.host))
        chan_list = [c.name for c in t.channels.values()]
        self.reply(b"319 %s %s :%s" % (self.nickname, t.nickname, b" ".join(chan_list)))
        self.reply(b"318 %s %s :End of WHOIS" % (self.nickname, t.nickname))

    def handle_join(self, args):
        if not self.is_identified: return self.reply(b"NOTICE %s :Identify first." % self.nickname)
        chan = self.server.get_channel(args[0])
        if chan.is_banned(self.nickname): return self.reply(b"474 %s %s :Banned" % (self.nickname, chan.name))
        
        my_lvl = chan.get_user_level(self)
        if chan.is_invite_only() and not chan.has_invite(self.nickname) and self.HIERARCHY[my_lvl] == 0:
            return self.reply(b"473 %s %s :Invite Only" % (self.nickname, chan.name))
        
        chan.add_member(self)
        self.channels[irc_lower(chan.name)] = chan
        self.message_channel(chan, b"JOIN", chan.name, include_self=True)
        if my_lvl in self.LVL_TO_MODE:
            self.message_channel(chan, b"MODE", b"%s %s %s" % (chan.name, self.LVL_TO_MODE[my_lvl], self.nickname), include_self=True)
        
        # Send current topic and name list on join
        self.handle_topic([chan.name])
        self.send_names(chan)

    def handle_names(self, args):
        if not args: return
        chan_name = args[0]
        if self.server.has_channel(chan_name):
            chan = self.server.get_channel(chan_name)
            self.send_names(chan)
        else:
            self.reply(b"366 %s %s :End of /NAMES list" % (self.nickname, chan_name))

    def send_names(self, chan: "Channel"):
        """Sends the standard IRC name list (Roster) for a channel."""
        names_list = []
        for m in chan.members:
            lvl = chan.get_user_level(m)
            prefix = self.PREFIXES.get(lvl, b"")
            names_list.append(prefix + m.nickname)
        
        self.reply(b"353 %s = %s :%s" % (self.nickname, chan.name, b" ".join(names_list)))
        self.reply(b"366 %s %s :End of /NAMES list" % (self.nickname, chan.name))

    def handle_topic(self, args):
        if not args: return
        chan = self.server.get_channel(args[0])
        
        # If providing a new topic: /TOPIC #channel :New Topic
        if len(args) > 1:
            if self.HIERARCHY[chan.get_user_level(self)] >= 2: # Ops and up
                new_topic = args[1]
                chan._topic = new_topic.decode() if isinstance(new_topic, bytes) else new_topic
                # Notify everyone in the channel of the change
                self.message_channel(chan, b"TOPIC", b"%s :%s" % (chan.name, chan._topic.encode()), include_self=True)
            else:
                self.reply(b"482 %s %s :You're not channel operator" % (self.nickname, chan.name))
        else:
            # Just viewing the topic: /TOPIC #channel
            topic = chan._topic
            if isinstance(topic, str): topic = topic.encode()
            if topic:
                self.reply(b"332 %s %s :%s" % (self.nickname, chan.name, topic))
            else:
                self.reply(b"331 %s %s :No topic is set" % (self.nickname, chan.name))

    def handle_mode(self, args):
        if len(args) < 1: return
        chan = self.server.get_channel(args[0])
        my_lvl = self.HIERARCHY[chan.get_user_level(self)]

        if len(args) == 2:
            if args[1] == b"+b":
                with self.server.get_db() as conn:
                    rows = conn.execute("SELECT mask FROM channel_bans WHERE channel_name=?", (irc_lower(chan.name).decode(),)).fetchall()
                    for r in rows: self.reply(b"367 %s %s %s" % (self.nickname, chan.name, r[0].encode()))
                    return self.reply(b"368 %s %s :End of Ban List" % (self.nickname, chan.name))
            if args[1].upper() == b"+I":
                with self.server.get_db() as conn:
                    rows = conn.execute("SELECT mask FROM channel_access WHERE channel=? AND level='INVITE'", (irc_lower(chan.name).decode(),)).fetchall()
                    for r in rows: self.reply(b"346 %s %s %s" % (self.nickname, chan.name, r[0].encode()))
                    return self.reply(b"347 %s %s :End of Invite List" % (self.nickname, chan.name))

        if len(args) < 3 or my_lvl < 2: return
        mode, target = args[1], args[2]
        low_chan = irc_lower(chan.name).decode()

        with self.server.get_db() as conn:
            if mode == b"+b":
                conn.execute("INSERT OR REPLACE INTO channel_bans VALUES (?, ?)", (low_chan, irc_lower(target).decode()))
            elif mode == b"-b":
                conn.execute("DELETE FROM channel_bans WHERE channel_name=? AND mask=?", (low_chan, irc_lower(target).decode()))
            elif mode == b"+i":
                conn.execute("INSERT OR REPLACE INTO channel_access (channel, mask, level) VALUES (?, ?, 'INVITE')", (low_chan, irc_lower(target).decode()))
            elif mode == b"-i":
                conn.execute("DELETE FROM channel_access WHERE channel=? AND mask=? AND level='INVITE'", (low_chan, irc_lower(target).decode()))
            conn.commit()
        self.message_channel(chan, b"MODE", b"%s %s %s" % (chan.name, mode, target), include_self=True)

    def handle_access(self, args):
        if not args: return
        chan_name = args[0]
        with self.server.get_db() as conn:
            rows = conn.execute("SELECT mask, level FROM channel_access WHERE channel=?", (irc_lower(chan_name).decode(),)).fetchall()
            self.reply(b"NOTICE %s :--- Access List for %s ---" % (self.nickname, chan_name))
            for n, l in rows: self.reply(b"NOTICE %s :[%s] %s" % (self.nickname, l.encode(), n.encode()))

    def handle_deaccess(self, args):
        if len(args) < 2: return
        chan = self.server.get_channel(args[0])
        target_nick = args[1]
        my_lvl = self.HIERARCHY[chan.get_user_level(self)]
        t_lvl = self.HIERARCHY[chan.get_user_level(target_nick)]

        if my_lvl > t_lvl or chan.get_user_level(self) == "owner":
            with self.server.get_db() as conn:
                conn.execute("DELETE FROM channel_access WHERE channel=? AND mask=?", 
                             (irc_lower(chan.name).decode(), irc_lower(target_nick).decode()))
                conn.commit()
            self.reply(b"NOTICE %s :Removed %s from access list." % (self.nickname, target_nick))

    def handle_register(self, args):
        salt = secrets.token_hex(8)
        h = hashlib.sha256((args[0].decode() + salt).encode()).hexdigest()
        try:
            with self.server.get_db() as conn:
                conn.execute("INSERT INTO users VALUES (?, ?, ?)", (irc_lower(self.nickname).decode(), h, salt))
                conn.commit()
            self.reply(b"NOTICE %s :Registered." % self.nickname)
        except: self.reply(b"NOTICE %s :Error/Taken." % self.nickname)

    def handle_identify(self, args):
        with self.server.get_db() as conn:
            row = conn.execute("SELECT password_hash, salt FROM users WHERE nickname=?", (irc_lower(self.nickname).decode(),)).fetchone()
            if row and hashlib.sha256((args[0].decode() + row[1]).encode()).hexdigest() == row[0]:
                self.is_identified = True
                self.needs_identification = False
                
                # Cancel the timer since they successfully logged in
                if self.ident_timer:
                    self.ident_timer.cancel()
                
                self.reply(b"NOTICE %s :Identified successfully. Restrictions lifted." % self.nickname)
            else: 
                self.reply(b"464 :Password incorrect.")

    def handle_register_chan(self, args):
        if not args: return
        chan = self.server.get_channel(args[0])
        
        try:
            with self.server.get_db() as conn:
                # Save the channel state to the database
                conn.execute(
                    "INSERT INTO registered_channels (name, owner_nick, topic, is_invite_only) VALUES (?, ?, ?, ?)", 
                    (irc_lower(chan.name).decode(), irc_lower(self.nickname).decode(), chan._topic, 1 if chan._invite_only_flag else 0)
                )
                conn.commit()
            
            # Update the local channel object status
            chan.is_registered = True
            chan.registered_owner = irc_lower(self.nickname).decode()
            
            # Feedback: Send a direct notice to the user confirming registration
            self.reply(b"NOTICE %s :Channel %s has been successfully registered to your account." % (self.nickname, chan.name))
            
        except Exception:
            self.reply(b"NOTICE %s :Registration failed. The channel might already be registered." % self.nickname)

    def message_channel(self, chan, cmd, msg, include_self=False):
        line = b":%s %s %s" % (self.prefix, cmd, msg)
        for m in chan.members:
            if m != self or include_self: m.message(line)

    def handle_privmsg(self, args):
        if len(args) < 2: return
        target, msg = args[0], args[1]
        if self.server.has_channel(target):
            chan = self.server.get_channel(target)
            self.message_channel(chan, b"PRIVMSG", b"%s :%s" % (target, msg))
        else:
            t = self.server.get_client(target)
            if t: t.message(b":%s PRIVMSG %s :%s" % (self.prefix, target, msg))

    def handle_list(self, args):
        self.reply(b"321 %s Channel :Users Topic" % self.nickname)
        for c in self.server.channels.values():
            topic = c._topic
            if isinstance(topic, str): topic = topic.encode()
            self.reply(b"322 %s %s %d :%s" % (self.nickname, c.name, len(c.members), topic))
        self.reply(b"323 %s :End of LIST" % self.nickname)

    def handle_kick(self, args):
        chan, t = self.server.get_channel(args[0]), self.server.get_client(args[1])
        if t and self.HIERARCHY[chan.get_user_level(self)] > self.HIERARCHY[chan.get_user_level(t)]:
            self.message_channel(chan, b"KICK", b"%s %s" % (chan.name, t.nickname), include_self=True)
            chan.remove_client(t)

    def socket_readable_notification(self):
        try:
            data = self.socket.recv(1024)
            if not data: self.disconnect("Closed")
            self.__readbuffer += data
            self._parse_buffer()
        except: self.disconnect("Error")

    def _parse_buffer(self):
        lines = self.__linesep_regexp.split(self.__readbuffer)
        self.__readbuffer = lines[-1]
        for line in lines[:-1]:
            if not line: continue
            parts = line.split(b" ", 1)
            cmd: bytes = parts[0].upper()
            args: list[bytes] = []
            if len(parts) > 1:
                if b" :" in parts[1]:
                    m, t = parts[1].split(b" :", 1)
                    args = m.split(b" ") + [t]
                else: args = parts[1].split(b" ")
            self.__handle_command(cmd, [a for a in args if a])

    def socket_writable_notification(self):
        try:
            sent = self.socket.send(self.__writebuffer)
            self.__writebuffer = self.__writebuffer[sent:]
        except: pass

    def disconnect(self, msg):
        self.server.remove_client(self, msg.encode()); self.socket.close()