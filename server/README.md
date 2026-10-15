# The c3resume server

**[Deutsch: LIESMICH.md](LIESMICH.md)**

Only the one person who runs your group's lobby does this. The players don't need this folder.

## Start

```
bash start_server.sh
```

Leave the terminal open while you play. **Ctrl+C** stops the server. There's no separate setup. The script starts
two programs together:

| Program | Port | What it does |
|---|---|---|
| the lobby server (`sich_c3.lua`) | TCP 31523 | Rooms, chat and matches, plus the commands `!save`, `!autosave`, `!saves`, `!load` |
| the save service (`c3saves_server.py`) | TCP 31524 | Keeps the host's saves. The players' save helpers upload and download them here |

Every player must reach **both ports** on this computer. With Tailscale or another VPN that works by itself. Behind
a home router, forward both ports to this PC. The script prints this computer's addresses; the players type one of
them into their setup window.

It needs **Lua 5.1 with LuaSocket** and **python3**. If something is missing, the script names the install command
(Debian/Ubuntu/Mint: `sudo apt install lua5.1 lua-socket`; Arch/SteamOS: `sudo pacman -S lua51 lua51-socket`).

## Where the files are

Everything stays in this folder, in `data/`, which is created at the first start:

```
data/saves/          the saves (you can delete old ones here)
data/register.store  the players' lobby accounts
data/recordings/     a recording of every match
data/server.log      the lobby's log
data/saves.log       the save service's log
data/config.store    settings (see below)
```

Nothing is installed anywhere else.

## Settings

`data/config.store` is created at the first start. To save every 10 minutes instead of every 5, add
`autosave_seconds = 600,` inside `commands = { ... }`:

```
commands = { bot = { nick = "C3Lab" }, saves_dir = "saves", autosave_seconds = 600 },
```

`bot.nick` is the name of the "player" that answers commands in the chat. Restart the server after a change.

## Update

Stop the server, unzip the new version **over** this folder (replace the files), and start it again. The `data/`
folder isn't in the zip, so your saves and accounts stay. You can also unzip somewhere new and move `data/` into
the new `server` folder.

## How the server knows who has a save helper

Every save helper asks the save service for its list every 5 seconds. The service writes the addresses it saw to
`data/saves/helpers.txt`. If a player's address hasn't asked in the last 2 minutes, the server treats that player
as having no helper. It doesn't wait for a download from that PC and says in the chat that the save must be copied
by hand. Players who share one internet address look like one player here.
