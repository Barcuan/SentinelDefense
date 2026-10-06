# Sentinel-X : réglages Windows qui demandent les droits administrateur. Lancé par install.bat.

# L'ESP doit pouvoir joindre le broker sur le port 8883, mais seulement depuis le partage de connexion
# (192.168.137.x) : les autres machines du Wi-Fi de l'école restent bloquées.
$rule = 'Sentinel-X MQTT 8883'
if (-not (Get-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $rule -Direction Inbound -Protocol TCP -LocalPort 8883 `
        -RemoteAddress 192.168.137.0/24 -Action Allow -Profile Any | Out-Null
}

# L'installeur de Mosquitto ajoute un service qui écoute en clair sur 1883 : inutile ici, on l'arrête.
Stop-Service mosquitto -ErrorAction SilentlyContinue
Set-Service mosquitto -StartupType Disabled -ErrorAction SilentlyContinue

Write-Host 'Pare-feu (port 8883) et service Mosquitto : OK'
Start-Sleep -Seconds 2
