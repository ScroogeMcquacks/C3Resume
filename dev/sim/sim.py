#!/usr/bin/env python3
"""
sim.py - test c3resume end to end WITHOUT the game: the real lobby server (server/sich_c3.lua) and save service
(server/c3saves_server.py), the real save helpers (installer-linux/c3resume.py, and installer-windows/c3resume.ps1
under PowerShell 7 when `pwsh` is there), and three simulated games (HOST, P1, P2) that join one match.

The simulated games answer the server's hidden questions (#c3check) from the files that really are in their saves
folders, "save" when the server tells the host to (they write a stand-in save file), and "load" when told to.

  python3 dev/sim/sim.py [options] -- <what P1 types, one argument each> ...

  options:  --helpers on,off,on      which of HOST,P1,P2 run the save helper (default: all on)
            --ips 127.0.0.1,127.0.0.12,127.0.0.13
                                     the address each machine uses (default: all 127.0.0.1). Different addresses
                                     let the server tell who runs a helper; on Linux, as root:
                                       ip addr add 127.0.0.12/32 dev lo
                                       ip route replace local 127.0.0.12 dev lo table local scope host src 127.0.0.12
            --save-mb 5              size of the stand-in save
            --port 31598             lobby port (the save service always uses 31524, like the helpers expect)

  special "commands":  wait <seconds>         let time pass
                       copy <P1|P2>           copy the host's newest save into that player's saves folder by hand
  example:  python3 dev/sim/sim.py --helpers on,off,on -- '!save' '!saves' '!load 1'

Requires: lua5.1 with LuaSocket, python3. Standard library only. Everything happens in a temporary folder.
"""
import argparse
import glob
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
from c3fake import Fake, s8, u32   # noqa: E402

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--helpers", default="on,on,on")
ap.add_argument("--ips", default="127.0.0.1,127.0.0.1,127.0.0.1")
ap.add_argument("--save-mb", type=int, default=5)
ap.add_argument("--port", type=int, default=31598)
ap.add_argument("--keep", action="store_true", help="keep the temporary folder")
ap.add_argument("commands", nargs="*")
A = ap.parse_args()
NAMES = ("HOST", "P1", "P2")
HELPERS = dict(zip(NAMES, [h.strip() == "on" for h in A.helpers.split(",")]))
IPS = dict(zip(NAMES, [i.strip() for i in A.ips.split(",")]))
PWSH = shutil.which("pwsh")
W = Path(tempfile.mkdtemp(prefix="c3sim-"))
procs = []


def start_servers():
    srv = W / "server"
    (srv / "saves").mkdir(parents=True)
    shutil.copy(str(ROOT / "server" / "sich_c3.lua"), str(srv / "sich.lua"))
    (srv / "config.store").write_text(
        'io.stdout:setvbuf("line")\nreturn { host = "*", port = %d, log = { level = "info", output = io.output() },\n'
        '  commands = { bot = { nick = "C3Lab" }, saves_dir = "saves", autosave_seconds = 60 } }\n' % A.port)
    lua = open(str(srv / "server.log"), "w")
    procs.append(subprocess.Popen(["lua5.1", "sich.lua"], cwd=str(srv), stdout=lua, stderr=subprocess.STDOUT))
    files = open(str(srv / "saves.log"), "w")
    procs.append(subprocess.Popen([sys.executable, str(ROOT / "server" / "c3saves_server.py"), "--dir", str(srv / "saves"),
                                   "--port", "31524"], stdout=files, stderr=subprocess.STDOUT))
    time.sleep(1.5)


def make_machine(name, windows):
    root = W / name
    game = root / "game"
    (game / "data" / "resources").mkdir(parents=True)
    (game / "data" / "resources" / "servers.dat").write_bytes(
        b"section.begin\r\n* = %s:%d\r\nsection.end\r\n" % (IPS[name].encode(), A.port))
    docs = root / ("Documents" if windows else "home")
    profile = {"HOST": "Host", "P1": "P1", "P2": "Friend"}[name]
    (docs / "cossacks" / "profiles" / profile).mkdir(parents=True)        # a profile that never saved
    env = dict(os.environ, HOME=str(root / "home"), C3RESUME_HOME=str(root / "helper"))
    if windows:
        env["C3RESUME_DOCS"] = str(docs)
        cmd = [PWSH, "-NoProfile", "-File", str(ROOT / "installer-windows" / "c3resume.ps1"), "helper", "-GameDir", str(game)]
    else:
        cmd = [sys.executable, "-I", str(ROOT / "installer-linux" / "c3resume.py"), "helper", "--game-dir", str(game)]
    Path(env["C3RESUME_HOME"]).mkdir(parents=True)
    return {"docs": docs, "profile": profile, "env": env, "cmd": cmd, "root": root}


