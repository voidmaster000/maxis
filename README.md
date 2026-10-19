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

- Help system with a category selector, top-level `/help`
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

.\venv\Scripts\python.exe -m ruff check    # lint
.\venv\Scripts\python.exe -m ruff format  # format (same config, one tool)
.\venv\Scripts\python.exe -m pyright       # type check
.\venv\Scripts\python.exe -m pytest        # tests
.\venv\Scripts\python.exe -m pytest --cov=bot --cov-report=term-missing
```

`pyproject.toml` points `pyright` and `ruff` at `./venv`, so both resolve the
same discord.py the bot actually runs against rather than any other install on
the machine. `requirements.txt` is pinned to the versions in `./venv`;
`requirements-dev.txt` pins the tools above. Ruff lints and formats, so the
formatting and the import order come out of one config and cannot disagree.

The tests run offline. Nothing touches Discord or MongoDB: commands are driven
through the stand-ins in `tests/conftest.py`, and the database layer is given a
fake collection. Each test starts from the bot's start-up state and leaves
nothing queued behind, so the suite passes in any order.

## Requirements

- Python 3.13+
- MongoDB instance
- Discord bot token

Install dependencies:

```bash
pip install -r requirements.txt
```

`tzdata` is in there because `zoneinfo` depends on the host for its time zone
database. A host with a system copy (most Linux images) never uses the package;
one without (Windows, slim containers) cannot run `/utility datetime` or fill
the timezone autocomplete without it.

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
[Command layout](#command-layout) for why. `/help` is the one exception — it is
top-level, because it documents the categories rather than being one.

- `/help [category]` — the category index, or one category's commands

### `/utility`

- `/utility ping`
- `/utility hello`
- `/utility datetime [timezone]`
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
│   ├── main.py               # wiring, the Discord events, the FastAPI status page
│   ├── core/
│   │   ├── global_state.py           # every tuning constant + all mutable runtime state
│   │   ├── database_sync.py          # syncs global_state to MongoDB
│   │   ├── transactions.py           # credit / debit
│   │   └── helper.py                 # pure shared helpers + /help rendering
│   ├── commands/
│   │   ├── utility_commands.py       # /utility
│   │   ├── economy_commands.py       # /economy
│   │   ├── moderation_commands.py    # /moderation
│   │   ├── image_commands.py         # /image
│   │   └── help_command.py           # /help (top level, not a category)
│   ├── listeners/
│   │   ├── components_listener.py    # button and select menu clicks
│   │   └── modals_listener.py        # modal submissions
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
│   ├── index.html
│   ├── Inter-SemiBold.ttf
│   └── public/
├── tests/
│   ├── conftest.py            # stand-ins for Discord + per-test state isolation
│   ├── test_database_sync.py  # the writer, its retries, and the loader
│   ├── test_command_tree.py   # command layout, install flags, /help
│   ├── test_objects.py        # games, calculator, laptop, nitro, image swatch
│   ├── test_startup.py        # what on_ready may block on, and when
│   ├── test_events.py         # on_message, on_interaction, the status page
│   ├── test_components_listener.py  # buttons, the help dropdown, the dispatcher
│   ├── test_modals_listener.py      # the hacker laptop modal
│   ├── test_economy.py        # money conservation and cooldowns
│   ├── test_moderation.py     # the moderator gate and every action
│   ├── test_utility.py        # argument handling, custom replies, currconv
│   ├── test_transactions.py   # credit / debit, including the failure paths
│   ├── test_image.py          # colour validation and the files sent back
│   └── test_helper.py         # random ranges and the currency list's limits
├── requirements.txt
├── requirements-dev.txt
└── pyproject.toml          # pyright + ruff + pytest configuration
```

### Data flow

`global_state` is the single source of truth for both configuration and data:

- **Constants** — env config, paths, cooldowns, DB names, tuning values, the
  word lists (`WORKS`) and the currencies `/utility currconv` accepts
  (`CURRENCY_CODES`). Nothing else reads an environment variable or defines a
  module-level constant, apart from `COGS` in `main.py` and the discord
  `Choice` objects built for a command's own decorator.
- **Runtime data** — the mutable collections the cogs share. `database_sync`
  loads it at startup and is the only module that talks to MongoDB, so cogs
  read `global_state`, mutate it, and call a `database_sync.save_*()`.
  Balance changes go through `credit` / `debit` in `transactions.py`.

The currency list is a constant rather than a data file on purpose. Discord
allows at most 25 choices on one command option, so the set has to be curated
either way, and only the codes are used — the names that a package like
`pycountry` or `babel` would supply are never displayed.

Saves are queued to one writer thread, which retries a failing document a few
times and logs an error rather than dropping it if it keeps failing.

### Logging

Every module asks for `logging.getLogger(__name__)` and never configures a
handler. `main.setup_logging()` runs once from the `__main__` block and decides
the format, so a deploy gets timestamps, levels and module names on one stream
instead of a wall of `print`. It is a function rather than a statement at import
so that importing `main` — which the tests do — never reconfigures the host's
logging.

### Command layout

Each category is a `commands.GroupCog`, which registers as an `app_commands.Group`
on the tree. Commands are therefore invoked as `/<category> <command>`
(e.g. `/utility ping`, `/economy daily`, `/moderation ban`, `/image makecolor`).

Because the grouping is done by discord.py itself, `/help` has no hand-maintained
command list: `help_groups()` / `help_category_embed()` in `helper.py` read the
registered groups straight off the command tree. Category order is whatever
discord.py registered, and there is no second list that can drift.

`/help` itself is deliberately *not* a `GroupCog`. A group is never invocable on
its own, so a group named `help` could only ever be reached as `/help help`, and
`/help` has to be usable with no category typed. It is registered as a plain
top-level command instead, which keeps `help_groups()` returning exactly the
categories.

## License

MIT. See `LICENSE`.
