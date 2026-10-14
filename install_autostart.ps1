# Starts krillionDbot by itself in the background (no window) when you log in to Windows.
# background.py restarts the bot if it ever stops and writes its log (view_log.bat opens it).
#
#   Install:  powershell -ExecutionPolicy Bypass -File install_autostart.ps1
#   Remove:   powershell -ExecutionPolicy Bypass -File install_autostart.ps1 -Remove
#
# Run run_bot.bat once first, so the bot is set up and has its token.
param([switch]$Remove)

$TaskName = "krillionDbot"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed $TaskName from startup. If it's running now, stop it with stop_background.bat."
    return
}

if (-not (Test-Path (Join-Path $Here ".venv\Scripts\python.exe"))) {
    Write-Host "Run run_bot.bat once first, so the bot is set up and has its token."
    exit 1
}

$User = "$env:USERDOMAIN\$env:USERNAME"
# pythonw runs without any window, so the bot lives in the background, off the taskbar.
$Action = New-ScheduledTaskAction -Execute (Join-Path $Here ".venv\Scripts\pythonw.exe") `
    -Argument "`"$(Join-Path $Here 'background.py')`"" -WorkingDirectory $Here
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $User
$Trigger.Delay = "PT20S"  # give the network a moment after login
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -User $User `
    -Description "Starts the krillionDbot Discord bot in the background at login." -Force | Out-Null

Write-Host "krillionDbot will now start by itself in the background when $User logs in."
Write-Host "Start it right now with start_background.bat; stop it with stop_background.bat."
