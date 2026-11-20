# Install CUE Uno Agent to start automatically at Windows logon.
# Run in PowerShell (as your normal user is fine):
#   cd ...\cue-push\scripts\uno_agent
#   .\install_windows_autostart.ps1

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Agent = Join-Path $Here "cue_uno_agent.py"
$Config = Join-Path $Here "config.json"
$TaskName = "CUE-Uno-Agent"
$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) { $PythonCmd = Get-Command py -ErrorAction SilentlyContinue }
if (-not $PythonCmd) { throw "Python not found on PATH. Install Python 3 and retry." }
$Python = $PythonCmd.Source

if (-not (Test-Path $Agent)) { throw "Missing $Agent" }
if (-not (Test-Path $Config)) {
  Copy-Item (Join-Path $Here "config.example.json") $Config
  Write-Host "Created config.json — edit api_base and api_key, then re-run this installer." -ForegroundColor Yellow
  notepad $Config
  exit 1
}

Write-Host "Installing pyserial + requests…" -ForegroundColor Cyan
& $Python -m pip install --quiet pyserial requests

$Action = New-ScheduledTaskAction -Execute $Python -Argument "`"$Agent`"" -WorkingDirectory $Here
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal | Out-Null

# Start now
Start-ScheduledTask -TaskName $TaskName

Write-Host ""
Write-Host "CUE Uno Agent installed and started." -ForegroundColor Green
Write-Host "  Task:    $TaskName (runs at every Windows logon)"
Write-Host "  Script:  $Agent"
Write-Host "  Config:  $Config"
Write-Host "  Log:     $(Join-Path $Here 'uno_agent.log')"
Write-Host ""
Write-Host "Plug the Uno into ANY USB port — the agent will find it and keep listening." -ForegroundColor Cyan
Write-Host "To stop:  Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
