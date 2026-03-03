<p align="center">
  <img src="resources/public/favicon.png" alt="Maxis Logo" width="200"/>
</p>

# Maxis - Discord Bot

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![discord.py](https://img.shields.io/badge/discord.py-2.0+-blue.svg)](https://github.com/Rapptz/discord.py)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Maxis is a multi-purpose Discord bot built with `discord.py`, with economy, moderation, utility, and interactive features.. This bot is the successor to [UnknownBot-latest](https://github.com/UnknownCoder56/UnknownBot-latest), providing improved functionality and modern slash command support.

## Features

### Utility

- Help system with category selector UI
- Bot/server/user information commands
- Custom auto-replies for message content triggers
- Math expression calculator
- Text-to-image generation (`Pillow`)
- Currency conversion via ExchangeRate API
- Color generation tools (`/makecolor`, `/randomcolor`)
- Rock-Paper-Scissors (choice or interactive buttons)
- ADMES query command + owner tunnel URL command

### Economy

- Balance tracking and money transfer
- Work/rob/daily/weekly/monthly reward commands with cooldowns
- Server and global leaderboards
- Inventory + shop + buy/use item flow
- User setting support for passive mode and bank DM notifications

### Moderation

- Kick, ban, unban
- Mute, unmute
- Warn, clearwarns, getwarns
- Clear messages and channel nuke

### Web + ADMES

- FastAPI web server (`/`) showing online status + invite button
- ADMES client that posts questions to remote bridge and polls answers

## Requirements

- Python 3.10+
- MongoDB instance
- Discord bot token

Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in project root:

```env
TOKEN=your_discord_bot_token
CONNSTR=your_mongodb_connection_string
PORT=8080
EXAPI=your_exchange_rate_api_key
OWNER_USER_ID=(your user id)
```

### Environment Variables

- `TOKEN` (required): Discord bot token
- `CONNSTR` (required): MongoDB connection string
- `PORT` (optional, default `8080`): FastAPI web server port
- `EXAPI` (optional but required for `/currconv`): ExchangeRate API key
- `OWNER_USER_ID` (optional, default set in code): owner-only access for `/admes_tunnel`

## Run

```bash
pip install -r requirements.txt
python -m bot.main
```

## Commands

### Utility Commands

- `/ping`
- `/hello`
- `/datetime`
- `/help [category]`
- `/replies`
- `/botinfo`
- `/userinfo [user]`
- `/serverinfo`
- `/admes <query>`
- `/admes_tunnel [url]` (owner only)
- `/makefile <filename> <content>`
- `/calculate <expression>`
- `/reply <text> <reply>`
- `/noreply <text>`
- `/dm <user> <message>`
- `/rps [choice]`
- `/tti <text>`
- `/setting <type> <value>`
- `/currconv <amount> <from_currency> <to_currency>`
- `/makecolor <red> <green> <blue>`
- `/randomcolor`

### Economy Commands

- `/balance [user]`
- `/daily`
- `/weekly`
- `/monthly`
- `/work`
- `/rob <user>`
- `/give <user> <amount>`
- `/leaderboard`
- `/globalleaderboard`
- `/inventory`
- `/shop [item]`
- `/buy <item>`
- `/use <item>`

### Moderation Commands

- `/kick <user> [reason]`
- `/ban <user> [reason]`
- `/unban <user>`
- `/mute <user>`
- `/unmute <user>`
- `/warn <user> <cause>`
- `/clearwarns <user>`
- `/getwarns <user>`
- `/clear <amount>`
- `/nuke`

## Shop Items (Current)

- Juice
- Nitro
- Hacker Code
- Hacker Laptop
- Pet Cat
- Premium Pass
- Magna Diamond

Notes:

- `Nitro` reduces active work and daily cooldown timers.
- `Hacker Laptop` opens an interactive flow; running Hacker Code can reward or cost coins based on modal answer.

## MongoDB Notes

The project currently uses:

- database: `UnknownDatabase`
- collection: `UnknownCollection`

Documents are keyed by `name` (e.g., `balance`, `warn`, `item`, `reply`, `usersettings`, cooldown datasets).

## Project Structure

```text
maxis/
├── bot/
│   ├── main.py
│   ├── slash_commands.py
│   ├── helper.py
│   ├── components.py
│   ├── modals.py
│   ├── web_server.py
│   ├── admes_server.py
│   ├── commands/
│   │   ├── basic_commands.py
│   │   ├── currency_commands.py
│   │   └── mod_commands.py
│   └── objects/
│       ├── shop.py
│       ├── nitro.py
│       ├── hacker_laptop.py
│       ├── user_settings.py
│       └── warn.py
├── resources/
│   ├── commands.json
│   ├── currencies.json
│   ├── index.html
│   └── public/
└── requirements.txt
```

## License

MIT. See `LICENSE`.
