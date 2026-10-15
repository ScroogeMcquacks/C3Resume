@echo off
rem c3resume setup - double-click this file.
cd /d "%~dp0"
if not exist "%~dp0c3resume-gui.ps1" (
  echo.
  echo Please unzip first: right-click the downloaded zip file and choose "Extract All...",
  echo then open the new folder and double-click this file again.
  echo.
  pause
  exit /b 1
)
start "c3resume" /min powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0c3resume-gui.ps1"
