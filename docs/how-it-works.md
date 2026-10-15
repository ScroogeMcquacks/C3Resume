# How c3resume works

This is the technical side, for people who want to change or check the code. How to use it is in the
[README](../README.md).

## The problem

Cossacks 3 (build 2.2.3, a 32-bit Windows program that also runs natively on Linux or through Proton) has a save
format and a load function for single player, but in multiplayer the save and load buttons are switched off. A
running match is a lockstep simulation: every PC runs the same game from the same commands. Saving means writing
that state to a file, and resuming means every PC loading the same file at the same moment and carrying on in
lockstep.

## The pieces

```
 player PCs                                           the server PC
 +-----------------------------+                      +-----------------------------------+
 | Cossacks 3                  |  TCP 31523 (lobby)   | sich_c3.lua   lobby + !commands   |
 |  + patched script files ----+--------------------->|   writes meta.txt, wanted.txt     |
 |                             |                      |   reads index.txt, helpers.txt    |
 | save helper (optional) -----+--------------------->| c3saves_server.py  HTTP, saves/   |
 |  c3resume.py / c3resume.ps1 |  TCP 31524 (HTTP)    |                                   |
 +-----------------------------+                      +-----------------------------------+
```

## The patches to the game scripts

The game's logic lives in plain-text script files (`data/gui/*.inc`, `data/scripts/**`), lines like
`[*] = ;if (...) then`, with CRLF line ends. The installers find each place by an **anchor**, a short original
line that must occur exactly once, and replace it with the anchor plus c3resume's code. If an anchor isn't found
exactly once, nothing is changed. Every changed file is backed up first to `<game>/c3backup/` and recorded in
`c3backup/manifest.json` with checksums of the original and the patched file. Uninstall copies the backups back.

The patch list is in `patch_list()` in `installer-linux/c3resume.py`. `installer-windows/patches.json` is the same
data exported for the Windows installer: `python3 installer-linux/c3resume.py export installer-windows/patches.json`.

| Patch | File | What it does |
|---|---|---|
| readload | `data/gui/menu.aix` (+ new `readload.inc`) | A new GUI state `ReadLoad` right after `ReadSave`, so it gets section number 71. When the server sends a record for section 71 with a save's name, the game checks that it has that save and marks it for loading |
| deferload | `doprogress.inc` | Runs the load one frame later, outside the network command handling (loading inside it crashed or hung). 3 seconds after the load it reports `#c3loaded <name> ok` (or `missing`) |
| onlineload | `onloadfull.inc` | After loading in an online match: sets the control modes of the players again and maps them by nickname to the new session's player ids |
| session | `docreate.inc` | Puts the lobby event handler back after the load |
| check | `onlaneventsession.inc` | Answers the server's hidden chat question `#c3check <id> name;` with `#c3have <id> <bits> <version>` |
| unloadoffline | `net.script`, `onload.inc`, `onloadfull.inc` | Keeps the game in "online" mode while the old map is unloaded, so it doesn't drop out of the match |
| menu | `showmenu.inc`, `eventmenu.inc` | The four F10 buttons, which send `!save`, `!autosave`, `!saves`, `!load 1` |
| globals | `dmscript.global` | The few global variables the code above uses |

## The lobby server

`server/sich_c3.lua` is Sich v0.2.9 as extended by qossacks_4 (see THIRD_PARTY_NOTICES.md). It forwards the
matches' traffic and handles chat lines that start with `!`. The game sends "GUI records" through the lobby, and the
server can send them too:

- section **66** (ReadPause), the pause the game's own pause key sends
- section **70** (ReadSave): *save the match under this name*. The game had this for its own online saves, which
  were switched off
- section **71** (ReadLoad, added by the patch): *load this save*

The host only accepts such a record from another player, so the server sends it in another player's name
(`record_sender`). That's why a host alone in a match can't save.

### !save

1. Pause the match (a pause record, not counted against the players' pauses).
2. Send ReadSave with a name `qladder_<date>_<time>_<minutes>min` to the **host only**.
3. Ask the host with `#c3check` until its game reports the file (up to 90 s), then unpause.
4. Write the name, room and players to `saves/meta.txt`. If the host runs a save helper, wait for the upload (up to
   5 minutes) and say "safe on the server". Otherwise say at once that the save is only on the host's PC.

`!autosave` does the same every 5 minutes (`autosave_seconds`), with names `qladder_auto_...`. The save service and
the helpers keep only the newest autosave.

### !saves and !load

`!saves` lists the uploaded saves (`saves/index.txt`) and the ones in `meta.txt` that no helper uploaded
(`[host PC]`; of those autosaves only the newest). `!load <number or name>` then:

1. Marks the save as *wanted* in `saves/wanted.txt`. The helpers see the flag in the list and download it.
2. Asks every game with `#c3check` every few seconds which of them has the file. It waits while players who run a
   helper are still downloading (up to 10 minutes; the chat says who every 30 s). It stops waiting at once for
   players without a helper.
3. If anyone is missing the file or doesn't answer, it says who and loads nothing. The match isn't paused for a typo
   or a missing file.
4. Otherwise: pause, send ReadLoad to everyone, wait for `#c3loaded` from everyone (up to 10 minutes), then for an
   answer to `#c3check` from everyone, which shows they really run again. Then "everyone has loaded" and unpause.

Only one load per match: a second load in the same match leaves the other PCs in an endless loading screen. The
cause is somewhere in the engine and hasn't been found, so the server refuses it.

### Who has a save helper

`c3saves_server.py` writes the address of every client that asks for `/c3/list` to `saves/helpers.txt` (address,
time). A player whose lobby connection comes from an address that hasn't asked in the last 2 minutes has no helper.
The file is emptied when the service starts. Players behind one shared address can't be told apart.

## The save service

`server/c3saves_server.py`, Python standard library only:

| Request | Meaning |
|---|---|
| `GET /c3/list` | One line per save: `name <TAB> bytes <TAB> unix time <TAB> 1 if a !load wants it now` |
| `GET /c3/file/<name>` | The gzip-packed save, streamed |
| `PUT /c3/file/<name>` | Store a save. The first upload of a name wins. It must unpack to a Cossacks 3 save (`OSWMap`), at most 2 GB packed / 4 GB unpacked |

Only names like `qladder_YYYYMMDD_HHMMSS_<n>min` and `qladder_auto_...` are accepted.

## The save helper

`c3resume.py helper` (Linux: a systemd user service, or the desktop's autostart) and `c3resume.ps1 helper`
(Windows: a hidden PowerShell started from the Startup folder, one at a time through a named mutex). Every 5 seconds
(slower while the service can't be reached):

- upload new `qladder_*.map` files from the profiles' `saves` folders once their size stopped changing, packed
  piece by piece (a failed upload is tried again after 2 minutes)
- download every save the list marks as wanted and that isn't there yet (via a temporary file, then renamed)
- delete local autosaves that a newer one replaced, unless a load wants them right now

## Testing without the game

`dev/sim/sim.py` starts the real server and save service in a temporary folder, the real helpers (and the Windows
helper under PowerShell 7 when `pwsh` is there), and three simulated games that join a match and answer the
server like the patched game does. `dev/check.py` checks versions, generated files, texts and syntax, and installs
and uninstalls on a stand-in game folder made by `dev/fake_game.py`. GitHub runs both on every push
(`.github/workflows/check.yml`).
