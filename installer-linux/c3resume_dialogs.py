#!/usr/bin/env python3
"""c3resume setup for Linux without Tk: the same steps as the setup window, as simple dialogs - zenity (GNOME, most
desktops), kdialog (KDE, Steam Deck desktop), or questions in the terminal.

  python3 c3resume_dialogs.py              zenity or kdialog, whichever is there (else the terminal)
  python3 c3resume_dialogs.py --terminal   questions in the terminal
"""
import html
import os
import shutil
import subprocess
import sys
from pathlib import Path

import c3resume_ui as ui

TITLE = "c3resume"


class Zenity:
    def _run(self, args):
        p = subprocess.run(["zenity", "--title=" + TITLE] + args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        return p.returncode, p.stdout.decode("utf-8", "replace").strip()

    def message(self, text, error=False):
        self._run(["--error" if error else "--info", "--width=560", "--text=" + html.escape(text)])

    def choose(self, text, options, default=None, cancel=None):
        """options: [(id, label)]; returns the id, or None (closed / cancelled)"""
        args = ["--list", "--radiolist", "--width=600", "--height=%d" % (190 + 24 * text.count("\n") + 56 * len(options)),
                "--text=" + html.escape(text), "--column=", "--column=id", "--column=" + ui.text(LANG, "column"),
                "--hide-column=2", "--print-column=2", "--hide-header",
                "--ok-label=" + ui.text(LANG, "ok"), "--cancel-label=" + (cancel or ui.text(LANG, "cancel"))]
        default = default or options[0][0]                # first, so the marked row is also the highlighted one
        for oid, label in sorted(options, key=lambda o: o[0] != default):
            args += ["TRUE" if oid == default else "FALSE", oid, label]
        rc, out = self._run(args)
        return out.split("|")[0] if rc == 0 and out else None

    def ask_yes_no(self, text, yes, no):
        """True (yes), False (no), None (back / closed)"""
        rc, out = self._run(["--question", "--width=620", "--text=" + text, "--ok-label=" + yes,
                             "--cancel-label=" + ui.text(LANG, "back"), "--extra-button=" + no])
        if rc == 0:
            return True
        return False if out == no else None

    def confirm(self, text):
        return self._run(["--question", "--width=480", "--text=" + html.escape(text)])[0] == 0

    def entry(self, text, value):
        rc, out = self._run(["--entry", "--width=520", "--text=" + html.escape(text), "--entry-text=" + value])
        return out if rc == 0 else None

    def folder(self, text):
        rc, out = self._run(["--file-selection", "--directory", "--title=" + text])
        return out if rc == 0 else None

    def bold(self, text):
        return "<b>%s</b>" % html.escape(text)

    def plain(self, text):
        return html.escape(text)


class KDialog:
    def _run(self, args):
        p = subprocess.run(["kdialog", "--title", TITLE] + args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        return p.returncode, p.stdout.decode("utf-8", "replace").strip()

    def message(self, text, error=False):
        self._run(["--error" if error else "--msgbox", text])

    def choose(self, text, options, default=None, cancel=None):
        args = ["--radiolist", text]
        for oid, label in options:
            args += [oid, label, "on" if oid == (default or options[0][0]) else "off"]
        rc, out = self._run(args)
        return out if rc == 0 and out else None

    def ask_yes_no(self, text, yes, no):
        rc, _ = self._run(["--yes-label", yes, "--no-label", no, "--cancel-label", ui.text(LANG, "back"),
                           "--yesnocancel", text])
        return {0: True, 1: False}.get(rc)

    def confirm(self, text):
        return self._run(["--yesno", text])[0] == 0

    def entry(self, text, value):
        rc, out = self._run(["--inputbox", text, value])
        return out if rc == 0 else None

    def folder(self, text):
        rc, out = self._run(["--getexistingdirectory", str(Path.home()), "--title", text])
        return out if rc == 0 else None

    def bold(self, text):
        return text

    def plain(self, text):
        return text


class Terminal:
    def message(self, text, error=False):
        print()
        print(text)
        try:
            input(ui.text(LANG, "press_enter"))
        except EOFError:
            pass

    def _ask(self, prompt):
        try:
            return input(prompt).strip()
        except EOFError:
            return None

    def choose(self, text, options, default=None, cancel=None):
        print()
        print(text)
        for n, (oid, label) in enumerate(options, 1):
            print("  %d) %s" % (n, label))
        while True:
            a = self._ask(ui.text(LANG, "your_choice"))
            if a is None:
                return None
            if a == "" and default:
                return default
            if a.isdigit() and 1 <= int(a) <= len(options):
                return options[int(a) - 1][0]

    def ask_yes_no(self, text, yes, no):
        print()
        print(text)
        print("  1) " + yes)
        print("  2) " + no)
        print("  3) " + ui.text(LANG, "back"))
        while True:
            a = self._ask(ui.text(LANG, "your_choice"))
            if a is None or a == "3":
                return None
            if a in ("1", "2"):
                return a == "1"

    def confirm(self, text):
        a = self._ask("%s %s " % (text, ui.text(LANG, "yes_no")))
        return bool(a) and a[0].lower() in ui.text(LANG, "yes_letters")

    def entry(self, text, value):
        print()
        a = self._ask("%s%s\n> " % (text, " [%s]" % value if value else ""))
        if a is None:
            return None
        return a or value

    def folder(self, text):
        print()
        return self._ask(text + "\n> ")

    def bold(self, text):
        return text.upper()

    def plain(self, text):
        return text


LANG = "en"


def pick_backend(force_terminal):
    if not force_terminal and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        if shutil.which("zenity"):
            return Zenity()
        if shutil.which("kdialog"):
            return KDialog()
    return Terminal()


def main():
    global LANG
    ui_ = pick_backend("--terminal" in sys.argv)
    LANG = ui.saved_lang()
    lang = ui_.choose("Please choose your language.\nBitte wähle deine Sprache.",
                      [(l, ui.TEXTS[l]["lang_name"]) for l in ui.LANGS], default=LANG,
                      cancel="Cancel / Abbrechen")
    if lang is None:
        return
    LANG = lang
    ui.save_lang(lang)
    t = lambda key, **kw: ui.text(LANG, key, **kw)

    i = ui.info()
    game = i["game_dir"] if i and i.get("found") else ""
    server = ui.suggested_server(i)
    while True:
        if not i or not i.get("found"):
            ui_.message(t("st_notfound"))
            d = ui_.folder(t("pick"))
            if not d:
                return
            if not (Path(d) / "data").exists():
                ui_.message(t("not_c3"), error=True)
                continue
            game = d
            i = ui.info(game)
            continue
        key, _color, kw, btn = ui.state(i)
        options = [("install", t(btn).split(".", 1)[-1].strip())]
        if i["installed"]:
            options.append(("uninstall", t("act_uninstall")))
        options += [("saves", t("saves")), ("quit", t("act_quit"))]
        what = ui_.choose("%s\n\n%s\n\n%s" % (t("head"), t(key, **kw), t("menu_text")), options)
        if what in (None, "quit"):
            return
        if what == "saves":
            rc, out = ui.run(["saves", "--game-dir", game])
            if rc != 0:
                ui_.message(t("saves_none"))
            elif isinstance(ui_, Terminal):
                ui_.message(out.strip())
            continue
        if what == "uninstall":
            if not ui_.confirm(t("confirm_uninstall")):
                continue
            args, done = ["uninstall", "--game-dir", game], "done_uninstall"
        else:
            srv = ui_.entry(t("step2").split(".", 1)[-1].strip(), server)
            if srv is None:
                continue
            srv = srv.strip()
            if not ui.valid_server(srv):
                ui_.message(t("need_server") if not srv else t("bad_server"), error=True)
                continue
            server = srv
            helper = ui_.ask_yes_no("%s\n\n%s\n%s\n\n%s\n%s" % (
                ui_.bold(t("helper_ask")), ui_.bold(t("helper_with")), ui_.plain(t("helper_on")),
                ui_.bold(t("helper_without")), ui_.plain(t("helper_off"))), t("helper_yes"), t("helper_no"))
            if helper is None:
                continue
            args, done = ui.install_args(game, srv, helper), ("done_install" if helper else "done_install_manual")
        if isinstance(ui_, Terminal):
            print()
            print(t("working"))
        rc, out = ui.run(args)
        if rc == 0:
            ui_.message("%s\n\n%s\n%s" % (t(done), t("details"), out.strip()))
        else:
            ui_.message("%s\n\n%s" % (t("failed_dialog"), out.strip()), error=True)
        i = ui.info(game)


if __name__ == "__main__":
    main()
