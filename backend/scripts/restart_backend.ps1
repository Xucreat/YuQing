param(
    [int]$Port = 8000,
    [int]$WaitSeconds = 30
)

$ErrorActionPreference = "Stop"
$backendDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonExe = Join-Path $backendDir ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Python 虚拟环境不存在: $pythonExe"
}

$pattern = "-m uvicorn app.main:app"
$processes = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
    Where-Object {
        $_.CommandLine -like "*$pattern*" -and
        $_.CommandLine -like "*--port $Port*"
    })

foreach ($process in $processes) {
    Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Milliseconds 500

$arguments = "-m uvicorn app.main:app --host 0.0.0.0 --port $Port"
Start-Process -FilePath $pythonExe `
    -ArgumentList $arguments `
    -WorkingDirectory $backendDir `
    -WindowStyle Hidden

$deadline = (Get-Date).AddSeconds($WaitSeconds)
do {
    Start-Sleep -Milliseconds 500
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
} while (-not $listener -and (Get-Date) -lt $deadline)

if (-not $listener) {
    throw "后端未在 ${WaitSeconds} 秒内监听端口 $Port"
}

Write-Output "后端已启动: http://127.0.0.1:$Port"
