# c3resume: Eine Cossacks-3-Mehrspieler-Partie speichern und an einem anderen Tag zu Ende spielen

**[English guide: README.md](README.md)**

Cossacks 3 kann Mehrspieler-Partien nicht speichern. Dauert eine Partie lange, muss man sie meist abbrechen oder
bis zum Ende durchspielen. c3resume schließt diese Lücke. Irgendein Spieler tippt `!save` oder drückt einen Knopf
im F10-Menü. An einem anderen Tag starten dieselben Spieler eine neue Partie, tippen `!load 1` und spielen dort
weiter, wo sie aufgehört haben: dieselbe Karte, dieselben Armeen, dieselben Nationen, und der Chat funktioniert.

Es ist ein inoffizielles Fan-Projekt für Freundesgruppen, die auf ihrem **eigenen Lobby-Server** spielen. Auf dem
offiziellen Server funktioniert es nicht.

---

## Inhalt

1. [So funktioniert es, kurz gesagt](#1-so-funktioniert-es-kurz-gesagt)
2. [Was ihr braucht](#2-was-ihr-braucht)
3. [Herunterladen](#3-herunterladen)
4. [Den Server einrichten (eine Person)](#4-den-server-einrichten-eine-person)
5. [Auf jedem Spieler-PC installieren](#5-auf-jedem-spieler-pc-installieren)
6. [Der Speicher-Helfer: installieren oder nicht?](#6-der-speicher-helfer-installieren-oder-nicht)
7. [Spielen: speichern und weiterspielen](#7-spielen-speichern-und-weiterspielen)
8. [Ohne Speicher-Helfer: einen Spielstand von Hand kopieren](#8-ohne-speicher-helfer-einen-spielstand-von-hand-kopieren)
9. [Wenn etwas nicht klappt](#9-wenn-etwas-nicht-klappt)
10. [Aktualisieren und deinstallieren](#10-aktualisieren-und-deinstallieren)
11. [Ist das sicher?](#11-ist-das-sicher)
12. [Für Entwickler](#12-für-entwickler)
13. [Lizenz und Danksagung](#13-lizenz-und-danksagung)

---

## 1. So funktioniert es, kurz gesagt

Es gibt drei Teile:

- **Der Server.** Eine Person in eurer Gruppe betreibt auf einem Linux-PC einen kleinen Lobby-Server. Das Spiel aller
  Spieler verbindet sich damit statt mit dem offiziellen Server. Er versteht die Chat-Befehle `!save`, `!autosave`,
  `!saves` und `!load` und bewahrt eine Kopie jedes Spielstands auf.
- **Das Installationsprogramm.** Jeder Spieler führt es einmal aus. Es ändert ein paar Skript-Dateien des Spiels
  auf diesem PC, damit das Spiel mitten in einer Mehrspieler-Partie einen Spielstand laden kann. Außerdem stellt es
  das Spiel auf euren Server um.
- **Der Speicher-Helfer** (freiwillig, empfohlen). Dieses kleine Hintergrundprogramm schickt die Spielstände des
  Hosts zum Server und holt sie für alle anderen, wenn eine Partie geladen wird. Ohne ihn kopiert ihr Spielstände
  von Hand (siehe [Abschnitt 8](#8-ohne-speicher-helfer-einen-spielstand-von-hand-kopieren)).

Beim Speichern schreibt nur das Spiel des **Hosts** einen Spielstand. Beim Laden lädt **jeder** PC genau diese
Datei, so starten alle Spiele wieder vom exakt gleichen Stand.

## 2. Was ihr braucht

| Wer | Was |
|---|---|
| Alle | Cossacks 3 auf Steam, unter Windows 10/11 oder Linux (Steam mit Proton oder die native Linux-Version) |
| Alle | Eine Verbindung zum Server-PC: dasselbe Heimnetz, oder [Tailscale](https://tailscale.com) (kostenlos, am einfachsten), oder weitergeleitete Ports |
| Wer den Server betreibt | Einen Linux-PC, der beim Spielen läuft, mit Python 3, Lua 5.1 und LuaSocket |
| Linux-Spieler | Python 3 (fast jedes Linux hat es) |

Alle Spieler einer Partie sollten **dieselbe c3resume-Version** installiert haben.

## 3. Herunterladen

Ladet die neueste Zip-Datei von der Seite **[Releases](../../releases)** herunter. Ihr könnt auch den grünen Knopf
**Code** und dann **Download ZIP** nehmen. Danach **entpacken**:

- **Windows:** Rechtsklick auf die Zip-Datei, dann **Alle extrahieren...**, dann **Extrahieren**. Startet nichts
  direkt aus der Zip-Datei heraus, das funktioniert nicht.
- **Linux:** Rechtsklick auf die Zip-Datei, dann **Hier entpacken**.

Darin findet ihr:

```
installer-windows/   für Spieler unter Windows
installer-linux/     für Spieler unter Linux
server/              nur für die Person, die den Server betreibt
tools/               Hilfen zur Fehlersuche
```

## 4. Den Server einrichten (eine Person)

Das macht nur eine Person in der Gruppe. Nehmt einen Linux-PC, der beim Spielen eingeschaltet bleibt. Es kann auch
der PC eines Spielers sein.

1. Installiere die drei Dinge, die der Server braucht. Unter Debian, Ubuntu, Mint oder Pop!_OS:

   ```
   sudo apt install python3 lua5.1 lua-socket
   ```

   Unter Arch, Manjaro oder SteamOS: `sudo pacman -S python lua51 lua51-socket`. Auf anderen Systemen: Lua **5.1**
   (nicht 5.3 oder 5.4) und LuaSocket für Lua 5.1 installieren.
2. Öffne den Ordner `server`, mach einen Rechtsklick auf eine freie Stelle und wähle **Im Terminal öffnen**. Tippe:

   ```
   bash start_server.sh
   ```

   Lass dieses Fenster beim Spielen offen. **Strg+C** beendet den Server. Fehlt etwas, sagt das Skript dir, was du
   installieren musst.
3. Das Skript zeigt die Adressen dieses PCs an. Gib deinen Spielern die richtige:
   - Mit **Tailscale** ist es die, die mit `100.` anfängt (zum Beispiel `100.90.34.72`). Jeder Spieler installiert
     Tailscale und tritt demselben Netzwerk bei.
   - Im selben Heimnetz ist es die lokale Adresse (zum Beispiel `192.168.1.20`).
   - Über das Internet ohne Tailscale: im Router die **TCP-Ports 31523 und 31524** an diesen PC weiterleiten und
     die öffentliche Adresse weitergeben.

Alles, was der Server speichert, bleibt in `server/data/`: Spielstände, Spielerkonten, Aufzeichnungen und Logs.
Mehr Details stehen in [server/LIESMICH.md](server/LIESMICH.md).

## 5. Auf jedem Spieler-PC installieren

Schließe vorher Cossacks 3.

### Windows

1. Öffne den entpackten Ordner, dann `installer-windows`.
2. Doppelklicke auf **`SETUP - double-click me.bat`**.
   - Erscheint ein blaues Fenster *„Der Computer wurde durch Windows geschützt“*, klicke auf **Weitere
     Informationen**, dann auf **Trotzdem ausführen**. Das kommt, weil die Datei aus dem Internet stammt und nicht
     signiert ist.
   - Fragt Windows *„Möchten Sie zulassen, dass durch diese App Änderungen an Ihrem Gerät vorgenommen werden?“*,
     klicke auf **Ja**. Der Spiel-Ordner ist geschützt, wenn Steam unter „Programme“ installiert ist, und das ist
     der übliche Ort.
3. Das Setup-Fenster öffnet sich.

### Linux

1. Öffne den entpackten Ordner, dann `installer-linux`.
2. Mach einen Rechtsklick auf eine freie Stelle, wähle **Im Terminal öffnen** und tippe:

   ```
   bash setup-linux.sh
   ```

3. Das Setup-Fenster öffnet sich. Fehlt deinem System Tk (häufig bei Fedora und Bazzite), bekommst du dieselben
   Fragen stattdessen als ein paar einfache Dialogfenster, und die funktionieren genauso gut. Für das volle Fenster
   installiere Tk: `sudo dnf install python3-tkinter` (Fedora) oder `sudo apt install python3-tk` (Debian/Ubuntu).

### Im Setup-Fenster (beide Systeme)

- **Language / Sprache:** oben rechts English oder Deutsch wählen. Das Fenster merkt sich die Wahl.
- **1. Dein Cossacks-3-Ordner:** wird automatisch gefunden. Nur wenn es heißt, das Spiel wurde nicht gefunden, auf
  **Ändern...** klicken und den Ordner wählen. In Steam: Rechtsklick auf Cossacks 3, dann **Verwalten**, dann
  **Lokale Dateien durchsuchen**.
- **2. Server-Adresse:** die Adresse eintragen, die dir die Server-Person gegeben hat, zum Beispiel
  `100.90.34.72`.
- **3. Speicher-Helfer:** den Haken drin lassen, außer du hast einen Grund dagegen. Siehe nächster Abschnitt.
- **4. Installieren.** Steht oben grün **Fertig**, bist du fertig.

Nach einem Spiel-Update oder nach **Dateien auf Fehler überprüfen** in Steam das Setup noch einmal öffnen. Es sagt
dir dann, dass du **Neu installieren** klicken sollst.

## 6. Der Speicher-Helfer: installieren oder nicht?

Der Speicher-Helfer ist ein kleines Programm ohne Fenster. Er startet mit dem Computer und spricht nur mit dem
Server eurer Gruppe. Er hat zwei Aufgaben:

- Bist **du der Host** und die Partie wird gespeichert, lädt er den Spielstand auf den Server hoch.
- Wird eine Partie **geladen**, holt er diesen Spielstand vom Server auf deinen PC.

**Mit dem Helfer (empfohlen):** alles passiert von selbst. Tippt `!load 1`, und der Server sorgt dafür, dass jeder
PC den Spielstand hat, bevor er lädt.

**Ohne den Helfer:** im Hintergrund läuft nichts, aber Spielstände werden nicht von selbst verteilt. Ein
Spielstand bleibt auf dem PC des Hosts. Bevor ihr eine Partie fortsetzen könnt, muss der Host die
Spielstand-Datei an jeden Spieler schicken, und jeder legt sie in seinen eigenen Spielstände-Ordner.
[Abschnitt 8](#8-ohne-speicher-helfer-einen-spielstand-von-hand-kopieren) erklärt, wie das geht.

Ihr könnt beides in einer Gruppe mischen. Zum Beispiel nutzen der Host und ein Freund den Helfer, und ein anderer
Freund kopiert von Hand. Der Server sagt im Chat, wem die Datei noch fehlt.

Du kannst dich jederzeit umentscheiden: Setup öffnen, Haken setzen oder entfernen, **Neu installieren** klicken.

Wo seine Log-Datei liegt: Windows `%LOCALAPPDATA%\c3resume\helper.log`, Linux `~/.local/share/c3resume/helper.log`.

## 7. Spielen: speichern und weiterspielen

### Knöpfe und Befehle

Drücke in einer Partie **F10**. Im Menü gibt es vier neue Knöpfe. Du kannst auch den passenden Befehl in den Chat
tippen:

| Knopf | Chat-Befehl | Was er macht |
|---|---|---|
| Partie speichern | `!save` | Pausiert die Partie für alle, das Spiel des Hosts speichert, und die Partie geht weiter (ein paar Sekunden) |
| Autospeichern (5 Min.) an/aus | `!autosave` | Speichert alle 5 Minuten. Nur der neueste Auto-Spielstand bleibt |
| Gespeicherte Partien | `!saves` | Zeigt die Spielstände, neueste zuerst, mit Nummer |
| Neueste Partie laden | `!load 1` | Lädt Spielstand Nummer 1 auf jedem PC |

Jeder Spieler kann sie benutzen. Die Speicher-Pause zählt nicht zu deinen `!pause`-Pausen.

### An einem anderen Tag weiterspielen

1. **Dieselben Spieler**, mit denselben Spielernamen, treffen sich auf eurem Server. Der Host macht einen Raum auf.
   Karte, Nationen und Teams sind egal, weil der Spielstand das alles ersetzt. Nehmt die kleinste Karte, dann
   startet die Partie schneller. Dann die Partie starten.
2. Tippt `!saves`. Ihr seht eine Liste wie diese:

   ```
   1)  09.10. 21:30   Freitagsspiel   Aaron, Iven, Leonie
   2)  02.10. 20:15   [auto] Große Karte   Aaron, Iven
   ```

3. Tippt `!load 1`, oder F10 und **Neueste Partie laden**. Der Server prüft, ob jeder PC den Spielstand hat (die
   Helfer laden ihn jetzt herunter, und ein großer Spielstand kann ein paar Minuten dauern). Dann pausiert er, lädt
   den Spielstand überall und macht von selbst weiter, sobald alle geladen haben.

Gut zu wissen:

- **Einmal laden pro Partie.** Ein zweites Laden in derselben Partie kann die anderen PCs einfrieren, darum lehnt
  der Server es ab. Zum erneuten Laden verlassen alle die Partie, der Host macht einen neuen Raum auf, startet ihn
  und tippt wieder `!load`.
- **Ein Tippfehler schadet nicht.** `!load 7` ohne Spielstand Nummer 7 bringt dir nur eine Nachricht, und die
  Partie läuft weiter.
- Alle laden die Datei des **Hosts**. Es ist also egal, wer letztes Mal Host war und an welchem PC jemand saß.
- In `!saves` markiert `[auto]` den Auto-Spielstand und `[nur Host-PC]` einen Spielstand, den nur der Host hat
  (kein Helfer hat ihn hochgeladen).

## 8. Ohne Speicher-Helfer: einen Spielstand von Hand kopieren

Das braucht ihr nur, wenn der Host oder einige Spieler **ohne** Speicher-Helfer installiert haben.

**Der Host:**

1. Nach dem Speichern das Setup öffnen und auf **Spielstände-Ordner** klicken. Der Spielstand ist die neueste Datei
   mit einem Namen wie `qladder_20261009_213012_95min.map`. Der Chat zeigt den Namen auch beim Speichern an.
   Auto-Spielstände fangen mit `qladder_auto_` an.
2. Schick diese Datei an jeden Spieler. Spielstand-Dateien können groß sein (nach einer langen Partie Hunderte MB),
   also packe sie vorher: Rechtsklick auf die Datei, dann **Komprimieren** oder **Senden an > ZIP-komprimierter
   Ordner**. Dann die Zip-Datei über einen Cloud-Ordner (Google Drive, OneDrive, Dropbox), LocalSend oder einen
   USB-Stick teilen. Für Discord ist die Datei meistens zu groß.

**Jeder andere Spieler:**

1. Das Setup öffnen und auf **Spielstände-Ordner** klicken. Der Ordner wird angelegt, falls du noch nie gespeichert
   hast.
2. Die Datei dort hineinlegen. Hast du eine Zip-Datei bekommen, entpacke sie vorher, sodass die `.map`-Datei selbst
   in diesem Ordner liegt. Nicht umbenennen.

Dann weiter wie in [Abschnitt 7](#7-spielen-speichern-und-weiterspielen). Fehlt jemandem die Datei noch, sagt der
Server wem, zum Beispiel *„Der Spielstand ... ist nur auf dem PC des Hosts ... Diese Spieler brauchen eine Kopie
der Datei ...map in ihrem Spielstaende-Ordner: Iven“*, und es wird nichts geladen.

Wo der Spielstände-Ordner liegt, falls du ihn selbst suchen willst:

- **Windows:** `Dokumente\cossacks\profiles\<dein Profil>\saves`
- **Linux mit Proton:** `~/.local/share/Steam/steamapps/compatdata/333420/pfx/drive_c/users/steamuser/Documents/cossacks/profiles/<dein Profil>/saves`
- **Linux, native Version:** `~/cossacks/profiles/<dein Profil>/saves`

Spielt der Host ohne Helfer und benutzt Autospeichern, bleibt jeder Auto-Spielstand als eigene Datei auf dem PC des
Hosts. Alte ab und zu löschen.

## 9. Wenn etwas nicht klappt

**Das Setup-Fenster**

| Meldung | Was tun |
|---|---|
| „Cossacks 3 wurde nicht gefunden“ | **Ändern...** klicken und den Spiel-Ordner wählen (Steam: Rechtsklick auf Cossacks 3 > Verwalten > Lokale Dateien durchsuchen) |
| „ein Spiel-Update oder Steam hat es zurückgesetzt“ | **Neu installieren** klicken |
| „der Speicher-Helfer läuft NICHT“ | **Neu installieren** klicken. Bleibt es orange, den PC neu starten |
| „Windows did not allow changing the game files“ | Spiel schließen; noch einmal Installieren klicken und die Windows-Frage erlauben |

**Meldungen im Spiel-Chat**

| Meldung | Bedeutung und Lösung |
|---|---|
| „Kein Speicher-Helfer aktiv bei: NAME“ | Auf diesem PC läuft kein Helfer, er konnte den Spielstand nicht holen. Datei von Hand kopieren ([Abschnitt 8](#8-ohne-speicher-helfer-einen-spielstand-von-hand-kopieren)) oder dort den Helfer installieren |
| „Der Spielstand ... ist nur auf dem PC des Hosts“ | Der Host spielt ohne Helfer. Die genannten Spieler brauchen eine Kopie der Datei |
| „Diese PCs konnten den Spielstand nicht holen: NAME“ | Der Helfer dieses Spielers läuft, konnte den Spielstand aber nicht herunterladen. Prüfen, ob er den Server erreicht (Ports 31523 **und** 31524) |
| „Keine Antwort von: NAME“ | Dieser Spieler hat kein c3resume oder eine sehr alte Version. Die aktuelle installieren |
| „Lade den Spielstand noch herunter ...“ | Ein großer Spielstand über eine langsame Leitung. Warten; der Server wartet bis zu 10 Minuten |
| „Der Spielstand des Hosts kam nicht auf dem Server an“ | Der Helfer des Hosts läuft nicht, oder ein sehr großer Spielstand wird noch hochgeladen |
| „Diese Partie wurde schon einmal geladen“ | Einmal laden pro Partie. Verlassen, neuen Raum aufmachen, starten, dann `!load` |
| „Waehrend des Ladens ausgestiegen: NAME“ | Das Spiel ist beim Laden abgestürzt oder hat die Verbindung verloren. `!unpause` tippen, um ohne ihn weiterzuspielen, oder neu anfangen |

**Fehlersuche auf einem Windows-PC:** Rechtsklick auf `tools/c3diag.ps1` und **Mit PowerShell ausführen** wählen.
Nach etwa einer Minute liegt ein Bericht namens `c3resume-diagnose.txt` auf dem Desktop. Schick ihn der Person, die
den Server betreibt. Er enthält keine Passwörter und ersetzt deinen Windows-Benutzernamen durch `<user>`.

**Geht dem Spiel der Speicher aus? (Linux):** `python3 tools/c3mem.py 10` zeigt alle 10 Sekunden, wie nah Cossacks 3
an seiner 4-GB-Grenze ist.

Spieler, die sich eine Internetverbindung teilen (zum Beispiel bei einer LAN-Party, wenn der Server woanders
steht), sehen für den Server wie ein einziger Spieler aus. Dann kann er nicht erkennen, wer einen Helfer hat, und
wartet vielleicht auf Downloads, die nie kommen. Installiert den Helfer dann auf allen diesen PCs oder auf keinem.

## 10. Aktualisieren und deinstallieren

- **Aktualisieren (Spieler):** die neue Version herunterladen und entpacken, ihr Setup öffnen und auf
  **Aktualisieren** klicken. Alle in eurer Gruppe sollten aktualisieren.
- **Aktualisieren (Server):** den Server mit Strg+C beenden, die neue Version über den alten Ordner entpacken
  (Dateien ersetzen) und wieder starten. Euer Ordner `server/data/` ist nicht in der Zip-Datei, Spielstände und
  Konten bleiben also erhalten.
- **Deinstallieren (Spieler):** das Setup öffnen und auf **Deinstallieren** klicken. Jede geänderte Spieldatei wird
  wieder zum Original, das Spiel benutzt wieder den offiziellen Server, und der Speicher-Helfer wird entfernt.

## 11. Ist das sicher?

- c3resume ändert **ein paar Text-Skriptdateien** des Spiels auf deinem PC. Das Programm selbst (`cossacks.exe`)
  rührt es nicht an. Bevor es etwas ändert, bewahrt es das Original im Ordner `c3backup` im Spiel-Ordner auf, und
  Deinstallieren stellt es exakt wieder her.
- Der Speicher-Helfer spricht nur mit der Server-Adresse, die du eingetragen hast, und bewegt nur Spielstand-Dateien
  namens `qladder_...`.
- Nichts liest deine Passwörter oder dein Steam-Konto.
- Dieses Projekt enthält keine Dateien des Spiels. Alles wird auf deinem eigenen PC geändert, in deiner eigenen
  Kopie des Spiels.
- Es ist ein inoffizielles Fan-Projekt. Die Nutzung erfolgt auf eigenes Risiko. Es wurde viel damit gespielt, aber
  es kann keine Abstürze des Spiels selbst beheben.

## 12. Für Entwickler

Die Übersicht über die Dateien, die Prüfungen (`dev/check.py`), den Simulator (`dev/sim/sim.py`) und wie eine neue
Version veröffentlicht wird, steht in der englischen [README.md, Abschnitt 12](README.md#12-for-developers). Die
technischen Details stehen in [docs/how-it-works.md](docs/how-it-works.md).

## 13. Lizenz und Danksagung

c3resume steht unter der **MIT-Lizenz** (siehe [LICENSE](LICENSE)).

Der Lobby-Server basiert auf **[Sich](https://github.com/3skcassoc/sich)** von 3skcassoc und dessen Fork
**[qossacks_4](https://github.com/kewl-ua/qossacks_4)** von kewl-ua, beide unter der WTFPL. Die Beschreibung des
Lobby-Protokolls in **[cossacks_3_net_spec](https://github.com/kewl-ua/cossacks_3_net_spec)** war eine große Hilfe.
Alles über Code von anderen, und was *nicht* enthalten ist, steht in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Cossacks 3 ist ein Spiel von GSC Game World. Dieses Projekt steht in keiner Verbindung zu GSC Game World und wird
nicht von GSC Game World unterstützt.
