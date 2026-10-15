#!/usr/bin/env python3
"""
c3resume - save a running Cossacks 3 multiplayer match and continue it later.

This installer changes a few of the game's own script files on YOUR computer (originals are kept in
<game folder>/c3backup and come back with "uninstall"). Nothing from the game is shipped with it.

  python3 c3resume.py install                 install (or update) the mod
  python3 c3resume.py install --server 1.2.3.4   ... and point the game at that lobby server
  python3 c3resume.py install --no-helper     ... without the save helper (saves are then copied by hand)
  python3 c3resume.py uninstall               put every original file back
  python3 c3resume.py status                  is it installed?
  python3 c3resume.py saves                   show (and open) the folder with your saved games
  python3 c3resume.py helper                  the save-sync helper (install starts it, and at every login)
  python3 c3resume.py export patches.json     (for developers: write the patch data used by c3resume.ps1)

Options:  --game-dir "/path/to/Cossacks 3"    if the game folder is not found automatically
          --diag                              also write diagnostic lines to the game log
Standard library only, Python 3.6+.
"""
import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import gzip
import urllib.request
import urllib.error
import sys
import time
from pathlib import Path

VERSION = "2.2"
BACKUP_DIR = "c3backup"
SERVERS_DAT = "data/resources/servers.dat"
SHOWMENU = "data/gui/menu.inc/showmenu.inc"
MENU_AIX = "data/gui/menu.aix"
READLOAD = "data/gui/menu.inc/readload.inc"
DOCREATE = "data/gui/menu.inc/docreate.inc"
DOPROGRESS = "data/gui/menu.inc/doprogress.inc"
ONLOADFULL = "data/scripts/common.inc/onloadfull.inc"
DMGLOBAL = "data/scripts/dmscript.global"
GLOBAL_INC = "data/scripts/units/global.inc/"
SESSION_INC = "data/gui/menu.inc/onlaneventsession.inc"
EVENTMENU = "data/gui/menu.inc/eventmenu.inc"
NET_SCRIPT = "data/scripts/lib/net.script"
ONLOAD = "data/scripts/common.inc/onload.inc"


def say_chat(text_expr):
    """Script code that sends a room chat line (the server reads lines starting with #c3 and hides them)."""
    return ["c3lang := '';",
            "_profile_ConvertConfigValueToLocale(gProfile.lang, c3lang);",
            "LanPublicServerSendSessionMessage(0, IntToStr(gc_chatmessage_mode_all)+gc_gui_delimitercharstr+c3lang+#7+%s);" % text_expr]
TRACED = ["WriteOrder", "ReadOrder", "WriteMove", "ReadMove", "WriteConstruct", "ReadConstruct"]


def code(lines):
    """Lines of a state's Code block (the game prefixes every code line with "[*] = ;")."""
    return "\n".join("      [*] = ;" + ln for ln in lines)


# =============================================================================== the patch data
# Text uses "\n"; the installers convert it to the file's own line ending (the game's files use CRLF).

