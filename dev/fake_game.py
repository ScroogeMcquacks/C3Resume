#!/usr/bin/env python3
"""Make a stand-in "Cossacks 3" folder for testing the installers without the game: every game file c3resume
changes, containing just the lines it looks for (taken from the installer's own patch data), with the game's CRLF
line ends. Also a Proton-style profile folder next to it, like Steam has.

  python3 dev/fake_game.py <folder>        -> <folder>/steamapps/common/Cossacks 3  (prints that path)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    base = Path(sys.argv[1]).resolve()
    game = base / "steamapps" / "common" / "Cossacks 3"
    data = json.loads((ROOT / "installer-windows" / "patches.json").read_text())
    files = {}
    for p in data["normal"]["patches"]:
        files.setdefault(p["file"], []).append(p["anchor"])
    for rel, anchors in files.items():
        f = game / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        body = "// stand-in for a game file\n" + "\n// ...\n".join(anchors) + "\n// end\n"
        f.write_bytes(body.replace("\n", "\r\n").encode("latin-1"))
    sd = game / "data" / "resources" / "servers.dat"
    sd.parent.mkdir(parents=True, exist_ok=True)
    sd.write_bytes(b"section.begin\r\n* = 138.201.198.174:31523\r\nsection.end\r\n")
    (game / "mods").mkdir(exist_ok=True)
    prof = base / "steamapps" / "compatdata" / "333420" / "pfx" / "drive_c" / "users" / "steamuser" / "Documents" / "cossacks" / "profiles" / "Player"
    prof.mkdir(parents=True, exist_ok=True)
    print(game)


if __name__ == "__main__":
    main()
