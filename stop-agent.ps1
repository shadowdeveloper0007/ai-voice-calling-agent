$agents = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "agent.py" }
if ($agents) { $agents | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host "🛑 Stopped PID $($_.ProcessId)" } }
else { Write-Host "ℹ️ No running LiveKit Agent found." }