def patch_list(diag):
    P = []

    def add(name, rel, anchor, repl):
        P.append({"name": name, "file": rel, "anchor": anchor, "replace": repl})

    # 2. readload: the network record ReadLoad (state 71, right after ReadSave) - the server's !load <name> sends it
    def block(name, f):
        return "\n".join(["section.begin", "   Name = " + name, "   LanClientExecute = True",
                          "   UsedFile = True", "   UsedFileName = .\\data\\gui\\menu.inc\\" + f, "section.end"])
    add("readload", MENU_AIX, block("ReadSave", "readsave.inc"),
        block("ReadSave", "readsave.inc") + "\n\n" + block("ReadLoad", "readload.inc"))

    # 3. online-load repair, appended to OnLoadFull
    lines = [
        "",
        "// c3resume: a save was loaded inside a RUNNING online match. Make this machine's game work online again.",
        "if (_net_IsOnline) and (gMap.gamestage<>gc_map_gamestage_waitingloading) then",
        "begin",
        "   var c3i : Integer;",
        "   var c3k : Integer;",
        "   var c3h : Integer;",
        "   Log('c3resume OnLoadFull: online load, t='+FloatToStr(GetGameTime)+' server='+BoolToStr(_net_IsServer)+' ready='+BoolToStr(IsLanReady)+' myid='+IntToStr(LanMyInfoID));",
        "   // the repairs the game itself makes when it loads a .map into an online match (InitMapHistoricalBattle):",
        "   // service players get their control mode back, the 'progress' player (economy, network sync) runs online again",
        "   c3h := GetPlayerHandleByName(gc_racename_env);",
        "   if (c3h<>0) then",
        "   SetPlayerControlModeByHandle(c3h, 'cmPC');",
        "   c3h := GetPlayerHandleByName(gc_racename_misc);",
        "   if (c3h<>0) then",
        "   begin",
        "      SetPlayerControlModeByHandle(c3h, 'cmPC');",
        "      _player_ResetSaveLoadStates(c3h);",
        "      for c3i:=0 to gc_MaxPlayerCount-1 do",
        "      AddPlayerEnemyPlayerByHandle(c3h, GetPlayerHandleByIndex(c3i));",
        "   end;",
        "   c3h := GetPlayerHandleByName(gc_racename_progress);",
        "   if (c3h<>0) then",
        "   begin",
        "      SetPlayerControlModeByHandle(c3h, 'cmPC');",
        "      SetPlayerProgressOnLanByHandle(c3h, True);",
        "      _player_ResetSaveLoadStates(c3h);",
        "      SetPlayerProgressOnEditByHandle(c3h, True);",
        "   end;",
        "   c3h := GetPlayerHandleByName(gc_plname_pool);",
        "   if (c3h<>0) then",
        "   begin",
        "      SetPlayerControlModeByHandle(c3h, 'cmPC');",
        "      _player_ResetSaveLoadStates(c3h);",
        "      for c3i:=0 to gc_MaxPlayerCount-1 do",
        "      AddPlayerEnemyPlayerByHandle(c3h, GetPlayerHandleByIndex(c3i));",
        "   end;",
        "   // game players: control mode 'player', player data initialised",
        "   for c3i:=0 to gc_MaxPlayerCount-1 do",
        "   begin",
        "      c3h := GetPlayerHandleByIndex(c3i);",
        "      if (c3h<>0) and (GetPlayerRaceNameByHandle(c3h)=gc_racename_units) then",
        "      begin",
        "         if (GetPlayerControlModeIntByHandle(c3h)=0) then",
        "         SetPlayerControlModeIntByHandle(c3h, 2);",
        "         if (StateMachineGetArgDataByInd(GetPlayerStateMachineHandle(c3h), gc_argplayer_plr)=nil) then",
        "         PlayerExecuteStateByHandle(c3h, 'Initial');",
        "         _player_ResetSaveLoadStates(c3h);",
        "      end;",
        "   end;",
        "   // lobby ids can change between sessions: find every human player of the save again by nickname",
        "   for c3i:=0 to gc_MaxPlayerCount-1 do",
        "   if (gMap.players[c3i].bexists) and (gMap.players[c3i].bhuman) and (gMap.players[c3i].name<>'') then",
        "   begin",
        "      c3h := gMap.players[c3i].lanid;",
        "      if (gMap.players[c3i].name=LanMyInfoName) then",
        "      c3h := LanMyInfoID",
        "      else",
        "      for c3k:=0 to LanGetClientsCount-1 do",
        "      if (LanGetClientNameByIndex(c3k)=gMap.players[c3i].name) then",
        "      begin",
        "         c3h := LanGetClientIDByIndex(c3k);",
        "         break;",
        "      end;",
        "      if (c3h<>gMap.players[c3i].lanid) then",
        "      begin",
        "         Log('c3resume OnLoadFull: player '+IntToStr(c3i)+' '+gMap.players[c3i].name+' lobby id '+IntToStr(gMap.players[c3i].lanid)+' -> '+IntToStr(c3h));",
        "         gMap.players[c3i].lanid := c3h;",
        "      end;",
        "   end;",
        "   // this machine controls the nation of its own lobby id (not the nation the saver played)",
        "   for c3i:=0 to gc_MaxPlayerCount-1 do",
        "   if (gMap.players[c3i].bexists) and (gMap.players[c3i].lanid=LanMyInfoID) then",
        "   begin",
        "      gbool_gui_bspectator := (gMap.players[c3i].cid=gc_spectator_countryid);",
        "      _control_SetPlayer(c3i);",
        "      Log('c3resume OnLoadFull: this machine (lobby id '+IntToStr(LanMyInfoID)+') controls player '+IntToStr(c3i));",
        "      break;",
        "   end;",
        "end;",
    ]
    last = "      [*] = ;//ExecuteState('InitMapGen');"
    add("onlineload", ONLOADFULL, last + "\n   struct.end", last + "\n" + code(lines) + "\n   struct.end")

    # 4. session: the GUI is rebuilt by a load and falls back to the lobby network handler -> put the in-match one back
    a = "\n".join(["      [*] = ;if (gMap.gamestage=gc_map_gamestage_waitingloading) then",
                   "      [*] = ;begin",
                   "      [*] = ;   if (_net_IsOnline) then",
                   "      [*] = ;   SetGUIEventStateOnLanChange('OnLanEventSession');",
                   "      [*] = ;end;"]) + "\n"
    lines = [
        "// c3resume: after a save was loaded inside a running online match the GUI is rebuilt and its network handler",
        "// falls back to the lobby one. Put the in-match handler back (chat, clock sync) and restart the sync timers.",
        "if (gMap.gamestage<>gc_map_gamestage_waitingloading) and (_net_IsOnline) and (gInterface.gamemode<>gc_gamemode_mainmenu) then",
        "begin",
        "   SetGUIEventStateOnLanChange('OnLanEventSession');",
        "   gfloat_gui_lanlastgametimesyncreceived := 0;",
        "   gfloat_gui_lanlastgametimesync := 0;",
        "   gfloat_lan_lastsyncrestime := 0;",
        "   gfloat_lan_lastsyncstatstime := 0;",
        "   gfloat_lan_lastsyncdatatime := 0;",
        "   Log('c3resume DoCreate: in-match network handler set, t='+FloatToStr(GetGameTime));",
        "   // the 'loaded' report goes out from DoProgress, once the game loop really runs again (see there)",
        "   if (gstring_c3resume_load<>'') then",
        "   gfloat_c3resume_loadedat := _misc_GetRealTime;",
        "end;",
    ]
    add("session", DOCREATE, a, a + code(lines) + "\n")

    # 5. globals: the name of a load in progress (read by DoCreate after the load)
    a = "   gbool_recordwascleared = Boolean\n"
    add("globals", DMGLOBAL, a, a + "   // c3resume (c3resume installer): the save being loaded, and the load DoProgress still has to start\n"
        "   gstring_c3resume_load = String\n   gstring_c3resume_pending = String\n"
        "   // c3resume: True while our load clears away the running match (see the OnDestroy patches)\n"
        "   gbool_c3resume_unloading = Boolean\n   gfloat_c3resume_unloadstart = Float\n"
        "   // c3resume: when DoCreate ran after our load (DoProgress reports 'loaded' 3 seconds later)\n"
        "   gfloat_c3resume_loadedat = Float\n")

    # 6. the server asks every game "do you have these saves?" in a chat line  #c3check <id> name1;name2;
    #    the game answers  #c3have <id> <0/1 per name> <version>  (a game without c3resume just shows the line)
    a = "      [*] = ;      var msg : String = LanPublicServerGetRegMessage;"
    lines = [
        "      // c3resume: questions of the server about saved games",
        "      if StrExists(msg, '#c3check ') then",
        "      begin",
        "         var c3start : Integer = StrPos('#c3check ', msg)+9;",
        "         var c3a : String = SubStr(msg, c3start, StrLength(msg)-c3start+1);",
        "         var c3sp : Integer = StrPos(' ', c3a);",
        "         var c3id : String = SubStr(c3a, 1, c3sp-1);",
        "         var c3rest : String = SubStr(c3a, c3sp+1, StrLength(c3a)-c3sp);",
        "         var c3bits : String = '';",
        "         var c3lang : String;",
        "         var c3i : Integer;",
        "         UserProfileRefreshSavesList;",
        "         var c3q : Integer = StrPos(';', c3rest);",
        "         while (c3q>0) do",
        "         begin",
        "            var c3n : String = SubStr(c3rest, 1, c3q-1);",
        "            c3rest := SubStr(c3rest, c3q+1, StrLength(c3rest)-c3q);",
        "            var c3have : String = '0';",
        "            for c3i:=0 to UserGetProfileSavesCount-1 do",
        "            if (UserGetProfileSaveByIndex(c3i)=c3n) then",
        "            c3have := '1';",
        "            c3bits := c3bits+c3have;",
        "            c3q := StrPos(';', c3rest);",
        "         end;",
    ] + ["         " + x for x in say_chat("'#c3have '+c3id+' '+c3bits+' %s'" % VERSION)] + [
        "         msg := '';",
        "      end;",
    ]
    add("check", SESSION_INC, a, a + "\n" + code(lines))

    # 7. F10 menu: buttons that send the chat commands (online only)
    a = "      [*] = ;elmHnd := ShowButton('bsavegame', elmHnd, elmMain, cbtnmat, cTextSaveGame,"
    lines = [
        "// c3resume: buttons for the lobby server's commands !save, !autosave, !saves and !load 1",
        "if (_net_IsOnline) and (not _net_IsReplay) then",
        "begin",
        "   var c3lang : String;",
        "   _profile_ConvertConfigValueToLocale(gProfile.lang, c3lang);",
        "   var c3t1 : String = 'Save match';",
        "   var c3t4 : String = 'Autosave every 5 min on/off';",
        "   var c3t2 : String = 'List saved matches';",
        "   var c3t3 : String = 'Continue newest save';",
        "   if (c3lang='de') then",
        "   begin",
        "      c3t1 := 'Partie speichern';",
        "      c3t4 := 'Autospeichern (5 Min.) an/aus';",
        "      c3t2 := 'Gespeicherte Partien';",
        "      c3t3 := 'Neueste Partie laden';",
        "   end;",
        "   elmHnd := ShowButton('bc3save', elmHnd, elmMain, cbtnmat, c3t1, cmargin2+cSmallOffset, 120, (not gbool_gui_bspectator));",
        "   elmHnd := ShowButton('bc3auto', elmHnd, elmMain, cbtnmat, c3t4, cmargin2, 123, (not gbool_gui_bspectator));",
        "   elmHnd := ShowButton('bc3list', elmHnd, elmMain, cbtnmat, c3t2, cmargin2, 121, True);",
        "   elmHnd := ShowButton('bc3load', elmHnd, elmMain, cbtnmat, c3t3, cmargin2, 122, (not gbool_gui_bspectator));",
        "end;",
    ]
    add("menu", SHOWMENU, a, code(lines) + "\n" + a)
    a = "      [*] = ;      cTagStatistics : begin"
    lines = [
        "      120, 121, 122, 123 : begin // c3resume: send the chat command to the lobby server, close the menu",
        "         var c3cmd : String = '!save';",
        "         if (tag=121) then",
        "         c3cmd := '!saves'",
        "         else",
        "         if (tag=122) then",
        "         c3cmd := '!load 1'",
        "         else",
        "         if (tag=123) then",
        "         c3cmd := '!autosave';",
        "         var c3lang : String;",
    ] + ["         " + x for x in say_chat("c3cmd")] + [
        "         SetClipCursor(gProfile.bclipmouse and IsEngine and (gInterface.gamemode<>gc_gamemode_mainmenu));",
        "         if (not GetGUIMiniMapVisible) then",
        "         _misc_SetMinimapVisible(True);",
        "         _gui_SetGUIElementVisibleByName(elmname, False);",
        "         gint_gui_changeresolutionstage := 0;",
        "      end;",
    ]
    add("menu", EVENTMENU, a, code(lines) + "\n" + a)

    # 8. the load itself: once per frame in the GUI's DoProgress, outside the processing of network commands,
    #    like the game's own Load button (eventmodalmessage.inc, cTagLoadApproved)
    a = "      [*] = ;//_misc_ProfilerBegin('gui:doprogress');"
    lines = [
        "// c3resume: never leave the 'clearing the old match' flag on (OnLoadFull clears it; this is the safety net)",
        "if (gbool_c3resume_unloading) and (Abs(_misc_GetRealTime-gfloat_c3resume_unloadstart)>60) then",
        "begin",
        "   gbool_c3resume_unloading := False;",
        "   Log('c3resume DoProgress: unloading flag cleared by timeout');",
        "end;",
        "// c3resume: report 'loaded' to the server only when this loop runs again 3 seconds after the load: a game that",
        "// is still busy behind the loading screen does not get here, so the server does not unpause too early",
        "if (gstring_c3resume_load<>'') and (gfloat_c3resume_loadedat>0) and (Abs(_misc_GetRealTime-gfloat_c3resume_loadedat)>3) then",
        "begin",
        "   var c3lang : String;",
    ] + ["   " + x for x in say_chat("'#c3loaded '+gstring_c3resume_load+' ok'")] + [
        "   Log('c3resume DoProgress: loaded '+gstring_c3resume_load+' - reported to the server');",
        "   gstring_c3resume_load := '';",
        "   gfloat_c3resume_loadedat := 0;",
        "end;",
        "// c3resume: the load the server asked for (ReadLoad noted it) starts here, between two frames",
        "if (gstring_c3resume_pending<>'') then",
        "begin",
        "   var c3name : String = gstring_c3resume_pending;",
        "   gstring_c3resume_pending := '';",
        "   Log('c3resume DoProgress: loading '+c3name+' t='+FloatToStr(GetGameTime));",
        "   gbool_gui_maxcameradist := True;",
        "   if (_control_GetGameSpeedMode<>gProfile.igamespeed) then",
        "   _control_SetGameSpeedByMode(gProfile.igamespeed, True);",
        "   UserProfileRefreshSavesList;",
        "   UserProfileRefreshReplaysList;",
        "   gint_gui_changeresolutionstage := 0;",
        "   _gui_ProcessProgressBar('', 0, 0, False);",
        "   // while the old match is cleared away the game's online checks answer No (see net.script): the cleanup",
        "   // runs like an offline load and sends no network messages for owners that are already deleted",
        "   // the match recording (every network command since the start) still refers to the units and the clock of",
        "   // the running match; a client trips over it in the NEXT load (endless loading screen). Clear it the way the",
        "   // game itself does when memory runs low (doprogress.inc, 'OutOfMemory preventing'): safe on one PC alone.",
        "   Log('c3resume DoProgress: clearing the match recording before the load');",
        "   ClearRecordManager;",
        "   gbool_recordwascleared := True;",
        "   _net_setRecord(False);",
        "   gbool_c3resume_unloading := True;",
        "   gfloat_c3resume_unloadstart := _misc_GetRealTime;",
        "   UserProfileLoadMap(c3name);",
        "   exit;",
        "end;",
        "",
    ]
    add("deferload", DOPROGRESS, a, code(lines) + "\n" + a)

    # 9. while our load clears away the running match, the game's own "online / recording?" checks answer No:
    #    the cleanup then runs exactly like an offline load. Online, every unit/building that is cleared away runs its
    #    death handling and sends network messages (ReadFree, ReadProduce, ...) for owners that are already deleted:
    #    access violation, endless loading screen (seen on clients). OnLoad / OnLoadFull switch the checks back on.
    a = "   result:=(GetLanMode>0) or (_net_lanmode_last=gc_lanmode_client);"
    add("unloadoffline", NET_SCRIPT, a,
        "   result:=((GetLanMode>0) or (_net_lanmode_last=gc_lanmode_client)) and (not gbool_c3resume_unloading);   // c3resume")
    a = "   result:=(GetRecordManagerGameMode=2) and (GetRecordEnabled or gbool_recordwascleared);"
    add("unloadoffline", NET_SCRIPT, a,
        "   result:=(GetRecordManagerGameMode=2) and (GetRecordEnabled or gbool_recordwascleared) and (not gbool_c3resume_unloading);   // c3resume")
    clear = ["// c3resume: the old match is cleared away - the online checks answer normally again",
             "if (gbool_c3resume_unloading) then",
             "begin",
             "   gbool_c3resume_unloading := False;",
             "   Log('c3resume %s: old match cleared, online again');",
             "end;"]
    a = "      [*] = ;if (gScenario.bexists) then"
    add("unloadoffline", ONLOAD, a, code([x.replace("%s", "OnLoad") for x in clear]) + "\n" + a)
    a = "      [*] = ;_scenario_AIRegionForceRescan;"
    add("unloadoffline", ONLOADFULL, a, code([x.replace("%s", "OnLoadFull") for x in clear]) + "\n" + a)

    # 5. (optional) diagnostics
    if diag:
        a = "   gbool_recordwascleared = Boolean\n"
        add("diag", DMGLOBAL, a, a + "   // c3resume (diagnostics): time of the last status line\n   gfloat_c3diag_lasthb = Float\n")  # noqa
        a = "      [*] = ;//ExecuteState('ShowAIDebug');"
        lines = [
            "// c3resume diagnostics: one status line every 10 seconds while an online game runs",
            "if (_net_IsOnline) and (gInterface.gamemode<>gc_gamemode_mainmenu) and (Abs(_misc_GetRealTime-gfloat_c3diag_lasthb)>10) then",
            "begin",
            "   gfloat_c3diag_lasthb := _misc_GetRealTime;",
            "   var c3io : Integer = GetPlayerIndexByHandle(GetPlayerHandleInterfaceIO);",
            "   var c3s : String = 'c3diag hb t='+FloatToStr(GetGameTime)+' ready='+BoolToStr(IsLanReady)+' pause='+BoolToStr(GetProgressingPauseMode)+' stage='+IntToStr(gMap.gamestage)+' io='+IntToStr(c3io)+' ptick='+IntToStr(gProgress.progresstick);",
            "   var c3k : Integer;",
            "   c3s := c3s+' cm=';",
            "   for c3k:=0 to GetCountOfPlayers-1 do",
            "   c3s := c3s+IntToStr(GetPlayerControlModeIntByHandle(GetPlayerHandleByIndex(c3k)));",
            "   Log(c3s);",
            "end;",
            "",
        ]
        add("diag", DOPROGRESS, a, code(lines) + "\n" + a)
        for s in TRACED:
            a = "      [*] = ;SwitchTo('Progress');"
            ln = ("if (_net_IsOnline) then Log('c3diag %s pl='+IntToStr(GetPlayerIndexByHandle(GetPlayerCurrentPlHandle))"
                  "+' t='+FloatToStr(GetGameTime));      // c3resume diagnostics" % s)
            add("diag", GLOBAL_INC + s.lower() + ".inc", a, code([ln]) + "\n" + a)
    return P