class Game(Fake):
    def __init__(self, name, m, host=False):
        super().__init__(name, IPS[name], A.port, source=IPS[name])
        self.m, self.is_host = m, host

    def saves(self):
        return self.m["docs"] / "cossacks" / "profiles" / self.m["profile"] / "saves"

    def has(self, save):
        return bool(glob.glob(str(self.m["docs"] / "cossacks" / "profiles" / "*" / "saves" / (save + ".map"))))

    def react(self):
        self.pump(0.2)
        for code, a, b, p in self.take():
            if code in (0x0194, 0x0195, 0x0196, 0x0197) and p:
                body = p[1:1 + p[0]].decode("utf-8", "replace").split("\x07", 1)[-1]
                if body.startswith("#c3check "):
                    _, cid, names = body.split(" ", 2)
                    bits = "".join("1" if self.has(n) else "0" for n in names.split(";") if n)
                    self.chat("#c3have %s %s 2.2" % (cid, bits))
                elif self.name == "P1":
                    print("   chat:", body.split("% ", 1)[-1], flush=True)
            elif code == 0x04B0 and len(p) > 4 and p[:2] == b"\x00\x04":
                sec = p[2]
                if sec == 66:                                       # pause
                    if self.is_host:
                        self.send(0x04B0, 0, p)
                        print("   [host pauses]" if p[4] == 1 else "   [host unpauses]", flush=True)
                elif sec == 71:                                     # ReadLoad
                    n = struct.unpack_from("<H", p, 4)[0]
                    name = p[6:6 + n].decode()
                    st = "ok" if self.has(name) else "missing"
                    print("   [%s loads %s -> %s]" % (self.name, name, st), flush=True)
                    self.chat("#c3loaded %s %s" % (name, st))
                elif sec == 70:                                     # ReadSave
                    n = struct.unpack_from("<H", p, 4)[0]
                    name = p[6:6 + n].decode()
                    print("   [%s SAVES as %s]" % (self.name, name), flush=True)
                    self.saves().mkdir(parents=True, exist_ok=True)
                    with open(str(self.saves() / (name + ".map")), "wb") as f:
                        f.write(b"OSWMap" + os.urandom(A.save_mb << 20))

    def chat(self, text, prefix="0|en\x07"):
        super().chat(text, prefix)


def main():
    start_servers()
    machines = {n: make_machine(n, n == "P2" and PWSH is not None) for n in NAMES}
    for n, m in machines.items():
        if HELPERS[n]:
            log = open(str(m["root"] / "helper.out"), "w")
            procs.append(subprocess.Popen(m["cmd"], env=m["env"], stdout=log, stderr=subprocess.STDOUT))
    print("machines: " + ", ".join("%s %s helper %s%s" % (n, IPS[n], "on" if HELPERS[n] else "OFF",
                                                       " (Windows helper)" if n == "P2" and PWSH else "") for n in NAMES))
    time.sleep(4)
    tag = str(int(time.time() * 1000))[-7:]
    games = {n: Game(n, machines[n], host=(n == "HOST")) for n in NAMES}
    h, p1, p2 = games["HOST"], games["P1"], games["P2"]
    for g in games.values():
        g.register("%s%s@x.test" % (g.name.lower(), tag), "%s%s" % (g.name, tag))
    for g in games.values():
        g.take()
    h.send(0x019C, 0, u32(3) + s8("") + s8('"sim room"\t""\t03EEB') + s8("0") + u32(0) + bytes([0]) + bytes([0]))
    h.pump(0.5)
    for g in (p1, p2):
        g.send(0x019E, 0, u32(h.id))
        g.pump(0.3)
    h.pump(0.5)
    for g in games.values():
        g.take()
    h.send(0x01A2, 0, u32(3) + u32(h.id) + bytes([1]) + u32(p1.id) + bytes([2]) + u32(p2.id) + bytes([3]))
    time.sleep(0.5)
    for g in games.values():
        g.pump(0.3)
        g.take()

    def run_for(seconds):
        end = time.time() + seconds
        while time.time() < end:
            for g in games.values():
                g.react()

    for cmd in A.commands:
        if cmd.startswith("wait "):
            print("... waiting %s s" % cmd.split()[1], flush=True)
            run_for(float(cmd.split()[1]))
            continue
        if cmd.startswith("copy "):
            who = games[cmd.split()[1]]
            newest = max(h.saves().glob("qladder_*.map"), key=lambda f: f.stat().st_mtime)
            who.saves().mkdir(parents=True, exist_ok=True)
            shutil.copy(str(newest), str(who.saves() / newest.name))
            print("... copied %s to %s by hand" % (newest.name, who.name), flush=True)
            continue
        wait = 60 if cmd.startswith("!load") else (20 if cmd.startswith("!save") else 6)
        print("P1 types:", cmd, flush=True)
        p1.chat(cmd)
        run_for(wait)
        time.sleep(1.2)
    for n, g in games.items():
        print("%s saves folder: %s" % (n, sorted(f.name for f in g.saves().glob("*")) if g.saves().exists() else []))


try:
    main()
finally:
    for p in procs:
        p.terminate()
    if A.keep:
        print("files kept in", W)
    else:
        shutil.rmtree(str(W), ignore_errors=True)
