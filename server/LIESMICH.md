# Der c3resume-Server

**[English: README.md](README.md)**

Das macht nur die eine Person, die die Lobby eurer Gruppe betreibt. Die Spieler brauchen diesen Ordner nicht.

## Starten

```
bash start_server.sh
```

Lass das Terminal beim Spielen offen. **Strg+C** beendet den Server. Ein extra Setup gibt es nicht. Das Skript
startet zwei Programme zusammen:

| Programm | Port | Was es macht |
|---|---|---|
| der Lobby-Server (`sich_c3.lua`) | TCP 31523 | Räume, Chat und Partien, dazu die Befehle `!save`, `!autosave`, `!saves`, `!load` |
| der Spielstand-Dienst (`c3saves_server.py`) | TCP 31524 | Bewahrt die Spielstände des Hosts auf. Die Speicher-Helfer der Spieler laden sie hier hoch und herunter |

Jeder Spieler muss **beide Ports** auf diesem Computer erreichen. Mit Tailscale oder einem anderen VPN geht das von
selbst. Hinter einem Router beide Ports an diesen PC weiterleiten. Das Skript zeigt die Adressen dieses Computers
an; die Spieler tragen eine davon in ihr Setup-Fenster ein.

Nötig sind **Lua 5.1 mit LuaSocket** und **python3**. Fehlt etwas, nennt das Skript den Installationsbefehl
(Debian/Ubuntu/Mint: `sudo apt install lua5.1 lua-socket`; Arch/SteamOS: `sudo pacman -S lua51 lua51-socket`).

## Wo die Dateien liegen

Alles bleibt in diesem Ordner, in `data/`, das beim ersten Start angelegt wird:

```
data/saves/          die Spielstände (alte können hier gelöscht werden)
data/register.store  die Lobby-Konten der Spieler
data/recordings/     eine Aufzeichnung jeder Partie
data/server.log      das Log der Lobby
data/saves.log       das Log des Spielstand-Dienstes
data/config.store    Einstellungen (siehe unten)
```

Sonst wird nirgends etwas installiert.

## Einstellungen

`data/config.store` wird beim ersten Start angelegt. Um alle 10 statt alle 5 Minuten zu speichern,
`autosave_seconds = 600,` in `commands = { ... }` ergänzen:

```
commands = { bot = { nick = "C3Lab" }, saves_dir = "saves", autosave_seconds = 600 },
```

`bot.nick` ist der Name des „Spielers“, der im Chat auf Befehle antwortet. Nach einer Änderung den Server neu
starten.

## Aktualisieren

Den Server beenden, die neue Version **über** diesen Ordner entpacken (Dateien ersetzen) und wieder starten. Der
Ordner `data/` ist nicht in der Zip-Datei, Spielstände und Konten bleiben also erhalten. Du kannst auch woanders
entpacken und `data/` in den neuen `server`-Ordner verschieben.

## Woher der Server weiß, wer einen Speicher-Helfer hat

Jeder Speicher-Helfer fragt den Spielstand-Dienst alle 5 Sekunden nach seiner Liste. Der Dienst schreibt die
Adressen, die er gesehen hat, nach `data/saves/helpers.txt`. Hat die Adresse eines Spielers in den letzten 2 Minuten
nicht gefragt, behandelt der Server diesen Spieler als einen ohne Helfer. Er wartet dann nicht auf einen Download
von diesem PC und sagt im Chat, dass der Spielstand von Hand kopiert werden muss. Spieler, die sich eine
Internetadresse teilen, sehen hier wie ein einziger Spieler aus.