def new_files():
    lines = [
        "// c3resume: load a named save of THIS machine's profile when the server's record asks for it (!load <name>)",
        "if _net_IsOnline then",
        "begin",
        "   var loadname : String = RecordCustomReadString;",
        "   Log('c3resume ReadLoad: '+loadname+' t='+FloatToStr(GetGameTime));",
        "   var c3found : Boolean = False;",
        "   var c3i : Integer;",
        "   var c3lang : String;",
        "   UserProfileRefreshSavesList;",
        "   for c3i:=0 to UserGetProfileSavesCount-1 do",
        "   if (UserGetProfileSaveByIndex(c3i)=loadname) then",
        "   c3found := True;",
        "   if (not c3found) then",
        "   begin",
        "      // never load a save this machine does not have: report it to the server and keep playing",
        "      Log('c3resume ReadLoad: '+loadname+' is not in the saved games - not loading');",
    ] + ["      " + x for x in say_chat("'#c3loaded '+loadname+' missing'")] + [
        "      exit;",
        "   end;",
        "   // do NOT load here: this runs in the middle of the match's network commands, and the ones after it would",
        "   // point at units of the old map (access violation, endless loading screen). DoProgress loads it next frame.",
        "   gstring_c3resume_load := loadname;",
        "   gstring_c3resume_pending := loadname;",
        "end",
        "else _net_ErrorLog('c3resume ReadLoad ignored: not online');",
    ]
    text = "section.begin\n   Name = ReadLoad\n   Code : struct.begin\n" + code(lines) + "\n   struct.end\nsection.end\n"
    return [{"file": READLOAD, "content": text}]


