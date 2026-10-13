# Starts krillionDbot by itself when you log in to Windows, in a minimized window that
# restarts the bot if it ever stops (see autostart.bat).
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
    Write-Host "Removed $TaskName from startup. If it's running now, close its window to stop it."
    return
}

if (-not (Test-Path (Join-Path $Here ".venv\Scripts\python.exe"))) {
    Write-Host "Run run_bot.bat once first, so the bot is set up and has its token."
    exit 1
}

$User = "$env:USERDOMAIN\$env:USERNAME"
# "start /min" opens autostart.bat in its own minimized window and lets the task finish right away.
$Action = New-ScheduledTaskAction -Execute "cmd.exe" -WorkingDirectory $Here `
    -Argument "/c start `"krillionDbot`" /min `"$(Join-Path $Here 'autostart.bat')`""
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $User
$Trigger.Delay = "PT20S"  # give the network a moment after login
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -User $User `
    -Description "Starts the krillionDbot Discord bot at login, in a minimized window." -Force | Out-Null

Write-Host "krillionDbot will now start by itself when $User logs in."
Write-Host "Start it right now with: schtasks /run /tn $TaskName"
