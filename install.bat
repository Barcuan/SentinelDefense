@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo.
echo ===== Installation de Sentinel-X =====
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo Python est introuvable. Installez Python 3.14 depuis python.org
    echo en cochant "Add python.exe to PATH", puis relancez install.bat.
    goto :erreur
)

echo [1/5] Environnement Python...
if not exist .venv\Scripts\python.exe (
    python -m venv .venv || goto :erreur
)
set PY=%~dp0.venv\Scripts\python.exe

echo [2/5] Dependances (quelques minutes la premiere fois)...
"%PY%" -m pip install --upgrade pip -q || goto :erreur
"%PY%" -m pip install -r server\requirements.txt -q || goto :erreur

echo [3/5] Modeles de reconnaissance des visages...
"%PY%" server\scripts\get_models.py || goto :erreur

echo [4/5] Mosquitto, pare-feu (une fenetre administrateur va s'ouvrir : acceptez)...
if not exist "C:\Program Files\mosquitto\mosquitto.exe" (
    winget install --id EclipseFoundation.Mosquitto -e --accept-source-agreements --accept-package-agreements || goto :erreur
)
powershell -NoProfile -Command "$p = Join-Path '%~dp0' 'server\scripts\windows_admin.ps1'; Start-Process powershell -Verb RunAs -Wait -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File', ('\"' + $p + '\"'))"

echo [5/5] Liaison chiffree et reglages de l'ESP...
pushd server
"%PY%" -m sentinel.setup || (popd & goto :erreur)
popd

echo.
echo ===== Installation terminee =====
echo Prochaine etape : televerser firmware\door-node\door-node.ino sur l'ESP avec Arduino IDE,
echo puis double-cliquer sur start.bat.
echo.
pause
exit /b 0

:erreur
echo.
echo L'installation s'est arretee. Lisez le message ci-dessus, corrigez, puis relancez install.bat.
pause
exit /b 1