def patch_data(diag=False):
    return {"version": VERSION, "patches": patch_list(diag), "newfiles": new_files()}


# =============================================================================== helpers
def say(*a):
    print(*a)
    sys.stdout.flush()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def L(text):                                   # text <-> bytes, one byte per character
    return text.encode("latin-1")


def find_game_dir(override, prompt=True):
    if override:
        return Path(override).expanduser()
    home = Path.home()
    roots = [home / ".local/share/Steam", home / ".steam/steam", home / ".steam/root",
             home / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
             home / "snap/steam/common/.local/share/Steam"]
    if os.name == "nt":
        roots = [Path(os.environ.get(k, "C:/")) / "Steam" for k in ("ProgramFiles(x86)", "ProgramFiles")]
    libs = []
    for r in roots:
        if r.exists():
            libs.append(r)
            vdf = r / "steamapps" / "libraryfolders.vdf"
            if vdf.exists():
                libs += [Path(m.replace("\\\\", "\\")) for m in
                         re.findall(r'"path"\s+"([^"]+)"', vdf.read_text(errors="replace"))]
    for lib in libs:
        g = lib / "steamapps" / "common" / "Cossacks 3"
        if (g / "data").exists():
            return g
    if not prompt:
        return None
    say("I could not find the Cossacks 3 folder.")
    say("In Steam: right-click Cossacks 3 > Manage > Browse local files, copy that folder's path and paste it here.")
    try:
        typed = input("Cossacks 3 folder: ").strip().strip('"').strip("'")
    except EOFError:
        typed = ""
    g = Path(typed).expanduser()
    if typed and (g / "data").exists():
        return g
    sys.exit("That is not the Cossacks 3 folder (it has no 'data' folder inside). Nothing was changed.")


