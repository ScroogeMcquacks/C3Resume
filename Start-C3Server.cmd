@echo off
rem Start-C3Server.cmd - double-click this to start the C3Resume server for Cossacks 3.
rem The window stays open while Cossacks 3 is played; Ctrl+C stops the server and its two helpers.
rem
rem   Start-C3Server.cmd                        normal start
rem   Start-C3Server.cmd -Stop                  stop the server running in another window
rem   Start-C3Server.cmd -DataDir D:\C3Data     use another data folder
rem
rem Nothing is installed and no administrator rights are needed.
setlocal
title C3Resume server (Cossacks 3)
cd /d "%~dp0"

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-C3Server.ps1" %*
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo.
    echo The server stopped with exit code %RC%.
    echo See the messages above and the log files in the data folder.
    echo.
    pause
)
endlocal
