#!/usr/bin/env bash
# c3resume setup for Linux. Run it:  bash setup-linux.sh   (or right-click > Run as a program)
# It opens the setup window (needs Tk). Without Tk it asks the same questions in simple dialogs (zenity or kdialog),
# and without those in the terminal.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  msg="python3 is missing - install it with your package manager. / python3 fehlt - bitte mit der Paketverwaltung installieren."
  if command -v zenity >/dev/null; then zenity --error --text="$msg"
  elif command -v kdialog >/dev/null; then kdialog --error "$msg"
  else echo "$msg"; fi
  exit 1
fi
if python3 -c "import tkinter; tkinter.Tk().destroy()" >/dev/null 2>&1; then
  exec python3 c3resume_gui.py
fi
exec python3 c3resume_dialogs.py
