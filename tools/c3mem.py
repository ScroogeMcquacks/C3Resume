#!/usr/bin/env python3
"""c3mem.py - how close is a running Cossacks 3 (under Proton/Wine) to its 4 GB limit?

The game is a 32-bit Windows program: everything it uses must fit below the 4 GB address mark. Linux tools (top, VSZ)
do not show that under Wine. This reads /proc/<pid>/maps of every running cossacks.exe and sums what lies below 4 GB.

  python3 c3mem.py            once
  python3 c3mem.py 10         every 10 seconds (Ctrl+C to stop); shows the highest value seen
  python3 c3mem.py --detail   once, plus what the memory is used for (game, graphics driver, Wine, ...)
"""
import os
import sys
import time

LIMIT = 1 << 32           # 4 GB: the 32-bit game's address space
MB = 1 << 20
peak = 0

# what a mapping belongs to, decided by its file name (first match wins)
KINDS = [
    ("graphics driver", ("nvidia", "libgl", "libegl", "mesa", "/dri/", "dri_", "gallium", "radeon", "amdgpu", "iris",
                         "libvulkan", "vulkan", "libllvm", "libdrm", "/dev/dri", "libxcb", "libx11", "libwayland",
                         "opengl32", "winex11", "winevulkan", "glu32", "d3d9", "dxgi")),
    ("game files", ("cossacks 3",)),
    ("Wine / Proton", ("/wine/", "proton", "/pfx/", "wine")),
    ("Linux libraries", (".so",)),
]


def kind(path):
    p = path.lower()
    if not p:
        return "game + driver data (no file)"
    if p.startswith("["):
        return "game + driver data (no file)" if p in ("[heap]", "[anon]") else "other"
    for name, keys in KINDS:
        if any(k in p for k in keys):
            return name
    return "other files"


def games():
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open("/proc/%s/maps" % pid) as f:
                maps = f.read()
        except OSError:
            continue
        if "cossacks.exe" in maps.lower():
            yield int(pid), maps


def measure(maps, detail=None):
    used = reserved = 0           # used: readable/writable memory; reserved: kept free by Wine/the game (---p)
    regions = []
    for line in maps.splitlines():
        parts = line.split(None, 5)
        rng, perms = parts[:2]
        a, b = (int(x, 16) for x in rng.split("-"))
        if a >= LIMIT:
            continue
        b = min(b, LIMIT)
        regions.append((a, b))
        if perms[:3] == "---":
            reserved += b - a
        else:
            used += b - a
            if detail is not None:
                k = kind(parts[5].strip() if len(parts) > 5 else "")
                detail[k] = detail.get(k, 0) + b - a
    regions.sort()
    gaps, pos = [], 0x10000                         # the lowest 64 KB are never usable on Windows
    for a, b in regions:
        if a > pos:
            gaps.append(a - pos)
        pos = max(pos, b)
    if LIMIT > pos:
        gaps.append(LIMIT - pos)
    return used, reserved, sum(gaps), max(gaps or [0])


def rss(pid):
    try:
        with open("/proc/%d/status" % pid) as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
    except OSError:
        pass
    return 0


def report(want_detail=False, every=0):
    global peak
    found = False
    for pid, maps in games():
        found = True
        detail = {} if want_detail else None
        used, reserved, free, biggest = measure(maps, detail)
        peak = max(peak, used)
        print("cossacks.exe  pid %d   %s" % (pid, time.strftime("%H:%M:%S")))
        print("  in use below 4 GB:   %5d MB   (%2d %% of 4096)%s" % (
            used // MB, used * 100 // LIMIT, ("   highest so far: %d MB" % (peak // MB)) if every else ""))
        if detail:
            for k, v in sorted(detail.items(), key=lambda kv: -kv[1]):
                print("      %-30s %5d MB" % (k, v // MB))
            above = sum(1 for line in maps.splitlines() if int(line.split("-")[0], 16) >= LIMIT)
            print("      Proton mode: %s" % ("NEW WoW64 (Wine and driver code live above 4 GB)" if above > 20
                                             else "classic 32-bit (everything shares the 4 GB)"))
        print("  reserved, not used:  %5d MB   (kept free by Wine / the game)" % (reserved // MB))
        print("  completely free:     %5d MB   largest free block: %d MB" % (free // MB, biggest // MB))
        print("  RAM actually in use: %5d MB" % (rss(pid) // MB))
        if used > 3300 * MB:
            verdict = "VERY CLOSE - save now; a big load or more units can freeze the game."
        elif used > 2800 * MB:
            verdict = "getting tight - keep an eye on it."
        else:
            verdict = "fine - plenty of room."
        print("  -> " + verdict)
        print()
    if not found:
        print("No running cossacks.exe found.")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--detail"]
    every = int(args[0]) if args else 0
    while True:
        report("--detail" in sys.argv, every)
        if not every:
            break
        time.sleep(every)
