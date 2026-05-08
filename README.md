# BigIRCd Windows Edition

A high-performance, refactored IRC server built with Python, featuring a centralized SQLite database for persistence, channel registration, and user authentication.

## ?š€ Key Features

* **User Registration & Identification**: Secure account management using SHA-256 hashing and unique salts.
* **Channel Persistence**: Register channels to save topics, access lists, and invite-only flags to a database.
* **Hierarchy System**: Role-based permissions (Owner, SuperOp, Op, Voice, User) that dictate what commands a user can execute.
* **Identification Grace Period**: Users using registered nicknames are given 30 seconds to identify; otherwise, they are automatically renamed to a Guest account.
* **Custom MOTD**: Supports a file-based Message of the Day (`motd.txt`) with ASCII art and multi-line support.
* **Cross-Platform Core**: Designed for Windows but built with portable Python logic.

## ?› ?¸? Installation & Setup

1. **Requirements**: Python 3.8+
2. **Database**: The server automatically initializes `bigircd.db` on first run.
3. **MOTD**: Create a `motd.txt` file in the root directory to customize your welcome message.
4. **Run**:
   
   ```bash
   python Main.py
   ```

## ?’¬ User Commands

### Connection & Services

| Command    | Usage                  | Description                                               |
|:---------- |:---------------------- |:--------------------------------------------------------- |
| `REGISTER` | `/REGISTER <password>` | Creates a new account for your current nickname           |
| `IDENTIFY` | `/IDENTIFY <password>` | Authenticates you with your registered nickname           |
| `NICK`     | `/NICK <new_nick>`     | Changes your nickname (broadcasts to all shared channels) |
| `QUIT`     | `/QUIT [reason]`       | Disconnects you from the server                           |

### Channel Interaction

| Command   | Usage                          | Description                                          |
|:--------- |:------------------------------ |:---------------------------------------------------- |
| `JOIN`    | `/JOIN #channel`               | Joins a channel. Checks for bans and invite status   |
| `PART`    | `/PART #channel [reason]`      | Leaves the specified channel                         |
| `REJOIN`  | `/REJOIN #channel`             | Quickly cycles your connection (Part then Join)      |
| `PRIVMSG` | `/PRIVMSG <target> :<msg>`     | Sends a private message to a user or channel         |
| `TOPIC`   | `/TOPIC #channel [:new_topic]` | Views or sets (Ops only) the channel topic           |
| `NAMES`   | `/NAMES #channel`              | Views the list of users currently in the channel     |
| `LIST`    | `/LIST`                        | Lists all active channels and their topics           |
| `WHOIS`   | `/WHOIS <nickname>`            | Shows info about a user and the channels they are in |

### Management & Access

| Command        | Usage                            | Description                                                |
|:-------------- |:-------------------------------- |:---------------------------------------------------------- |
| `REGISTERCHAN` | `/REGISTERCHAN #channel`         | Permanently registers the channel to you (must be owner)   |
| `ACCESS`       | `/ACCESS #channel`               | Lists all users with special access levels in that channel |
| `DEACCESS`     | `/DEACCESS #channel <nick>`      | Removes a user's entry from the channel access list        |
| `KICK`         | `/KICK #channel <nick>`          | Removes a user from the channel (requires Ops)             |
| `MODE`         | `/MODE #channel <mode> <target>` | Sets channel modes like `+b` (ban) or `+i` (invite)        |

## ?“– Usage Examples

### 1. First Time Setup

1. Connect to the server.
2. Register your nick: `/REGISTER MySecretPass` 
3. Identify: `/IDENTIFY MySecretPass` 

### 2. Creating a Secure Channel

1. Join a new room: `/JOIN #dev-team` 
2. Register it: `/REGISTERCHAN #dev-team` 
3. Set the topic: `/TOPIC #dev-team :Official Development Channel` 
4. Make it invite-only: `/MODE #dev-team +i` 
5. Invite a friend: `/MODE #dev-team +i MyColleague` 

### 3. Handling Troublemakers

1. Ban a mask: `/MODE #lobby +b *!*@malicious-host.com` 
2. Kick a user: `/KICK #lobby TrollUser :Please follow the rules.` 

## ?“‚ Project Structure

* `Main.py`: Entry point and server initialization.
* `Server.py`: Core socket handling, client management, and DB schema setup.
* `Client.py`: The IRC protocol engine, command handlers, and state management.
* `Channel.py`: Logic for channel membership and permission checks.
* `Database.py`: SQLite wrapper for persistent storage.
* `motd.txt`: Plain text file for the server welcome message.