def manifest_path(game):
    return game / BACKUP_DIR / "manifest.json"


def load_manifest(game):
    p = manifest_path(game)
    m = json.loads(p.read_text()) if p.exists() else {}
    m.setdefault("files", {})
    m.setdefault("created", [])
    m.setdefault("applied", [])
    return m


def save_manifest(game, m):
    p = manifest_path(game)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(m, indent=1))


def backup_once(game, rel):
    """Keep the file's state from before the FIRST install (uninstall puts it back)."""
    src, bk = game / rel, game / BACKUP_DIR / rel
    if src.exists() and not bk.exists():
        bk.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(bk))


def undo_files(game, m, quiet=False):
    """Put the originals back - only over files that are still our patched version."""
    for rel, info in list(m["files"].items()):
        p, bk = game / rel, game / BACKUP_DIR / rel
        now = sha(p.read_bytes()) if p.exists() else None
        if now == info["patched_sha"] and bk.exists():
            shutil.copy2(str(bk), str(p))
            if not quiet:
                say("  restored", rel)
        elif now != info["orig_sha"]:
            say("  left alone (changed by something else, e.g. a game update):", rel)
    for rel in m["created"]:
        p = game / rel
        if p.exists():
            p.unlink()
            if not quiet:
                say("  removed ", rel)
    m["files"], m["created"], m["applied"] = {}, [], []


def enabled_mods(game):
    ini = game / "mods" / "mods.ini"
    out = []
    if not ini.exists():
        return out
    text = ini.read_bytes().decode("latin-1")
    for blk in re.findall(r"struct\.begin(.*?)struct\.end", text, re.S):
        d = re.search(r"^\s*dir\s*=\s*(.+?)\s*$", blk, re.M)
        dis = re.search(r"^\s*dis\s*=\s*(\w+)", blk, re.M)
        if d and not (dis and dis.group(1).lower() == "true"):
            out.append((d.group(1).strip(), game / d.group(1).strip().replace("\\", "/")))
    return out


def disable_mods(game, dirs):
    ini = game / "mods" / "mods.ini"
    backup_once(game, "mods/mods.ini")

    def fix(match):
        blk = match.group(0)
        d = re.search(rb"^\s*dir\s*=\s*(.+?)\s*$", blk, re.M)
        if d and d.group(1).decode("latin-1").strip() in dirs:
            blk = re.sub(rb"(^\s*dis\s*=\s*)\w+", rb"\1True", blk, flags=re.M)
        return blk
    ini.write_bytes(re.sub(rb"struct\.begin.*?struct\.end", fix, ini.read_bytes(), flags=re.S))


def valid_server(addr):
    return re.fullmatch(r"[A-Za-z0-9.\-]+(:\d{1,5})?", addr or "") is not None


