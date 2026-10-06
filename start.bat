@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo Lancez d'abord install.bat.
    pause
    exit /b 1
)

rem Si c'est la webcam integree du PC qui s'affiche au lieu de la C270, enlevez "rem" devant la ligne suivante :
rem set SENTINEL_CAMERA=1

echo Sentinel-X demarre : le navigateur va s'ouvrir sur http://localhost:8000
echo Pour arreter : fermez cette fenetre (ou Ctrl+C).
cd server
"%~dp0.venv\Scripts\python.exe" -m sentinel.app --open
pause
