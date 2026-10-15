# Third-party notices

c3resume's own code is under the MIT license (see `LICENSE`). This file lists everything in this repository
that comes from someone else, and everything c3resume needs but does **not** include.

## Included in this repository

### Sich and qossacks_4 (the lobby server) — WTFPL

`server/sich_c3.lua` is a modified copy of the Cossacks 3 lobby server **qossacks_4 0.1**, which is a fork of
**Sich v0.2.9**. c3resume added the save and load features (`!save`, `!autosave`, `!saves`, `!load`) and a few
fixes on top.

| Project | Author | Source | License |
|---|---|---|---|
| Sich v0.2.9 | 3skcassoc | <https://github.com/3skcassoc/sich> | WTFPL, version 2 |
| qossacks_4 0.1 | kewl-ua | <https://github.com/kewl-ua/qossacks_4> | WTFPL, version 2 |

The WTFPL lets anyone copy, change and pass on the code without conditions. Its full text is in
`LICENSES/WTFPL.txt`. Our changes to `server/sich_c3.lua` are also available under the MIT license (`LICENSE`);
the parts that come from Sich and qossacks_4 stay under the WTFPL.

### Short lines from the game's own scripts (patch anchors)

To change the game on a player's computer, the installers search the game's script files for a few short,
existing lines and insert c3resume's code next to them. Those search lines (about 930 characters in total,
mostly single lines such as `[*] = ;if (gScenario.bexists) then`) are stored in `installer-linux/c3resume.py`
and `installer-windows/patches.json`. They are needed only to find the right place in the player's own copy of the
game (interoperability). **No game file, game script, map, save or other asset of Cossacks 3 is included or
distributed.** All game files are changed only on the player's computer, a backup of every original is kept in
`<game folder>/c3backup`, and Uninstall puts the originals back.

## Used as documentation only (no code included)

| Project | What we used | License |
|---|---|---|
| cossacks_3_net_spec by kewl-ua, <https://github.com/kewl-ua/cossacks_3_net_spec> | Description of the lobby protocol; the test tools in `dev/sim/` were written from it and from the Sich source | MIT |

## Needed, but not included

These programs are installed separately by the people who use c3resume. They are not part of this repository and
not part of a c3resume download.

| What | Who needs it | License |
|---|---|---|
| Lua 5.1 (<https://www.lua.org>) | the server | MIT |
| LuaSocket (<https://github.com/lunarmodules/luasocket>) | the server | MIT |
| Python 3 (<https://www.python.org>) | the server and Linux players | PSF License |
| Tk / tkinter (optional) | Linux players, for the setup window | Tcl/Tk license (BSD-style) |
| zenity or kdialog (optional) | Linux players without Tk | LGPL / GPL (only started as separate programs) |
| Windows PowerShell 5.1 | Windows players | part of Windows |

## Trademarks

"Cossacks" and "GSC Game World" are trademarks of their respective owners. c3resume is an unofficial fan project:
it is not made, endorsed or supported by GSC Game World. You need your own copy of Cossacks 3 to use it.