# =============================================================================== commands
def cmd_install(game, a):
    data = patch_data(a.diag)
    m = load_manifest(game)
    if m["files"] or m["created"]:
        undo_files(game, m, quiet=True)                         # an update starts again from the originals
    targets = sorted({p["file"] for p in data["patches"]})
    for rel in targets:
        if not (game / rel).exists():
            sys.exit("PROBLEM: %s is missing in the game folder. Nothing was changed." % rel)
    # an enabled mod that ships one of our files would hide our change: switch it off (reversible)
    clash = sorted({d for d, folder in enabled_mods(game)
                    for rel in targets + [READLOAD] if (folder / rel).exists()})
    work = {}
    for p in data["patches"]:
        rel = p["file"]
        text = work.get(rel)
        if text is None:
            text = (game / rel).read_bytes().decode("latin-1")
        nl = "\r\n" if "\r\n" in text else "\n"
        anchor, repl = p["anchor"].replace("\n", nl), p["replace"].replace("\n", nl)
        n = text.count(anchor)
        if n != 1:
            sys.exit("PROBLEM: the game file %s is not what this mod expects (part '%s' found %d times).\n"
                     "Maybe the game was updated. Nothing was changed." % (rel, p["name"], n))
        work[rel] = text.replace(anchor, repl)
    if clash:
        disable_mods(game, set(clash))
        say("Switched off these mods because they replace the same game files (uninstall turns them back on):")
        for d in clash:
            say("   ", d)
    nl = "\r\n" if b"\r\n" in (game / MENU_AIX).read_bytes() else "\n"
    for rel, text in work.items():
        p = game / rel
        old = p.read_bytes()
        bk = game / BACKUP_DIR / rel
        if (not bk.exists()) or bk.read_bytes() != old:
            bk.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(p), str(bk))
        new = L(text)
        p.write_bytes(new)
        m["files"][rel] = {"orig_sha": sha(old), "patched_sha": sha(new)}
        save_manifest(game, m)                                   # so uninstall works even if a later step fails
    for f in data["newfiles"]:
        (game / f["file"]).write_bytes(L(f["content"].replace("\n", nl)))
        m["created"].append(f["file"])
        save_manifest(game, m)
    m["applied"] = sorted({p["name"] for p in data["patches"]} | {"readload"})
    m["version"] = VERSION
    m["when"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_manifest(game, m)
    if a.server:
        set_server(game, a.server)
    if a.no_helper:
        if helper_installed() or helper_running():
            helper_remove()
        say("Installed WITHOUT the save helper: saves are not shared automatically. To continue a match, the host")
        say("sends the save file to every player, who puts it into their saves folder (see the README).")
    else:
        helper_install(game)
    say("")
    say("c3resume %s is installed in: %s" % (VERSION, game))
    say("Restart the game if it is running. Everybody in a match needs the same version.")


def set_server(game, addr):
    if not valid_server(addr):
        sys.exit("'%s' does not look like a server address (example: 192.168.1.20 or myhost.example.org)." % addr)
    if ":" not in addr:
        addr += ":31523"
    sd = game / SERVERS_DAT
    backup_once(game, SERVERS_DAT)
    sd.write_bytes(L("section.begin\r\n* = %s\r\nsection.end\r\n" % addr))
    say("The game now uses the lobby server", addr, "(uninstall puts the old setting back).")


def cmd_uninstall(game, a):
    m = load_manifest(game)
    bk_dir = game / BACKUP_DIR
    if not bk_dir.exists():
        say("c3resume is not installed - nothing to do.")
        return
    undo_files(game, m)
    for rel in ("mods/mods.ini", SERVERS_DAT, "cossacks.ini"):
        bk = bk_dir / rel
        if bk.exists():
            shutil.copy2(str(bk), str(game / rel))
            say("  restored", rel)
    shutil.rmtree(str(bk_dir), ignore_errors=True)
    helper_remove()
    say("c3resume is removed - the game files are original again. Restart the game if it is running.")


def cmd_status(game, a):
    m = load_manifest(game)
    say("game folder:", game)
    if not m["files"]:
        say("c3resume is NOT installed.")
        return
    bad = []
    for rel, info in m["files"].items():
        p = game / rel
        if not p.exists() or sha(p.read_bytes()) != info["patched_sha"]:
            bad.append(rel)
    bad += [rel for rel in m["created"] if not (game / rel).exists()]
    say("c3resume %s installed %s" % (m.get("version", "?"), m.get("when", "")))
    if bad:
        say("BUT these files were changed back (Steam 'verify' or a game update?) - run install again:")
        for rel in bad:
            say("   ", rel)
    else:
        say("all files OK.")
    sd = game / SERVERS_DAT
    if sd.exists():
        srv = re.findall(rb"=\s*([^\s]+)", sd.read_bytes())
        say("lobby server:", ", ".join(s.decode("latin-1") for s in srv) or "?")
    if helper_running():
        say("save-sync helper: running")
    elif helper_installed():
        say("save-sync helper: set up, but NOT running (install again, or log in again)")
    else:
        say("save-sync helper: not installed (saves are copied by hand)")


def saves_dirs(game, create=False):
    """the saved-games folders of every game profile on this machine; create=True also returns (and makes) the
    "saves" folder of a profile that never saved yet - a player who never was host still needs one for downloads"""
    found = []
    home = Path.home()
    docs = []
    if os.name == "nt":
        docs.append(Path(os.environ.get("USERPROFILE", str(home))) / "Documents")
    else:
        docs.append(home)                                       # native Linux build: ~/cossacks
        steamapps = game.parent.parent                          # .../steamapps
        docs.append(steamapps / "compatdata/333420/pfx/drive_c/users/steamuser/Documents")
        docs.append(steamapps / "compatdata/333420/pfx/drive_c/users/steamuser/My Documents")
        for pat in ("*/pfx/drive_c/users/steamuser/Documents", "*/drive_c/users/steamuser/Documents"):
            docs += [Path(p) for p in glob.glob(str(home / "c3-lab" / pat))]     # second game copies of the lab
    for d in docs:
        found += [Path(p) for p in glob.glob(str(d / "cossacks" / "profiles" / "*" / "saves"))]
        if create:
            for prof in glob.glob(str(d / "cossacks" / "profiles" / "*" / "")):
                found.append(Path(prof) / "saves")
    return sorted(set(found))


def cmd_saves(game, a):
    dirs = saves_dirs(game)
    if not dirs:                                                # never saved yet: make the folder (for a copied save)
        for d in saves_dirs(game, create=True):
            try:
                d.mkdir(exist_ok=True)
                dirs.append(d)
            except OSError:
                pass
    if not dirs:
        sys.exit("No saves folder yet: start Cossacks 3 once and make a player profile, then try again.")
    for d in dirs:
        say(d)
    if not a.no_open:
        opener = "explorer" if os.name == "nt" else "xdg-open"
        try:
            subprocess.Popen([opener, str(dirs[0])], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass


# =============================================================================== save-sync helper
# On !save only the host's game saves ("qladder_..."). The host's helper uploads that file to the lobby's
# save service right away. On !load the server marks the save as wanted, and every player's helper downloads
# it then (only then), so that all machines load the host's file - also on a PC that was not in the match.
SYNC_NAME = re.compile(r"^qladder_(auto_)?\d{8}_\d{4,6}_\d{1,4}min$")   # auto_: the autosave
FILES_PORT = 31524


def helper_home():
    return Path(os.environ.get("C3RESUME_HOME") or (Path.home() / ".local/share/c3resume"))


def helper_log(msg):
    line = "%s  %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    say(line)


def server_host(game):
    sd = game / SERVERS_DAT
    if sd.exists():
        m = re.search(rb"=\s*([A-Za-z0-9.\-]+)(?::\d+)?", sd.read_bytes())
        if m:
            return m.group(1).decode("latin-1")
    return None


def http(method, url, data=None, timeout=60):
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/gzip")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def upload_file(url, path):
    """gzip a save into a temp file piece by piece (a long match's save is several 100 MB) and PUT it from there"""
    tmp = helper_home() / "upload.gz.tmp"
    try:
        with open(str(path), "rb") as src, gzip.open(str(tmp), "wb", 6) as gz:
            shutil.copyfileobj(src, gz, 1 << 20)
        size = tmp.stat().st_size
        with open(str(tmp), "rb") as body:
            req = urllib.request.Request(url, data=body, method="PUT")
            req.add_header("Content-Type", "application/gzip")
            req.add_header("Content-Length", str(size))
            with urllib.request.urlopen(req, timeout=900) as r:
                r.read()
        return size
    finally:
        if tmp.exists():
            tmp.unlink()


def download_file(url, target):
    """GET a gzip save and unpack it piece by piece into target (via a temp file next to it)"""
    tmp = target.with_suffix(".c3tmp")
    try:
        with urllib.request.urlopen(url, timeout=900) as r, gzip.GzipFile(fileobj=r) as gz, open(str(tmp), "wb") as out:
            shutil.copyfileobj(gz, out, 1 << 20)
        os.replace(str(tmp), str(target))
    finally:
        if tmp.exists():
            tmp.unlink()


def sync_once(game, since, seen):
    host = server_host(game)
    if not host:
        return
    base = "http://%s:%d/c3" % (host, FILES_PORT)
    try:
        remote = {}
        for line in http("GET", base + "/list", timeout=10).decode("latin-1").splitlines():
            f = line.split("\t")
            if len(f) >= 2 and SYNC_NAME.match(f[0]):
                remote[f[0]] = len(f) >= 4 and f[3] == "1"     # True: a !load needs it now
    except (OSError, ValueError) as e:
        if seen.get("_down") != str(e):
            helper_log("save service at %s not reachable (%s) - will keep trying" % (base, e))
        seen["_down"] = str(e)
        seen["_fails"] = seen.get("_fails", 0) + 1
        return
    seen.pop("_down", None)
    seen["_fails"] = 0
    dirs = saves_dirs(game)
    newest_auto = max([n for n in remote if n.startswith("qladder_auto_")] or [""])
    if newest_auto:                                             # the server keeps one autosave: drop the replaced ones
        for d in dirs:
            for f in d.glob("qladder_auto_*.map"):
                if SYNC_NAME.match(f.stem) and f.stem < newest_auto and not remote.get(f.stem):   # not while a !load needs it
                    try:
                        f.unlink()
                        helper_log("removed the older autosave %s" % f.name)
                    except OSError:
                        pass
    for d in dirs:                                              # upload the host's new saves
        for f in d.glob("qladder_*.map"):
            name = f.stem
            if not SYNC_NAME.match(name) or name in remote or (name.startswith("qladder_auto_") and name < newest_auto):
                continue
            st = f.stat()
            steady = seen.get(str(f)) == st.st_size or seen.get("_once")
            if st.st_mtime < since or time.time() - st.st_mtime < 3 or not steady:
                seen[str(f)] = st.st_size                       # upload only once the size stopped changing
                continue
            failed = seen.setdefault("_failed", {})
            if time.time() - failed.get(name, 0) < 120:
                continue                                        # after a failure: try again in 2 minutes, not every 5 s
            try:
                size = upload_file(base + "/file/" + name, f)
                remote[name] = False
                failed.pop(name, None)
                helper_log("uploaded %s (%d MB packed, %d MB unpacked)" % (name, size >> 20, st.st_size >> 20))
            except (OSError, ValueError) as e:
                failed[name] = time.time()
                helper_log("upload of %s (%d MB) failed: %s - trying again in 2 minutes" % (name, st.st_size >> 20, e))
    for name in sorted(n for n in remote if remote[n]):         # download what a !load needs and is missing
        for d in saves_dirs(game, create=True):
            target = d / (name + ".map")
            if target.exists():
                continue
            try:
                d.mkdir(exist_ok=True)
                download_file(base + "/file/" + name, target)
                helper_log("downloaded %s (%d MB) into %s" % (name, target.stat().st_size >> 20, d))
            except (OSError, ValueError, EOFError) as e:
                helper_log("download of %s failed: %s" % (name, e))


def cmd_helper(game, a):
    home = helper_home()
    home.mkdir(parents=True, exist_ok=True)
    pidf = home / "helper.pid"
    if not a.once and helper_running():
        say("the save-sync helper is already running.")
        return
    state = home / "state.json"
    st = json.loads(state.read_text()) if state.exists() else {}
    if "since" not in st:                                       # saves older than the installation are not uploaded
        st["since"] = time.time() - 600
        state.write_text(json.dumps(st))
    if not a.once:
        pidf.write_text(str(os.getpid()))
    helper_log("save-sync helper %s started for %s" % (VERSION, game))
    seen = {"_once": True} if a.once else {}
    while True:
        try:
            sync_once(game, st["since"], seen)
        except Exception as e:                                  # never die on an odd file or network state
            helper_log("problem: %r" % (e,))
        if a.once:
            return
        time.sleep(min(60, 5 * 2 ** min(seen.get("_fails", 0), 4)))   # slower while the service is unreachable


def helper_installed():
    """the helper is set up to start at login (it may still not be running right now)"""
    return any(f.exists() for f in (Path.home() / ".config/systemd/user/c3resume-helper.service",
                                     Path.home() / ".config/autostart/c3resume-helper.desktop"))


def helper_running():
    pidf = helper_home() / "helper.pid"
    try:
        pid = int(pidf.read_text())
        cmd = Path("/proc/%d/cmdline" % pid).read_bytes()
        return b"c3resume" in cmd and b"helper" in cmd
    except (OSError, ValueError):
        return False


def helper_install(game):
    """Copy the helper to ~/.local/share/c3resume, start it at every login (systemd user service, or the desktop's
    autostart) and start it now."""
    if os.name == "nt":
        return                                                  # Windows uses c3resume.ps1
    home = helper_home()
    home.mkdir(parents=True, exist_ok=True)
    me = home / "c3resume.py"
    if Path(__file__).resolve() != me.resolve():
        shutil.copy2(__file__, str(me))
    (home / "config.json").write_text(json.dumps({"game_dir": str(game)}))
    cmdline = '%s "%s" helper --game-dir "%s"' % (sys.executable, me, game)
    log = home / "helper.log"
    done = False
    if shutil.which("systemctl"):
        unit = Path.home() / ".config/systemd/user/c3resume-helper.service"
        unit.parent.mkdir(parents=True, exist_ok=True)
        unit.write_text("[Unit]\nDescription=c3resume save-sync helper (Cossacks 3)\n\n[Service]\n"
                        "ExecStart=%s\nRestart=always\nRestartSec=10\nStandardOutput=append:%s\nStandardError=append:%s\n\n"
                        "[Install]\nWantedBy=default.target\n" % (cmdline, log, log))
        r = subprocess.run(["systemctl", "--user", "daemon-reload"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        r2 = subprocess.run(["systemctl", "--user", "enable", "--now", "c3resume-helper.service"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        r3 = subprocess.run(["systemctl", "--user", "restart", "c3resume-helper.service"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        done = r.returncode == 0 and r2.returncode == 0 and r3.returncode == 0
    if not done:
        auto = Path.home() / ".config/autostart/c3resume-helper.desktop"
        auto.parent.mkdir(parents=True, exist_ok=True)
        auto.write_text("[Desktop Entry]\nType=Application\nName=c3resume save-sync helper\nExec=%s\n"
                        "NoDisplay=true\nX-GNOME-Autostart-enabled=true\n" % cmdline)
        if not helper_running():
            with open(str(log), "a") as lf:
                subprocess.Popen([sys.executable, str(me), "helper", "--game-dir", str(game)], stdout=lf, stderr=lf,
                                 stdin=subprocess.DEVNULL, start_new_session=True)
    for _ in range(50):                                         # until it really runs (the setup window checks next)
        if helper_running():
            break
        time.sleep(0.1)
    say("The save-sync helper runs now and starts by itself at every login (log: %s)." % log)


def helper_remove():
    if os.name == "nt":
        return
    if shutil.which("systemctl"):
        subprocess.run(["systemctl", "--user", "disable", "--now", "c3resume-helper.service"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for f in (Path.home() / ".config/systemd/user/c3resume-helper.service",
              Path.home() / ".config/autostart/c3resume-helper.desktop"):
        if f.exists():
            f.unlink()
    pidf = helper_home() / "helper.pid"
    if helper_running():
        try:
            os.kill(int(pidf.read_text()), 15)
        except (OSError, ValueError):
            pass
    say("The save-sync helper is stopped and removed from autostart.")


def game_info(game):
    """What the setup window shows: one JSON object."""
    info = {"version": VERSION, "game_dir": str(game) if game else "", "found": bool(game and (game / "data").exists()),
            "installed": False, "installed_version": "", "intact": False, "server": "", "helper": helper_running(),
            "helper_installed": helper_installed()}
    if not info["found"]:
        return info
    m = load_manifest(game)
    if m["files"]:
        info["installed"] = True
        info["installed_version"] = m.get("version", "")
        info["intact"] = all((game / rel).exists() and sha((game / rel).read_bytes()) == i["patched_sha"]
                             for rel, i in m["files"].items()) and all((game / rel).exists() for rel in m["created"])
    sd = game / SERVERS_DAT
    if sd.exists():
        mt = re.search(rb"=\s*([A-Za-z0-9.\-]+(?::\d+)?)", sd.read_bytes())
        if mt:
            info["server"] = mt.group(1).decode("latin-1")
    return info


def cmd_info(a):
    print(json.dumps(game_info(find_game_dir(a.game_dir, prompt=False))))


def cmd_export(a):
    out = Path(a.file)
    out.write_text(json.dumps({"normal": patch_data(False), "diag": patch_data(True)}, indent=1))
    say("wrote", out)


def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--game-dir", help="the Cossacks 3 folder, if it is not found automatically")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    i = sub.add_parser("install", parents=[common])
    i.add_argument("--server", help="lobby server address, e.g. 192.168.1.20")
    i.add_argument("--diag", action="store_true", help="also write diagnostic lines to the game log")
    i.add_argument("--no-helper", action="store_true", help="do not set up the save-sync helper")
    h = sub.add_parser("helper", parents=[common])
    h.add_argument("--once", action="store_true", help="one sync round, then stop")
    sub.add_parser("uninstall", parents=[common])
    sub.add_parser("status", parents=[common])
    s = sub.add_parser("saves", parents=[common])
    s.add_argument("--no-open", action="store_true")
    sub.add_parser("info", parents=[common])
    e = sub.add_parser("export")
    e.add_argument("file")
    a = ap.parse_args()
    if not a.cmd:
        ap.print_help()
        return
    if a.cmd == "export":
        return cmd_export(a)
    if a.cmd == "info":
        return cmd_info(a)
    game = find_game_dir(a.game_dir)
    legacy = game / BACKUP_DIR / "mods.ini"                     # c3mod.py (lab tool) kept mods.ini here
    if legacy.exists() and not (game / BACKUP_DIR / "mods" / "mods.ini").exists():
        (game / BACKUP_DIR / "mods").mkdir(parents=True, exist_ok=True)
        shutil.move(str(legacy), str(game / BACKUP_DIR / "mods" / "mods.ini"))
    {"install": cmd_install, "uninstall": cmd_uninstall, "status": cmd_status, "saves": cmd_saves,
     "helper": cmd_helper}[a.cmd](game, a)


if __name__ == "__main__":
    main()
