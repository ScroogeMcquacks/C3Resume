# c3resume: save a Cossacks 3 multiplayer match and finish it another day

**[Deutsche Anleitung: LIESMICH.md](LIESMICH.md)**

Cossacks 3 cannot save a multiplayer match. If a match runs long, you usually have to give up or play until the
end. c3resume adds the missing piece. Any player types `!save`, or presses a button in the F10 menu. Another day,
the same players start a new match, type `!load 1`, and continue where they stopped: same map, same armies, same
nations, and the chat still works.

It's an unofficial fan project for groups of friends who play on their **own lobby server**. It doesn't work on
the official server.

---

## Contents

1. [How it works, in short](#1-how-it-works-in-short)
2. [What you need](#2-what-you-need)
3. [Download](#3-download)
4. [Set up the server (one person)](#4-set-up-the-server-one-person)
5. [Install on every player's PC](#5-install-on-every-players-pc)
6. [The save helper: install it or not?](#6-the-save-helper-install-it-or-not)
7. [Playing: saving and continuing](#7-playing-saving-and-continuing)
8. [Without the save helper: copying a save by hand](#8-without-the-save-helper-copying-a-save-by-hand)
9. [When something goes wrong](#9-when-something-goes-wrong)
10. [Updating and uninstalling](#10-updating-and-uninstalling)
11. [Is it safe?](#11-is-it-safe)
12. [For developers](#12-for-developers)
13. [License and credits](#13-license-and-credits)

---

## 1. How it works, in short

There are three pieces:

- **The server.** One person in your group runs a small lobby server on a Linux PC. Everybody's game connects to
  it instead of the official one. It understands the chat commands `!save`, `!autosave`, `!saves` and `!load`, and
  it keeps a copy of every save.
- **The installer.** Every player runs it once. It changes a few of the game's script files on that PC so the
  game can load a save in the middle of a multiplayer match. It also points the game at your server.
- **The save helper** (optional, recommended). This small background program sends the host's saves to the server
  and fetches them for everybody else when a match is loaded. Without it, you copy save files by hand (see
  [section 8](#8-without-the-save-helper-copying-a-save-by-hand)).

When a match is saved, only the **host's** game writes a save. When it's loaded, **every** PC loads that same
file, so all games start again from exactly the same state.

## 2. What you need

| Who | What |
|---|---|
| Everybody | Cossacks 3 on Steam, on Windows 10/11 or on Linux (Steam with Proton, or the native Linux version) |
| Everybody | A way to reach the server PC: the same home network, or [Tailscale](https://tailscale.com) (free, easiest), or forwarded ports |
| The person running the server | A Linux PC that is on while you play, with Python 3, Lua 5.1 and LuaSocket |
| Linux players | Python 3 (almost every Linux has it) |

The players in a match should all have the **same c3resume version** installed.

## 3. Download

Download the newest zip from the **[Releases](../../releases)** page. You can also use the green **Code** button,
then **Download ZIP**. Then **unzip it**:

- **Windows:** right-click the zip, then **Extract All...**, then **Extract**. Don't run anything from inside the
  zip; it won't work.
- **Linux:** right-click the zip, then **Extract Here**.

Inside you'll find:

```
installer-windows/   for players on Windows
installer-linux/     for players on Linux
server/              only for the person who runs the server
tools/               helpers for finding problems
```

## 4. Set up the server (one person)

Only one person in the group does this. Use a Linux PC that stays on while you play. It can be one of the players'
PCs.

1. Install the three things the server needs. On Debian, Ubuntu, Mint or Pop!_OS:

   ```
   sudo apt install python3 lua5.1 lua-socket
   ```

   On Arch, Manjaro or SteamOS: `sudo pacman -S python lua51 lua51-socket`. On other systems, install Lua **5.1**
   (not 5.3 or 5.4) and LuaSocket for Lua 5.1.
2. Open the `server` folder, right-click an empty spot, and choose **Open in Terminal**. Type:

   ```
   bash start_server.sh
   ```

   Leave this window open while you play. **Ctrl+C** stops the server. If something is missing, the script tells you
   what to install.
3. The script prints this PC's addresses. Tell your players the right one:
   - With **Tailscale**, it's the one that starts with `100.` (for example `100.90.34.72`). Every player installs
     Tailscale and joins the same network.
   - In the same home network, it's the local address (for example `192.168.1.20`).
   - Over the internet without Tailscale, forward **TCP ports 31523 and 31524** on your router to this PC and give
     out your public address.

Everything the server stores stays in `server/data/`: saves, player accounts, recordings and logs. More details
are in [server/README.md](server/README.md).

## 5. Install on every player's PC

Close Cossacks 3 first.

### Windows

1. Open the unzipped folder, then `installer-windows`.
2. Double-click **`SETUP - double-click me.bat`**.
   - If a blue window says *"Windows protected your PC"*, click **More info**, then **Run anyway**. This happens
     because the file comes from the internet and isn't signed.
   - If Windows asks *"Do you want to allow this app to make changes?"*, click **Yes**. The game's folder is
     protected when Steam is installed in "Program Files", which is the usual place.
3. The setup window opens.

### Linux

1. Open the unzipped folder, then `installer-linux`.
2. Right-click an empty spot, choose **Open in Terminal**, and type:

   ```
   bash setup-linux.sh
   ```

3. The setup window opens. If your system lacks Tk (common on Fedora and Bazzite), you get the same questions as a
   few simple dialog windows instead, and those work just as well. For the full window, install Tk:
   `sudo dnf install python3-tkinter` (Fedora) or `sudo apt install python3-tk` (Debian/Ubuntu).

### In the setup window (both systems)

- **Language / Sprache:** choose English or Deutsch at the top right. The window remembers it.
- **1. Your Cossacks 3 folder:** found automatically. Only if it says it can't find the game, click
  **Change...** and pick the folder. In Steam: right-click Cossacks 3, then **Manage**, then **Browse local
  files**.
- **2. Server address:** type the address the server person gave you, for example `100.90.34.72`.
- **3. Save helper:** leave the tick on unless you have a reason not to. See the next section.
- **4. Install.** When it says **Ready** in green, you're done.

After a game update, or after Steam's **Verify integrity of game files**, open the setup again. It will tell you to
click **Install again**.

## 6. The save helper: install it or not?

The save helper is a small program without a window. It starts with your computer and only talks to your
group's server. It does two jobs:

- When **you are the host** and the match is saved, it uploads the save to the server.
- When a match is **loaded**, it downloads that save from the server onto your PC.

**With the helper (recommended):** everything happens by itself. Type `!load 1` and the server makes sure every PC
has the save before it loads.

**Without the helper:** nothing runs in the background, but saves aren't shared by themselves. A save stays on the
host's PC. Before you can continue a match, the host has to send the save file to every player, and each player
puts it into their own saves folder. [Section 8](#8-without-the-save-helper-copying-a-save-by-hand) explains how.

You can mix both in one group. For example, the host and one friend use the helper and another friend copies by
hand. The server tells you in the chat who still needs the file.

You can change your mind any time: open the setup, set or clear the tick, and click **Install again**.

Where its log file is: Windows `%LOCALAPPDATA%\c3resume\helper.log`, Linux `~/.local/share/c3resume/helper.log`.

## 7. Playing: saving and continuing

### Buttons and commands

In a match, press **F10**. The menu has four new buttons. You can also type the matching command in the chat:

| Button | Chat command | What it does |
|---|---|---|
| Save match | `!save` | Pauses the match for everyone, the host's game saves, and the match goes on (a few seconds) |
| Autosave every 5 min on/off | `!autosave` | Saves every 5 minutes. Only the newest autosave is kept |
| List saved matches | `!saves` | Shows the saves, newest first, with a number |
| Continue newest save | `!load 1` | Loads save number 1 on every PC |

Any player can use them. The save pause doesn't count against your `!pause` limit.

### Continuing another day

1. The **same players**, with the same nicknames, meet on your server. The host opens a room. Map, nations and
   teams don't matter, because the save replaces all of it. Pick the smallest map so the match starts faster. Then
   start the match.
2. Type `!saves`. You see a list like this:

   ```
   1)  09.10. 21:30   Friday game   Aaron, Iven, Leonie
   2)  02.10. 20:15   [auto] Big map   Aaron, Iven
   ```

3. Type `!load 1`, or press F10 and **Continue newest save**. The server checks that every PC has the save
   (the helpers download it now, and a big save can take a few minutes). Then it pauses, loads the save everywhere
   and continues by itself once everyone has loaded.

Good to know:

- **One load per match.** A second load in the same match can freeze the other PCs, so the server refuses it. To
  load again, everyone leaves, the host opens a new room, starts it, and types `!load` again.
- **A typo is harmless.** `!load 7` with no save number 7 only gets you a message, and the match goes on.
- Everyone loads the **host's** file, so it doesn't matter who hosted last time or which PC anyone used.
- In `!saves`, `[auto]` marks the autosave and `[host PC]` marks a save that only the host has (no helper uploaded
  it).

## 8. Without the save helper: copying a save by hand

You only need this if the host or some players installed **without** the save helper.

**The host:**

1. After saving, open the setup and click **Open saves folder**. The save is the newest file named like
   `qladder_20261009_213012_95min.map`. The chat also shows its name when it's saved. Autosaves start with
   `qladder_auto_`.
2. Send that file to every player. Save files can be big (hundreds of MB after a long match), so zip them first:
   right-click the file, then **Compress** or **Send to > Compressed (zipped) folder**. Then share the zip through a
   cloud folder (Google Drive, OneDrive, Dropbox), LocalSend, or a USB stick. The file is usually too big for
   Discord.

**Every other player:**

1. Open the setup and click **Open saves folder**. The folder is created if you never saved before.
2. Put the file there. If you got a zip, unzip it first, so that the `.map` file itself sits in that folder.
   Don't rename it.

Then continue as in [section 7](#7-playing-saving-and-continuing). If somebody is still missing the file, the
server says who, for example *"The save ... is only on the host's PC ... These players need a copy of the file
...map in their saves folder: Iven"*, and nothing is loaded.

Where the saves folder is, if you want to find it yourself:

- **Windows:** `Documents\cossacks\profiles\<your profile>\saves`
- **Linux with Proton:** `~/.local/share/Steam/steamapps/compatdata/333420/pfx/drive_c/users/steamuser/Documents/cossacks/profiles/<your profile>/saves`
- **Linux, native version:** `~/cossacks/profiles/<your profile>/saves`

When the host plays without the helper and uses autosave, every autosave stays on the host's PC as its own file.
Delete old ones now and then.

## 9. When something goes wrong

**The setup window**

| Message | What to do |
|---|---|
| "Cossacks 3 was not found" | Click **Change...** and pick the game folder (Steam: right-click Cossacks 3 > Manage > Browse local files) |
| "a game update or Steam reset it" | Click **Install again** |
| "the save helper is NOT running" | Click **Install again**. If it stays orange, restart the PC |
| "Windows did not allow changing the game files" | Close the game; click Install again and allow the Windows question |

**Messages in the game chat**

| Message | Meaning and fix |
|---|---|
| "No save helper running on: NAME" | That PC has no helper running, so it couldn't download the save. Copy the file by hand ([section 8](#8-without-the-save-helper-copying-a-save-by-hand)), or install the helper there |
| "The save ... is only on the host's PC" | The host plays without the helper. The players named need a copy of the file |
| "These PCs could not get the save: NAME" | That player's helper is running but couldn't download the save. Check that they can reach the server (ports 31523 **and** 31524) |
| "No answer from: NAME" | That player has no c3resume, or a very old version. Install the current one |
| "Still downloading the save ..." | A big save on a slow connection. Wait; the server waits up to 10 minutes |
| "The host's save did not reach the server" | The host's helper isn't running, or a very big save is still uploading |
| "This match was already loaded once" | One load per match. Leave, open a new room, start, then `!load` |
| "Left the match during the load: NAME" | That game crashed or lost the connection while loading. Type `!unpause` to go on without them, or start again |

**Finding problems on a Windows PC:** right-click `tools/c3diag.ps1` and choose **Run with PowerShell**. After about
a minute, a report named `c3resume-diagnose.txt` appears on the desktop. Send it to the person running the server.
It contains no passwords and replaces your Windows user name with `<user>`.

**Is the game running out of memory? (Linux):** `python3 tools/c3mem.py 10` shows every 10 seconds how close
Cossacks 3 is to its 4 GB limit.

Players who share one internet connection (for example a LAN party where the server is somewhere else) look like
one player to the server. Then it can't tell who has a helper and may wait for downloads that never come. Install
the helper on all of those PCs, or none of them.

## 10. Updating and uninstalling

- **Update (players):** download and unzip the new version, open its setup and click **Update**. Everybody in your
  group should update.
- **Update (server):** stop the server with Ctrl+C, unzip the new version over the old folder (replace the files),
  and start it again. Your `server/data/` folder isn't in the zip, so saves and accounts stay.
- **Uninstall (players):** open the setup and click **Uninstall**. Every changed game file goes back to the
  original, the game uses the official server again, and the save helper is removed.

## 11. Is it safe?

- c3resume changes **a few text script files** of the game on your PC. It doesn't touch the program
  (`cossacks.exe`). Before it changes anything, it keeps the original in the `c3backup` folder inside the game
  folder, and Uninstall puts it back exactly.
- The save helper only talks to the server address you typed in, and it only moves save files named `qladder_...`.
- Nothing reads your passwords or Steam account.
- No files from the game are included in this project. Everything is changed on your own PC, in your own copy of the
  game.
- It's an unofficial fan project. Use it at your own risk. It's been played a lot, but it can't fix crashes of
  the game itself.

## 12. For developers

```
installer-linux/c3resume.py     the installer, the patches to the game scripts, and the save helper (Linux)
installer-linux/c3resume_gui.py the Tk setup window; c3resume_dialogs.py: zenity / kdialog / terminal version
installer-linux/c3resume_ui.py  what both share; texts.json: all setup texts in English and German
installer-windows/c3resume.ps1  the same installer and helper for Windows; c3resume-gui.ps1: its window
installer-windows/patches.json  generated: python3 installer-linux/c3resume.py export installer-windows/patches.json
server/sich_c3.lua              the lobby server (Sich / qossacks_4 with c3resume's commands)
server/c3saves_server.py        the save service (HTTP, port 31524)
dev/check.py                    consistency checks; dev/make_release.py builds dist/c3resume-<version>.zip
dev/sim/sim.py                  a whole match without the game: real server, real helpers, three simulated games
docs/how-it-works.md            the technical side: patches, chat protocol, load sequence
```

Before a commit, run `python3 dev/check.py`. To try a change without the game, run for example
`python3 dev/sim/sim.py --helpers on,off,on -- '!save' '!saves' '!load 1'`.
To make a release, update the version in `c3resume.py`, `c3resume.ps1`, `sich_c3.lua` and `CHANGELOG.md`, then
push a tag like `v2.2`. GitHub builds the zip and publishes the release.

## 13. License and credits

c3resume is under the **MIT license** (see [LICENSE](LICENSE)).

The lobby server is based on **[Sich](https://github.com/3skcassoc/sich)** by 3skcassoc and its fork
**[qossacks_4](https://github.com/kewl-ua/qossacks_4)** by kewl-ua, both under the WTFPL. The lobby protocol
documentation in **[cossacks_3_net_spec](https://github.com/kewl-ua/cossacks_3_net_spec)** was a great help.
Everything about third-party code, and what is *not* included, is in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Cossacks 3 is a game by GSC Game World. This project isn't affiliated with or endorsed by GSC Game World.
