@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul && (py build.py) || (python build.py)
pause
