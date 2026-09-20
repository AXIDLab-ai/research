param([int]$Port = 8501)
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskPython = Join-Path $taskRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    throw '가상환경이 없습니다. README의 설치 절차를 먼저 실행하세요.'
}
Push-Location $taskRoot
try {
    & $taskPython -m streamlit run (Join-Path $taskRoot 'app.py') --server.address=127.0.0.1 --server.port=$Port --server.headless=true --browser.gatherUsageStats=false
} finally {
    Pop-Location
}
