# Postavljanje C3Resume servera na dva Windows 11 računala

Verzija: c3resume 2.2 + launcher iz ovog repozitorija. **Ista verzija c3resume moda mora biti na
oba PC-a.** Server i igra na PC1, drugi igrač na PC2.

## 1. Server (PC1)

1. Dvoklik: `launcher\Start-C3Server.cmd`
2. U ispisu nađi `LAN address(es)` — npr. `192.168.1.89 (Ethernet 2)`. **Tu adresu** (ne
   `127.0.0.1`, ne VPN adresu) daj igraču na PC2.
3. Provjera da save servis radi (u drugom prozoru): `Start-C3Server.cmd -Diag`
   → očekivano: `[ok] GET /c3/list -> HTTP 200` i `the save service is reachable`.
4. Zaustavljanje: **Ctrl+C** u prozoru, ili `Start-C3Server.cmd -Stop`.
5. Podaci (saveovi, logovi) su u `%LOCALAPPDATA%\C3ResumeServer` — ne u OneDrive-u.

## 2. Klijentski mod (oba PC-a)

Instalira se **isključivo postojećim službenim installerom** (ne mijenja se `cossacks.exe`):

1. Zatvori Cossacks 3.
2. Dvoklik: `installer-windows\SETUP - double-click me.bat` (ako Windows upozori: *More info → Run anyway*).
3. U prozoru: mapa igre (nađe sam), **server address = LAN IPv4 s PC1**, ostavi kvačicu za save
   helper, klikni **Install**. Zeleno „Ready“ = uspjeh.
4. Installer sam postavi `data\resources\servers.dat` i napravi backup u `<igra>\c3backup`.
   Ručno (ako ikad treba) sadržaj `data\resources\servers.dat` je:

   ```
   section.begin
   * = 192.168.1.89:31523
   section.end
   ```

   (zamijeni adresu stvarnom). Deinstalacija vraća original.

## 3. Windows Firewall (samo PC1)

Launcher **ne mijenja firewall**. Ako PC2 ne može pristupiti, u administratorskom promptu jednom:

```
netsh advfirewall firewall add rule name="C3Resume lobby TCP 31523" dir=in action=allow protocol=TCP localport=31523
netsh advfirewall firewall add rule name="C3Resume saves TCP 31524" dir=in action=allow protocol=TCP localport=31524
netsh advfirewall firewall add rule name="C3Resume echo UDP 31523"  dir=in action=allow protocol=UDP localport=31523
```

Za igru na istom PC-u (127.0.0.1) pravila nisu potrebna.

## 4. Ručni test (obavezno s dvije prave igre)

A. Pokreni server na PC1 (`Start-C3Server.cmd`).
B. Oba igrača pokrenu igru, prijave se (nadimak u polje „game key“) — oba vide lobby.
C. Host napravi sobu, oba uđu, host pokrene meč.
D. U chatu upiši `!save` (ili F10 gumb). Pričekaj potvrdu „safe on the server“.
E. `!saves` → save mora biti na popisu **bez** oznake `[host PC]`.
F. Izađi iz igre, zaustavi server (Ctrl+C), pa ga ponovno pokreni.
G. Ista dva igrača naprave **novu** sobu i pokrenu meč.
H. U chatu: `!load 1` (ili ime s popisa).
I. Obje igre moraju prijeći na isto stanje; chat mora raditi dalje.
J. Ponovi `!save`, izađi, restartaj server, `!load` — mora raditi i drugi put.

Napomena: korak J je sada moguć jer je popravljen `os.rename` (prije je drugi `!load` u istom
data folderu mogao ostati bez prijenosa savea).

## 5. Poznata ograničenja

* **Jedan `!load` po meču.** Drugi `!load` u istom meču se odbija (može zamrznuti klijente).
  Za novi load: izađi iz meča i pokreni novu sobu.
* **Ista verzija c3resume na svim PC-jevima** (2.2); starija verzija ne odgovara na `#c3check`.
* **Automatski prijenos savea traži save helper** na PC-u. Bez helpera host mora datoteku poslati
  ručno (`Documents\cossacks\profiles\<profil>\saves`).
* **Veliki saveovi**: 50–100 MB; upload/download može trajati minutama (server čeka do 10 min).
* **Helper se prepoznaje po IP adresi** — igrači iza istog NAT-a izgledaju kao jedan.
* Nakon nadogradnje igre ili Steam „Verify integrity“ treba ponovno pokrenuti installer.
* Server ne mijenja firewall, ne instalira servise i ne dira igru, Steam ni licence.
* `status.json` se osvježava svakih ~5 s (na Windowsu do sada nije — popravljeno u `sich_c3.lua`).
