#!/usr/bin/env bash
# start_server.sh - the private Cossacks 3 lobby with c3resume (!save, !autosave, !saves, !load).
#
#   bash start_server.sh        (leave the terminal open; Ctrl+C stops the server)
#
# Everything stays in this folder: the server keeps its files in  data/  next to this script
# (saves, player accounts, recordings, logs). Nothing is installed anywhere else.
# The first start takes over the saves and player accounts of an older setup in ~/c3-lab, if there is one.
# Needs Lua 5.1 with LuaSocket, and python3.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="$HERE/data"
OLD="$HOME/c3-lab/server"

die() { printf '\nPROBLEM: %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- tools
LUA=""
for cand in lua5.1 lua51 lua; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -v 2>&1 | grep -q "Lua 5\.1"; then
    if "$cand" -e 'require("socket")' >/dev/null 2>&1; then LUA="$cand"; break; fi
  fi
done
if [ -z "$LUA" ]; then
  cat >&2 <<'EOF'

PROBLEM: need Lua 5.1 together with the LuaSocket library, and could not find a working pair.
  Debian / Ubuntu / Mint / Pop!_OS :  sudo apt install lua5.1 lua-socket
  Arch / Manjaro / SteamOS         :  sudo pacman -S lua51 lua51-socket
Then run this script again. (It must be Lua 5.1, not 5.3 / 5.4.)
EOF
  exit 1
fi
command -v python3 >/dev/null 2>&1 || die "python3 is missing. Debian/Ubuntu/Mint: sudo apt install python3"
[ -f "$HERE/sich_c3.lua" ] && [ -f "$HERE/c3saves_server.py" ] || die "sich_c3.lua or c3saves_server.py is missing next to this script - unzip the whole folder."

# ---------------------------------------------------------------- first start: the data folder
if [ ! -d "$DATA" ]; then
  echo "First start: creating $DATA"
  mkdir -p "$DATA/saves" "$DATA/recordings"
  if [ -d "$OLD" ]; then
    echo "Taking over from the older setup in $OLD:"
    if [ -d "$OLD/saves" ]; then cp -p "$OLD/saves/"* "$DATA/saves/" 2>/dev/null || true; echo "  saves: $(ls "$DATA/saves" | grep -c '\.map\.gz$' || true)"; fi
    for f in register.store matches.jsonl; do
      if [ -f "$OLD/$f" ]; then cp -p "$OLD/$f" "$DATA/$f"; echo "  $f"; fi
    done
    echo "  (the old match recordings stay in $OLD/recordings; when all is fine you can delete ~/c3-lab)"
  fi
fi
if [ ! -f "$DATA/config.store" ]; then
cat > "$DATA/config.store" <<'EOF'
io.stdout:setvbuf("line")      -- write each log line at once
return {
	host = "*",
	port = 31523,
	log  = { level = "info", output = io.output() },
	echo = nil,

	-- every packet of every started room is recorded here (QLREC1 files); paths are inside the data folder
	recordings = "recordings",
	matchlog   = "matches.jsonl",
	status     = "status.json",

	-- chat commands: !pause !unpause !save !autosave !saves !load !help ...
	-- the autosave interval: add  autosave_seconds = 300,  inside commands = { ... }
	commands = { bot = { nick = "C3Lab" }, saves_dir = "saves" },
}
EOF
fi
# the server keeps its .store files (config, player accounts) next to the script it runs: run a copy in data/
cp "$HERE/sich_c3.lua" "$DATA/sich.lua"

# ---------------------------------------------------------------- start
cd "$DATA"
python3 "$HERE/c3saves_server.py" --dir "$DATA/saves" >> saves.log 2>&1 &
SAVES_PID=$!
trap 'kill $SAVES_PID 2>/dev/null' EXIT
echo
echo "Cossacks 3 lobby on TCP 31523, save service on TCP 31524 (players must reach both ports)."
echo "Files: $DATA   (logs: server.log, saves.log)"
if command -v hostname >/dev/null 2>&1; then echo "This computer's addresses: $(hostname -I 2>/dev/null || true)"; fi
echo "Ctrl+C stops the server."
echo
"$LUA" sich.lua 2>&1 | tee -a server.log
