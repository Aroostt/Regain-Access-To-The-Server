# Regain-Access-To-The-Server

A centered, white/gray styled CMD CLI tool that:

- reads Discord bot tokens from `tokens.txt`,
- checks which tokens are valid,
- lets you choose a token by number,
- shows a clean boxed actions menu.

## Requirements

- Python 3.10+
- `requests`

Install:

```bash
pip install requests
```

## Run

1. Put token(s) into `tokens.txt` (1 token per line).
2. Start:

```bash
python discord_tool.py
```

## Features

After selecting a valid token:

1. **Back** – return to token list.
2. **Copy server invite link** – creates and copies a server invite from a selected guild.
3. **Copy bot invite link** – creates and copies bot OAuth invite link.
4. **Grant admin role** – creates an admin role, tries to move it as high as possible, assigns it to user ID.
5. **Grant best existing role** – assigns the highest existing role the bot can legally grant in hierarchy.

> Note: The bot must have proper permissions on the guild (create invites, manage roles, assign roles).
