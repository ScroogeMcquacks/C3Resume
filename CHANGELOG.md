# Changelog

## 2.2
- The save helper is optional in both installers. The setup explains what it does and what playing without it
  means (the host sends the save file to everybody, who put it into their saves folder by hand).
- Linux setup: choose English or German (also in the simple zenity / kdialog dialogs and in the terminal version);
  the choice is remembered. Windows setup: a language list instead of a button, also remembered.
- Server: knows which players run a save helper. It no longer waits up to 10 minutes for a download that can never
  come, and says who has to copy the save by hand. Saves that only the host has are listed in `!saves` as
  `[host PC]` and can be loaded once everybody has a copy.
- Server: a save on a host without the helper says so right away instead of after 5 minutes.
- "Open saves folder" creates the folder if the game never saved yet (needed to put a copied save there).
- The save service no longer writes a log line for every 5-second check of every helper.
- Published as a GitHub project: license (MIT), third-party notices, beginner guide in English and German, checks
  and a test simulator in `dev/`.

## 2.1
- Windows: Update restarts the save helper (before, the old helper kept running until the next login).
- Server: waits up to 10 minutes for slow downloads of big saves and says every 30 seconds who is still
  downloading.
- `tools/c3diag.ps1`: a diagnostic report for Windows PCs that do not get the saves.

## 2.0
- Big saves: no size limit of 400 MB any more; the helpers pack, upload and download piece by piece; a failed upload
  is tried again after 2 minutes instead of every 5 seconds.
- "Everyone has loaded" only when every game really reported the load and answers again.

## 1.x
- Save a running multiplayer match on the host only and load it on all PCs (`!save`, `!saves`, `!load`), with
  the host's file sent through the server. Autosave every 5 minutes with one kept autosave (`!autosave`). Buttons in
  the F10 menu. Setup windows for Windows and Linux in English and German. One load per match (a second load in the
  same match can freeze the other PCs).
