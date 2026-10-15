#!/usr/bin/env python3
"""
c3fake.py - two SIMULATED Cossacks 3 clients (a host and a player) for testing a lobby server without the game.

It speaks only what the net spec documents for the lobby: register, create room, join, start (lock), room chat,
and it prints every frame each side receives. It does NOT simulate the game itself (no map, no units) - the
'host' just sits there, so a command that needs a real game to answer will show the frames the server SENT.

  python3 c3fake.py                      # against 127.0.0.1:31523, runs !pause then !save
  python3 c3fake.py --host 10.0.0.5 --cmd '!save'

Standard library only; uses c3wire.py (same folder).
"""
import argparse
import socket
import struct
import sys
import time

from c3wire import CODES, HDR, pack_frame

CODES.update({0x0198: "SERVER_REGISTER", 0x0199: "USER_REGISTER", 0x019A: "SERVER_AUTHENTICATE",
              0x019B: "USER_AUTHENTICATE", 0x019C: "SERVER_SESSION_CREATE", 0x019D: "USER_SESSION_CREATE",
              0x019E: "SERVER_SESSION_JOIN", 0x019F: "USER_SESSION_JOIN", 0x01A2: "SERVER_SESSION_LOCK",
              0x01A3: "USER_SESSION_LOCK", 0x0196: "SERVER_MESSAGE", 0x0197: "USER_MESSAGE",
              0x01A6: "USER_CONNECTED", 0x01A1: "USER_SESSION_LEAVE", 0x01AA: "SERVER_SESSION_UPDATE",
              0x01A5: "USER_SESSION_INFO", 0x01B4: "USER_UPDATE_INFO"})


def s8(text):
    raw = text.encode()
    return bytes([len(raw)]) + raw


def u32(n):
    return struct.pack("<I", n)


class Fake:
    def __init__(self, name, host, port, source=None):
        self.name = name
        self.sock = socket.create_connection((host, port), timeout=5, source_address=(source, 0) if source else None)
        self.buf = b""
        self.id = None
        self.inbox = []

    def send(self, code, to=0, payload=b""):
        self.sock.sendall(pack_frame(code, self.id or 0, to, payload))

    def pump(self, secs=0.6):
        end = time.time() + secs
        self.sock.settimeout(0.1)
        while time.time() < end:
            try:
                chunk = self.sock.recv(65536)
                if not chunk:
                    break
                self.buf += chunk
            except socket.timeout:
                pass
            while len(self.buf) >= HDR.size:
                n, code, a, b = HDR.unpack_from(self.buf)
                if len(self.buf) < HDR.size + n:
                    break
                self.inbox.append((code, a, b, self.buf[HDR.size:HDR.size + n]))
                self.buf = self.buf[HDR.size + n:]

    def take(self):
        got, self.inbox = self.inbox, []
        return got

    def register(self, email, nick):
        payload = (s8("1.0.0.7") + s8("2.2.3") + s8(email) + s8("pw") + s8("anykey")
                   + s8(nick) + s8("") + s8(""))
        self.send(0x0198, 0, payload)
        self.pump(1.0)
        for code, a, b, p in self.inbox:
            if code in (0x0199, 0x019B):
                self.id = b
                return p[0]
        return None

    def chat(self, text, prefix="0|en\x07"):
        self.send(0x0194, 0, s8(prefix + text))


def show(client, frames, only=None):
    for code, a, b, p in frames:
        if only and code not in only:
            continue
        name = CODES.get(code, "0x%04X" % code)
        extra = ""
        if code in (0x0194, 0x0195, 0x0196, 0x0197) and p:
            extra = "  text=" + repr(p[1:1 + p[0]].decode("utf-8", "replace"))
        elif code == 0x04B0:
            extra = "  payload=" + p.hex(" ")
        print("  [%s] <- %-24s from=%-10d to=%-10d len=%-4d%s" % (client.name, name, a, b, len(p), extra))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=31523)
    ap.add_argument("--cmd", action="append", help="chat command(s) the PLAYER types in the match (default: !pause !save)")
    a = ap.parse_args()
    cmds = a.cmd or ["!pause", "!save"]
    tag = str(int(time.time()))[-6:]

    h, p = Fake("HOST", a.host, a.port), Fake("PLAYER", a.host, a.port)
    print("register  HOST   -> error code", h.register("host%s@x.test" % tag, "Host%s" % tag), " id", h.id)
    print("register  PLAYER -> error code", p.register("player%s@x.test" % tag, "Player%s" % tag), " id", p.id)
    if h.id is None or p.id is None:
        sys.exit("could not register - is the server running? (check its terminal)")
    h.take(); p.take()

    gamename = '"fake room"\t""\t03EEB'
    h.send(0x019C, 0, u32(2) + s8("") + s8(gamename) + s8("0") + u32(0) + bytes([0]) + bytes([0]))
    h.pump(0.5)
    p.send(0x019E, 0, u32(h.id))
    h.pump(0.5); p.pump(0.5)
    h.take(); p.take()

    h.send(0x01A2, 0, u32(2) + u32(h.id) + bytes([1]) + u32(p.id) + bytes([2]))      # the host starts the match
    h.pump(0.5); p.pump(0.5)
    h.take(); p.take()
    print("room created, joined and started (locked).\n")

    for text in cmds:
        print("PLAYER types in the match chat:", repr(text))
        p.chat(text)
        h.pump(1.0); p.pump(1.0)
        print(" what the HOST receives:")
        show(h, h.take())
        print(" what the PLAYER receives:")
        show(p, p.take())
        print()
        time.sleep(1.2)                       # the server ignores a client's commands closer than 1 s


if __name__ == "__main__":
    main()
