#!/usr/bin/env python3
"""
c3saves_server.py - the save-file service of a c3resume lobby (runs next to the lobby server).

The host's c3resume helper uploads the save of every !save here (gzip-compressed). When a match loads a
save (!load), the lobby server lists it in wanted.txt and every player's helper downloads it then, so all
players load the SAME file (the host's).

  python3 c3saves_server.py [--dir SAVES_FOLDER] [--port 31524]

HTTP:  GET /c3/list                 one line per stored save: name <TAB> bytes <TAB> unix time <TAB> 1 if a
                                    !load needs it right now, else 0 (newest first). The helpers ask every 5 s;
                                    their addresses go to helpers.txt, so the lobby server knows which players
                                    run a helper (and does not wait for a download that never comes).
       GET /c3/file/<name>          the gzip file
       PUT /c3/file/<name>          store it (first upload of a name wins; size limited)
Only names of the form  qladder_<date>_<time>_<n>min  are accepted, and  qladder_auto_<date>_<time>_<n>min
for the autosave: of those only the newest is kept. Standard library only.
"""
import argparse
import gzip
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

NAME = re.compile(r"^qladder_(auto_)?\d{8}_\d{4,6}_\d{1,4}min$")
MAX_GZ = 2 * 1024 ** 3               # compressed upload limit (a save of a long, big match is several 100 MB unpacked)
MAX_RAW = 4 * 1024 ** 3              # unpacked: the game is a 32-bit program, its saves stay below 4 GB
CHUNK = 1 << 20
STORE = Path(".")
HELPERS = {}                         # address of a helper -> when it last asked for the list
HELPERS_LOCK = threading.Lock()


def note_helper(addr):
    """helpers.txt: address <TAB> unix time, one line per helper seen in the last day (rewritten at most every 10 s
    per helper). The lobby server compares a player's address with it."""
    now = time.time()
    with HELPERS_LOCK:
        if now - HELPERS.get(addr, 0) < 10:
            return
        HELPERS[addr] = now
        for a in [a for a, t in HELPERS.items() if now - t > 86400]:
            del HELPERS[a]
        tmp = STORE / "helpers.txt.tmp"
        try:
            tmp.write_text("".join("%s\t%d\n" % (a, t) for a, t in sorted(HELPERS.items())))
            os.replace(str(tmp), str(STORE / "helpers.txt"))
        except OSError:
            pass


def wanted():
    """names the lobby server is loading right now (it writes  name <TAB> until-unix-time  lines)"""
    out = set()
    try:
        for line in (STORE / "wanted.txt").read_text().splitlines():
            f = line.split("\t")
            if len(f) >= 2 and NAME.match(f[0]) and float(f[1]) > time.time():
                out.add(f[0])
    except (OSError, ValueError):
        pass
    return out


def listing():
    rows = []
    for p in STORE.glob("qladder_*.map.gz"):
        st = p.stat()
        rows.append((st.st_mtime, p.name[:-len(".map.gz")], st.st_size))
    rows.sort(reverse=True)
    w = wanted()
    return "".join("%s\t%d\t%d\t%d\n" % (n, s, int(t), n in w) for t, n, s in rows)


def write_index():
    tmp = STORE / "index.txt.tmp"
    tmp.write_text(listing())
    os.replace(str(tmp), str(STORE / "index.txt"))         # the lobby server reads this file for !saves


class Handler(BaseHTTPRequestHandler):
    server_version = "c3saves/2.2"

    def log_request(self, code="-", size="-"):
        if self.path == "/c3/list" and str(code) == "200":
            return                                              # the helpers ask every 5 s: not worth a log line
        BaseHTTPRequestHandler.log_request(self, code, size)

    def log_message(self, fmt, *args):
        sys.stdout.write("%s | %s | %s\n" % (time.strftime("%Y.%m.%d %H:%M:%S"), self.client_address[0], fmt % args))
        sys.stdout.flush()

    def answer(self, code, body=b"", ctype="text/plain"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def name_of(self):
        m = re.match(r"^/c3/file/([^/?]+)$", self.path)
        return m.group(1) if m and NAME.match(m.group(1)) else None

    def do_GET(self):
        if self.path == "/c3/list":
            note_helper(self.client_address[0])
            return self.answer(200, listing().encode())
        name = self.name_of()
        p = STORE / (name + ".map.gz") if name else None
        if not p or not p.exists():
            return self.answer(404, b"no such save\n")
        self.send_response(200)                                 # streamed: big saves never sit in memory
        self.send_header("Content-Type", "application/gzip")
        self.send_header("Content-Length", str(p.stat().st_size))
        self.end_headers()
        with open(str(p), "rb") as f:
            for chunk in iter(lambda: f.read(CHUNK), b""):
                self.wfile.write(chunk)

    def do_PUT(self):
        name = self.name_of()
        if not name:
            return self.answer(400, b"bad name\n")
        size = int(self.headers.get("Content-Length") or 0)
        if size <= 0 or size > MAX_GZ:
            self.log_message("refused %s: size %d", name, size)
            return self.answer(413, b"bad size\n")
        tmp = STORE / (name + ".tmp")
        got = 0
        with open(str(tmp), "wb") as out:                       # streamed to disk, not into memory
            while got < size:
                chunk = self.rfile.read(min(CHUNK, size - got))
                if not chunk:
                    break
                out.write(chunk)
                got += len(chunk)
        try:
            if got != size:
                return self.answer(400, b"short upload\n")
            try:
                with gzip.open(str(tmp), "rb") as g:
                    head = g.read(64)
                    total = len(head) + sum(len(c) for c in iter(lambda: g.read(CHUNK), b""))
            except (OSError, EOFError):
                self.log_message("refused %s: not a gzip file", name)
                return self.answer(400, b"not a gzip file\n")
            if b"OSWMap" not in head or total > MAX_RAW:
                self.log_message("refused %s: not a Cossacks 3 save (%d bytes unpacked)", name, total)
                return self.answer(400, b"not a Cossacks 3 save\n")
            final = STORE / (name + ".map.gz")
            if final.exists():
                return self.answer(200, b"already here\n")          # first upload (the host's) wins
            if name.startswith("qladder_auto_") and any(p.name > final.name for p in STORE.glob("qladder_auto_*.map.gz")):
                return self.answer(200, b"a newer autosave is here\n")
            os.replace(str(tmp), str(final))
            if name.startswith("qladder_auto_"):                   # one autosave: the new one replaces the older ones
                busy = wanted()                                     # (not one that a !load is fetching right now)
                for old in STORE.glob("qladder_auto_*.map.gz"):
                    if old.name < final.name and old.name[:-len(".map.gz")] not in busy:
                        old.unlink()
                        self.log_message("removed the older autosave %s", old.name)
            write_index()
            self.log_message("stored %s (%d bytes, %d unpacked)", name, size, total)
            self.answer(201, b"stored\n")
        finally:
            if tmp.exists():
                tmp.unlink()


def main():
    global STORE
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=str(Path(__file__).resolve().parent / "saves"))
    ap.add_argument("--port", type=int, default=31524)
    ap.add_argument("--host", default="0.0.0.0")
    a = ap.parse_args()
    STORE = Path(a.dir)
    STORE.mkdir(parents=True, exist_ok=True)
    write_index()
    (STORE / "helpers.txt").write_text("")                 # (an empty file tells the lobby server: no helper seen yet)
    print("c3resume save service: folder %s, port %d" % (STORE, a.port))
    sys.stdout.flush()
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
