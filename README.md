<p align="center">
  <img src="resources/public/favicon.png" alt="Maxis Logo" width="200"/>
</p>

# Maxis - Discord Bot

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![discord.py](https://img.shields.io/badge/discord.py-2.0+-blue.svg)](https://github.com/Rapptz/discord.py)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Maxis is a feature-rich Discord bot built with discord.py, offering currency system, moderation tools, utility commands, and interactive features. This bot is the successor to [UnknownBot-latest](https://github.com/UnknownCoder56/UnknownBot-latest), providing improved functionality and modern slash command support.

## Features

### 💰 Currency System
- **Economy Commands**: Work, rob, daily/weekly/monthly rewards
- **Balance Management**: Check balance, transfer money, leaderboard
- **Shop System**: Buy and use items including Hacker Laptop and Nitro
- **User Settings**: Configure DMs and passive mode for protection

### 🛡️ Moderation Tools
- **User Management**: Kick, ban, unban users
- **Warning System**: Warn users, clear warns, view warn history
- **Message Control**: Clear messages, nuke channels
- **Timeout**: Temporarily restrict users

### 🎮 Utility & Fun
- **Interactive Games**: Rock Paper Scissors
- **Information**: Bot info, server info, user info, ping
- **Custom Replies**: Set automated responses
- **Currency Converter**: Real-time currency conversion
- **Text to Image**: Convert text to images
- **Random Color Generator**: Generate random colors
- **ADMES AI**: Ask questions to the bot's AI system

### 🌐 Web Interface
- Built-in web server for monitoring and management
- ADMES server for advanced features

## Installation

### Prerequisites
- Python 3.8 or higher
- MongoDB database
- Discord Bot Token

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/UnknownCoder56/maxis.git
   cd maxis
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   
   Create a `.env` file in the root directory:
   ```env
   TOKEN=your_discord_bot_token
   CONNSTR=your_mongodb_connection_string
   PORT=8080
   ```

4. **Run the bot**
   ```bash
   python -m bot.main
   ```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TOKEN` | Discord bot token from Discord Developer Portal | Yes |
| `CONNSTR` | MongoDB connection string | Yes |
| `PORT` | Port for web server (default: 8080) | No |

### MongoDB Setup

The bot requires a MongoDB database with a collection named `UnknownCollection` in the `UnknownDatabase` database. The bot will automatically initialize data structures on first run.

## Commands

Maxis uses Discord's slash commands for all interactions. Type `/` in Discord to see available commands.

### Basic Commands

| Command | Description |
|---------|-------------|
| `/help` | Display help message with all commands |
| `/ping` | Check bot latency |
| `/hello` | Get a greeting from the bot |
| `/botinfo` | View information about Maxis |
| `/serverinfo` | Display server information |
| `/userinfo` | Display user information |
| `/replies` | View all custom replies |
| `/reply` | Set a custom reply trigger |
| `/noreply` | Remove a custom reply |
| `/dm` | Send a DM to a user |
| `/rps` | Play Rock Paper Scissors |
| `/tti` | Convert text to image |
| `/setting` | Configure your user settings |
| `/currconv` | Convert between currencies |
| `/randomcolor` | Generate a random color |
| `/admes` | Ask the ADMES AI a question |

### Currency Commands

| Command | Description |
|---------|-------------|
| `/balance` | Check your or another user's balance |
| `/daily` | Claim daily reward (🪙 5,000) |
| `/weekly` | Claim weekly reward (🪙 10,000) |
| `/monthly` | Claim monthly reward (🪙 50,000) |
| `/work` | Work to earn money |
| `/rob` | Rob another user (risky!) |
| `/give` | Transfer money to another user |
| `/baltop` | View the richest users |
| `/buy` | Purchase items from the shop |
| `/use` | Use an item from your inventory |
| `/inventory` | View your owned items |
| `/shop` | Browse available items |

### Moderation Commands

| Command | Description |
|---------|-------------|
| `/kick` | Kick a user from the server |
| `/ban` | Ban a user from the server |
| `/unban` | Unban a user |
| `/timeout` | Timeout a user temporarily |
| `/untimeout` | Remove timeout from a user |
| `/warn` | Warn a user |
| `/clearwarns` | Clear all warnings for a user |
| `/getwarns` | View warnings for a user |
| `/clear` | Delete a specified number of messages |
| `/nuke` | Clear all messages in a channel |

## Project Structure

```
maxis/
├── bot/
│   ├── commands/
│   │   ├── basic_commands.py    # Utility and fun commands
│   │   ├── currency_commands.py # Economy system commands
│   │   └── mod_commands.py      # Moderation commands
│   ├── objects/
│   │   ├── shop.py              # Shop and items
│   │   ├── user_settings.py     # User preferences
│   │   ├── warn.py              # Warning system
│   │   ├── nitro.py             # Nitro item
│   │   └── hacker_laptop.py     # Hacker Laptop item
│   ├── main.py                  # Bot entry point
│   ├── slash_commands.py        # Command setup
│   ├── components.py            # Button/select interactions
│   ├── modals.py                # Modal interactions
│   ├── helper.py                # Helper functions
│   ├── web_server.py            # Web interface
│   └── admes_server.py          # ADMES AI server
├── resources/                   # Bot resources
├── requirements.txt             # Python dependencies
└── .gitignore                   # Git ignore rules
```

## Bot Intents

The bot requires the following Discord intents:
- `message_content` - Read message content
- `members` - Access member information
- `guilds` - Access guild information
- `dm_messages` - Handle direct messages
- `guild_messages` - Read guild messages

Make sure these intents are enabled in the [Discord Developer Portal](https://discord.com/developers/applications).

## Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest new features
- Submit pull requests

## About

Maxis is the successor to [UnknownBot-latest](https://github.com/UnknownCoder56/UnknownBot-latest), rebuilt from the ground up with modern Discord API features, improved architecture, and enhanced functionality.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, questions, or feature requests, please open an issue on GitHub.

---

Made with ❤️ by UnknownCoder56
