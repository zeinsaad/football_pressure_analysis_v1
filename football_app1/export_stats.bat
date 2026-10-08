@echo off
cd /d "%~dp0"
python tools\export_stats.py %*
pause
