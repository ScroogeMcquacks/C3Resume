"""What both Linux setup windows share (c3resume_gui.py with Tk, c3resume_dialogs.py with zenity / kdialog / the
terminal): the texts in both languages, the remembered language, and calling c3resume.py, which does the work."""
import json
import locale
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLI = [sys.executable, str(HERE / "c3resume.py")]
OFFICIAL = {"138.201.198.174"}                          # the game's normal lobby server: it has no !save / !load
TEXTS = json.loads((HERE / "texts.json").read_text(encoding="utf-8"))
LANGS = ("en", "de")
SETTINGS = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")) / "c3resume" / "settings.json"


def system_lang():
    for v in (os.environ.get("LANGUAGE", ""), os.environ.get("LC_ALL", ""), os.environ.get("LANG", ""),
              (locale.getlocale()[0] or "")):
        if v:
            return "de" if v.lower().startswith("de") else "en"
    return "en"


def saved_lang():
    """the language picked last time, else the computer's"""
    try:
        lang = json.loads(SETTINGS.read_text()).get("lang")
        if lang in LANGS:
            return lang
    except (OSError, ValueError, AttributeError):
        pass
    return system_lang()


def save_lang(lang):
    try:
        SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS.write_text(json.dumps({"lang": lang}))
    except OSError:
        pass                                            # only a convenience


def text(lang, key, **kw):
    return TEXTS[lang][key].format(**kw)


def run(args):
    p = subprocess.run(CLI + args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    return p.returncode, p.stdout.decode("utf-8", "replace")


def info(game_dir=""):
    rc, out = run(["info"] + (["--game-dir", game_dir] if game_dir else []))
    try:
        return json.loads(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None


def valid_server(addr):
    return re.fullmatch(r"[A-Za-z0-9.\-]+(:\d{1,5})?", addr or "") is not None


def suggested_server(i):
    """the server address the game uses now - unless it is the official lobby"""
    current = re.sub(r":31523$", "", (i or {}).get("server", ""))
    return "" if current in OFFICIAL else current


def state(i):
    """(status text key, colour, {format values}, install button key) for what `info` reported"""
    green, orange, red = "#007828", "#be5a00", "#b40000"
    if not i or not i.get("found"):
        return "st_notfound", red, {}, "install"
    if not i["installed"]:
        return "st_notinstalled", orange, {}, "install"
    if not i["intact"]:
        return "st_reset", orange, {}, "install_again"
    if i["installed_version"] != i["version"]:
        return "st_older", orange, {"v": i["installed_version"]}, "update"
    if i.get("helper"):
        return "st_ready", green, {"v": i["version"]}, "install_again"
    if i.get("helper_installed"):
        return "st_nohelper", orange, {}, "install_again"
    return "st_ready_manual", green, {"v": i["version"]}, "install_again"


def helper_default(i):
    """the save helper box: as it is now when installed, else on (recommended)"""
    if i and i.get("installed"):
        return bool(i.get("helper_installed") or i.get("helper"))
    return True


def install_args(game_dir, server, helper):
    return ["install", "--game-dir", game_dir, "--server", server] + ([] if helper else ["--no-helper"])
