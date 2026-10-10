<p align="center">
  <img src="resources/public/favicon.png" alt="Maxis Logo" width="200"/>
</p>

# Maxis - Discord Bot

[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/downloads/)
[![discord.py](https://img.shields.io/badge/discord.py-2.7-blue.svg)](https://github.com/Rapptz/discord.py)
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
- Color generation tools (`/image makecolor`, `/image randomcolor`)
- Rock-Paper-Scissors (choice or interactive buttons)

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

### Web

- FastAPI web server (`/`) showing online status + invite button

## Development

```bash
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt

.\venv\Scripts\python.exe -m ruff check   # lint (config in pyproject.toml)
.\venv\Scripts\python.exe -m pyright       # type check
```

`pyproject.toml` points `pyright` and `ruff` at `./venv`, so both resolve the
same discord.py the bot actually runs against rather than any other install on
the machine. `requirements.txt` is pinned to the versions in `./venv`;
`requirements-dev.txt` pins the two tools above.

## Requirements

- Python 3.13+
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
```

### Environment Variables

- `TOKEN` (required): Discord bot token
- `CONNSTR` (required): MongoDB connection string
- `PORT` (optional, default `8080`): FastAPI web server port
- `EXAPI` (optional but required for `/currconv`): ExchangeRate API key

## Run

```bash
pip install -r requirements.txt
python -m bot.main
```

## Commands

Every command is invoked as `/<category> <command>`; see
[Command layout](#command-layout) for why.

### `/utility`

- `/utility ping`
- `/utility hello`
- `/utility datetime [timezone]`
- `/utility help [category]`
- `/utility replies`
- `/utility botinfo`
- `/utility userinfo [user]`
- `/utility serverinfo`
- `/utility makefile <filename> <content>`
- `/utility calculate <expression>`
- `/utility reply <text> <reply>`
- `/utility noreply <text>`
- `/utility dm <user> <message>`
- `/utility rps [choice]`
- `/utility setting <type> <value>`
- `/utility currconv <amount> <from_currency> <to_currency>`
- `/utility ttt`

### `/moderation`

- `/moderation kick <user> [reason]`
- `/moderation ban <user> [reason]`
- `/moderation unban <user>`
- `/moderation mute <user>`
- `/moderation unmute <user>`
- `/moderation warn <user> <cause>`
- `/moderation clearwarns <user>`
- `/moderation getwarns <user>`
- `/moderation clear <amount>`
- `/moderation nuke`

### `/economy`

- `/economy balance [user]`
- `/economy daily`
- `/economy weekly`
- `/economy monthly`
- `/economy work`
- `/economy rob <user>`
- `/economy give <user> <amount>`
- `/economy leaderboard`
- `/economy globalleaderboard`
- `/economy inventory`
- `/economy shop [item]`
- `/economy buy <item>`
- `/economy use <item>`

### `/image`

- `/image tti <text>`
- `/image makecolor <red> <green> <blue>`
- `/image randomcolor`

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
│   ├── main.py               # wiring + the FastAPI status page
│   ├── global_state.py       # every constant + all mutable runtime state
│   ├── database_sync.py      # syncs global_state to MongoDB
│   ├── slash_commands.py     # registers the cogs
│   ├── transactions.py       # credit / debit
│   ├── helper.py             # pure shared helpers + /help rendering
│   ├── components_listener.py
│   ├── modals_listener.py
│   ├── commands/
│   │   ├── utility_commands.py       # /utility (and /help)
│   │   ├── economy_commands.py       # /economy
│   │   ├── moderation_commands.py    # /moderation
│   │   └── image_commands.py         # /image
│   └── objects/
│       ├── shop.py             # the catalogue and its lookups
│       ├── hacker_laptop.py    # the laptop item and its command history
│       ├── nitro.py            # the nitro cooldown boost
│       ├── tictactoe.py        # the /utility ttt game
│       ├── rps.py              # the /utility rps game
│       ├── calculator.py       # the /utility calculate evaluator
│       ├── user_settings.py
│       └── warn.py
├── resources/
│   ├── currencies.json
│   ├── index.html
│   ├── Inter-SemiBold.ttf
│   └── public/
├── requirements.txt
├── requirements-dev.txt
└── pyproject.toml          # pyright + ruff configuration
```

### Data flow

`global_state` is the single source of truth for both configuration and data:

- **Constants** — env config, paths, cooldowns, DB names, tuning values and the
  reference data (`WORKS`, `CURRENCIES`). Nothing else reads an environment
  variable or defines a module-level constant, apart from `COGS` in
  `slash_commands.py` and the discord `Choice` objects built for a command's own
  decorator.
- **Runtime data** — the mutable collections the cogs share. `database_sync`
  loads it at startup and is the only module that talks to MongoDB, so cogs
  read `global_state`, mutate it, and call a `database_sync.save_*()`.
  Balance changes go through `credit` / `debit` in `transactions.py`.

### Command layout

Each category is a `commands.GroupCog`, which registers as an `app_commands.Group`
on the tree. Commands are therefore invoked as `/<category> <command>`
(e.g. `/utility ping`, `/economy daily`, `/moderation ban`, `/image makecolor`).

Because the grouping is done by discord.py itself, `/help` has no hand-maintained
command list: `help_groups()` / `help_category_embed()` in `helper.py` read the
registered groups straight off the command tree. Category order is whatever
discord.py registered, and there is no second list that can drift.

## License

MIT. See `LICENSE`.
