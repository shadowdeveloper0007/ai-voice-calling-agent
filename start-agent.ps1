$AgentDir = "D:\LiveKitAgentStaging"
$Python   = "$AgentDir\venv\Scripts\python.exe"
$Script   = "$AgentDir\agent.py"
$OutLog   = "$AgentDir\logs\agent.out"
$ErrLog   = "$AgentDir\logs\agent.err"

# Ensure logs folder exists
if (-not (Test-Path "$AgentDir\logs")) { 
    New-Item -ItemType Directory -Path "$AgentDir\logs" | Out-Null 
}

# Start the Python agent
Start-Process -FilePath $Python `
    -ArgumentList "$Script start" `  # <-- start, not dev
    -WorkingDirectory $AgentDir `
    -NoNewWindow `
    -RedirectStandardOutput $OutLog `
    -RedirectStandardError  $ErrLog

Write-Host "✅ LiveKit Agent started (start mode). Logs: $OutLog"

