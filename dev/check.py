#!/usr/bin/env python3
"""Consistency checks before a commit or a release:  python3 dev/check.py

 - the same version everywhere (Linux installer, Windows installer, lobby server, CHANGELOG)
 - installer-windows/patches.json is what installer-linux/c3resume.py exports (run "export" after changing patches)
 - texts.json is the same in both installers, and every text exists in every language
 - every file compiles / parses (Python; Lua if luac5.1 is there; PowerShell if pwsh is there)
 - the patches apply to a stand-in game folder, and uninstall restores every file byte for byte
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIN, WIN, SRV = ROOT / "installer-linux", ROOT / "installer-windows", ROOT / "server"
problems = []


def bad(msg):
    problems.append(msg)
    print("  PROBLEM:", msg)


def ok(msg):
    print("  ok:", msg)


def versions():
    v_lin = re.search(r'^VERSION = "(.+)"', (LIN / "c3resume.py").read_text(), re.M).group(1)
    v_win = re.search(r'^\$Version = "(.+)"', (WIN / "c3resume.ps1").read_text(), re.M).group(1)
    v_srv = re.search(r'c3resume ([\d.]+) \(Sich', (SRV / "sich_c3.lua").read_bytes().decode("latin-1")).group(1)
    v_log = re.search(r"^## ([\d.]+)", (ROOT / "CHANGELOG.md").read_text(), re.M).group(1)
    if len({v_lin, v_win, v_srv, v_log}) == 1:
        ok("version %s everywhere" % v_lin)
    else:
        bad("versions differ: linux %s, windows %s, server %s, CHANGELOG %s" % (v_lin, v_win, v_srv, v_log))
    return v_lin


def patches():
    with tempfile.TemporaryDirectory() as t:
        out = Path(t) / "p.json"
        subprocess.run([sys.executable, str(LIN / "c3resume.py"), "export", str(out)], check=True, stdout=subprocess.DEVNULL)
        if json.loads(out.read_text()) == json.loads((WIN / "patches.json").read_text()):
            ok("patches.json matches the Linux installer")
        else:
            bad("installer-windows/patches.json is outdated: python3 installer-linux/c3resume.py export installer-windows/patches.json")


def texts():
    a, b = (LIN / "texts.json").read_bytes(), (WIN / "texts.json").read_bytes()
    if a != b:
        bad("texts.json differs between installer-linux and installer-windows")
    t = json.loads(a)
    keys = [set(v) for v in t.values()]
    if all(k == keys[0] for k in keys):
        ok("texts.json: %d texts in %s" % (len(keys[0]), ", ".join(t)))
    else:
        bad("texts.json: missing texts: %s" % sorted(set.union(*keys) - set.intersection(*keys)))
    used = set()
    for f in [LIN / "c3resume_gui.py", LIN / "c3resume_dialogs.py", LIN / "c3resume_ui.py", WIN / "c3resume-gui.ps1"]:
        used |= set(re.findall(r'''(?:\bt|ui\.text\(LANG,|T|text\(lang,)\s*\(?\s*["']([a-z_0-9]+)["']''', f.read_text()))
    missing = sorted(k for k in used if k not in keys[0] and not k.startswith(("st_",)))
    if missing:
        bad("texts used but not in texts.json: %s" % missing)


def compiles():
    for f in list(ROOT.rglob("*.py")):
        r = subprocess.run([sys.executable, "-m", "py_compile", str(f)], stderr=subprocess.PIPE)
        if r.returncode:
            bad("python: %s" % r.stderr.decode()[-300:])
    ok("python files compile")
    for p in ROOT.rglob("__pycache__"):
        shutil.rmtree(str(p), ignore_errors=True)
    if shutil.which("luac5.1"):
        r = subprocess.run(["luac5.1", "-p", str(SRV / "sich_c3.lua")], stderr=subprocess.PIPE)
        if r.returncode:
            bad("lua: " + r.stderr.decode())
        else:
            listing = subprocess.run(["luac5.1", "-l", "-p", str(SRV / "sich_c3.lua")], stdout=subprocess.PIPE).stdout.decode()
            stray = sorted(set(re.findall(r"GETGLOBAL.*; (c3\w+|saves_\w+)", listing)))
            if stray:
                bad("lua: names used before they are defined (global by mistake): %s" % stray)
            else:
                ok("lua compiles")
    else:
        print("  (skipped: luac5.1 not installed)")
    pwsh = shutil.which("pwsh")
    if pwsh:
        for f in list(WIN.glob("*.ps1")) + list((ROOT / "tools").glob("*.ps1")):
            r = subprocess.run([pwsh, "-NoProfile", "-Command",
                                "$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile('%s',[ref]$null,[ref]$e); "
                                "$e | ForEach-Object { $_.ToString() }" % str(f).replace("'", "''")], stdout=subprocess.PIPE)
            if r.stdout.strip():
                bad("powershell %s: %s" % (f.name, r.stdout.decode()[:300]))
        for f in list(WIN.glob("*.ps1")) + list((ROOT / "tools").glob("*.ps1")):
            if re.search(rb"[^\x00-\x7f]", f.read_bytes()):
                bad("%s has non-ASCII characters (Windows PowerShell 5.1 would misread them)" % f.name)
        ok("powershell files parse")
    else:
        print("  (skipped: pwsh not installed)")


def install_roundtrip():
    with tempfile.TemporaryDirectory() as t:
        game = Path(subprocess.run([sys.executable, str(ROOT / "dev" / "fake_game.py"), t], stdout=subprocess.PIPE,
                                   check=True).stdout.decode().strip())
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in game.rglob("*") if p.is_file()}
        env = dict(os.environ, HOME=str(Path(t) / "home"), C3RESUME_HOME=str(Path(t) / "helper"))
        cli = [sys.executable, str(LIN / "c3resume.py")]
        r = subprocess.run(cli + ["install", "--game-dir", str(game), "--server", "10.0.0.1", "--no-helper"], env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        info = json.loads(subprocess.run(cli + ["info", "--game-dir", str(game)], env=env, stdout=subprocess.PIPE).stdout)
        if r.returncode or not (info["installed"] and info["intact"]):
            bad("install on the stand-in game failed:\n" + r.stdout.decode()[-800:])
            return
        subprocess.run(cli + ["uninstall", "--game-dir", str(game)], env=env, stdout=subprocess.DEVNULL, check=True)
        after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in game.rglob("*") if p.is_file()}
        if before == after:
            ok("install + uninstall on a stand-in game folder: every file back as it was")
        else:
            bad("uninstall left differences: %s" % sorted(set(before.items()) ^ set(after.items()))[:5])


def main():
    print("c3resume checks")
    versions()
    patches()
    texts()
    compiles()
    install_roundtrip()
    print()
    if problems:
        print("%d problem(s)." % len(problems))
        sys.exit(1)
    print("All good.")


if __name__ == "__main__":
    main()
