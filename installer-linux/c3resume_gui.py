#!/usr/bin/env python3
"""c3resume setup window for Linux (Tk). Started by setup-linux.sh. The work is done by c3resume.py next to it."""
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import c3resume_ui as ui

WRAP = 800


class App:
    def __init__(self, root):
        self.root = root
        self.lang = ui.saved_lang()
        self.last = None
        self.state = ("st_looking", "#333333", {}, "install")
        root.resizable(False, False)
        pad = {"padx": 14, "sticky": "w"}
        f = ("TkDefaultFont", 11)
        bold = ("TkDefaultFont", 11, "bold")
        small = ("TkDefaultFont", 10)

        top = tk.Frame(root)
        top.grid(row=0, column=0, columnspan=3, sticky="ew", padx=14, pady=(12, 2))
        self.head = tk.Label(top, font=bold)
        self.head.pack(side="left")
        names = {ui.TEXTS[l]["lang_name"]: l for l in ui.LANGS}
        self.langvar = tk.StringVar(value=ui.TEXTS[self.lang]["lang_name"])
        menu = tk.OptionMenu(top, self.langvar, *sorted(names), command=lambda name: self.set_lang(names[name]))
        menu.pack(side="right")
        self.langlabel = tk.Label(top, font=small)
        self.langlabel.pack(side="right", padx=(20, 4))

        self.about = tk.Label(root, font=small, wraplength=WRAP, justify="left", fg="#333333")
        self.about.grid(row=1, column=0, columnspan=3, pady=(4, 8), **pad)
        self.status = tk.Label(root, font=("TkDefaultFont", 12, "bold"), wraplength=WRAP, justify="left")
        self.status.grid(row=2, column=0, columnspan=3, pady=(0, 8), **pad)

        self.step1 = tk.Label(root, font=f)
        self.step1.grid(row=3, column=0, columnspan=3, **pad)
        self.game = tk.StringVar()
        tk.Entry(root, textvariable=self.game, width=84, state="readonly").grid(row=4, column=0, columnspan=2, **pad)
        self.browse = tk.Button(root, command=self.on_browse)
        self.browse.grid(row=4, column=2, padx=(0, 14), sticky="e")

        self.step2 = tk.Label(root, font=f)
        self.step2.grid(row=5, column=0, columnspan=3, pady=(10, 0), **pad)
        self.server = tk.StringVar()
        tk.Entry(root, textvariable=self.server, width=30, font=f).grid(row=6, column=0, columnspan=3, **pad)

        self.helper = tk.BooleanVar(value=True)
        self.helper_touched = False
        self.helpercheck = tk.Checkbutton(root, variable=self.helper, font=f, command=self.on_helper)
        self.helpercheck.grid(row=7, column=0, columnspan=3, pady=(10, 0), padx=10, sticky="w")
        self.helpertext = tk.Label(root, font=small, wraplength=WRAP - 26, justify="left", fg="#333333")
        self.helpertext.grid(row=8, column=0, columnspan=3, padx=(38, 14), sticky="w")

        row = tk.Frame(root)
        row.grid(row=9, column=0, columnspan=3, pady=12, **pad)
        self.install = tk.Button(row, font=bold, width=18, height=2, command=self.on_install)
        self.install.pack(side="left")
        self.uninstall = tk.Button(row, width=14, height=2, command=self.on_uninstall)
        self.uninstall.pack(side="left", padx=10)
        self.saves = tk.Button(row, width=18, height=2, command=self.on_saves)
        self.saves.pack(side="left")
        self.hint = tk.Label(root, font=f, wraplength=WRAP, justify="left")
        self.hint.grid(row=10, column=0, columnspan=3, **pad)
        self.details = tk.Text(root, width=112, height=7, font=("TkFixedFont", 9), state="disabled")
        self.details.grid(row=11, column=0, columnspan=3, padx=14, pady=(6, 14))
        self.apply_lang()
        root.after(100, lambda: self.show(ui.info()))

    def t(self, key, **kw):
        return ui.text(self.lang, key, **kw)

    def set_lang(self, lang):
        self.lang = lang
        ui.save_lang(lang)
        self.apply_lang()

    def apply_lang(self):
        self.root.title(self.t("window"))
        self.langlabel.configure(text=self.t("lang_label"))
        self.head.configure(text=self.t("head"))
        self.about.configure(text=self.t("about"))
        self.step1.configure(text=self.t("step1"))
        self.browse.configure(text=self.t("change"))
        self.step2.configure(text=self.t("step2"))
        self.helpercheck.configure(text=self.t("helper_check"))
        self.uninstall.configure(text=self.t("uninstall"))
        self.saves.configure(text=self.t("saves"))
        self.hint.configure(text=self.t("close_hint"))
        key, color, kw, btn = self.state
        self.status.configure(text=self.t(key, **kw), fg=color)
        self.install.configure(text=self.t(btn))
        self.on_helper(touched=False)

    def on_helper(self, touched=True):
        if touched:
            self.helper_touched = True
        self.helpertext.configure(text=self.t("helper_on" if self.helper.get() else "helper_off"),
                                  fg="#333333" if self.helper.get() else "#8a4500")

    def set_details(self, text):
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", text)
        self.details.configure(state="disabled")

    def buttons(self, install, uninstall, saves):
        self.install.configure(state="normal" if install else "disabled")
        self.uninstall.configure(state="normal" if uninstall else "disabled")
        self.saves.configure(state="normal" if saves else "disabled")

    def show(self, i):
        self.last = i
        self.state = ui.state(i)
        found = bool(i and i.get("found"))
        if found:
            self.game.set(i["game_dir"])
            if not self.server.get():
                self.server.set(ui.suggested_server(i))
            if not self.helper_touched:
                self.helper.set(ui.helper_default(i))
        self.buttons(found, found and i["installed"], found)
        self.apply_lang()

    def act(self, args, done_key):
        self.buttons(False, False, False)
        self.browse.configure(state="disabled")
        self.set_details(self.t("working"))
        self.root.config(cursor="watch")
        self.root.update()
        rc, out = ui.run(args)
        self.root.config(cursor="")
        self.browse.configure(state="normal")
        self.set_details(out.strip())
        self.helper_touched = False
        self.show(ui.info(self.game.get()))
        if rc == 0:
            messagebox.showinfo("c3resume", self.t(done_key))
        else:
            messagebox.showwarning("c3resume", self.t("failed"))

    def on_browse(self):
        d = filedialog.askdirectory(title=self.t("pick"))
        if d:
            if (Path(d) / "data").exists():
                self.game.set(d)
                self.show(ui.info(d))
            else:
                messagebox.showwarning("c3resume", self.t("not_c3"))

    def on_install(self):
        srv = self.server.get().strip()
        if not srv:
            messagebox.showwarning("c3resume", self.t("need_server"))
            return
        if not ui.valid_server(srv):
            messagebox.showwarning("c3resume", self.t("bad_server"))
            return
        helper = self.helper.get()
        self.act(ui.install_args(self.game.get(), srv, helper), "done_install" if helper else "done_install_manual")

    def on_uninstall(self):
        if messagebox.askyesno("c3resume", self.t("confirm_uninstall")):
            self.act(["uninstall", "--game-dir", self.game.get()], "done_uninstall")

    def on_saves(self):
        rc, out = ui.run(["saves", "--game-dir", self.game.get()])
        if rc != 0:
            messagebox.showwarning("c3resume", self.t("saves_none"))


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
