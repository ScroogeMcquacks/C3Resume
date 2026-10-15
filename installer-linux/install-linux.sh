#!/usr/bin/env bash
# c3resume setup in the terminal (the same questions as the setup window):  bash install-linux.sh
cd "$(dirname "$(readlink -f "$0")")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is missing. Install it with your package manager (e.g. sudo dnf install python3 / sudo apt install python3)."
  exit 1
fi
exec python3 c3resume_dialogs.py --terminal
