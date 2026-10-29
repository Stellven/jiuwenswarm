param(
    [ValidateSet('Start', 'Stop', 'Status')][string]$Action = 'Status',
    [Parameter(Mandatory=$true)][string]$Config,
    [string]$RuntimePython
)
$ErrorActionPreference = 'Stop'
$configPath = (Resolve-Path -LiteralPath $Config).Path
$viewerDirectory = Split-Path -Parent $configPath
$pidPath = Join-Path $viewerDirectory 'viewer.pid'
$entryPath = Join-Path $PSScriptRoot 'harbor_viewer.py'
$url = 'http://127.0.0.2:5175'
$viewerProcess = $null
if (Test-Path -LiteralPath $pidPath) {
    $viewerPid = [int](Get-Content -LiteralPath $pidPath -Raw).Trim()
    $candidate = Get-CimInstance Win32_Process -Filter "ProcessId=$viewerPid"
    if ($candidate -and $candidate.CommandLine.Contains($entryPath) -and
        $candidate.CommandLine.Contains($configPath)) {
        $viewerProcess = $candidate
    }
}
if ($Action -eq 'Stop') {
    if ($viewerProcess) { Stop-Process -Id $viewerProcess.ProcessId }
    if (Test-Path -LiteralPath $pidPath) { Remove-Item -LiteralPath $pidPath }
    Write-Output 'Owned Harbor viewer stopped; original jobs and application retained.'
    exit 0
}
if ($Action -eq 'Start' -and -not $viewerProcess) {
    if (-not $RuntimePython) { throw 'Start requires -RuntimePython pointing to Harbor 0.24 Python.' }
    $pythonPath = (Resolve-Path -LiteralPath $RuntimePython).Path
    $arguments = '"' + $entryPath + '" --config "' + $configPath + '"'
    $process = Start-Process -FilePath $pythonPath -ArgumentList $arguments -WindowStyle Hidden `
        -WorkingDirectory $viewerDirectory -PassThru `
        -RedirectStandardOutput (Join-Path $viewerDirectory 'viewer.stdout.log') `
        -RedirectStandardError (Join-Path $viewerDirectory 'viewer.stderr.log')
    Set-Content -LiteralPath $pidPath -Value $process.Id -Encoding ascii
    $deadline = (Get-Date).AddSeconds(20)
    do {
        if ($process.HasExited) { throw 'Viewer exited; inspect viewer.stderr.log.' }
        try {
            $health = Invoke-RestMethod -Uri "$url/api/health" -TimeoutSec 2 -NoProxy
            if ($health.status -eq 'ok') { break }
        } catch { Start-Sleep -Milliseconds 250 }
    } while ((Get-Date) -lt $deadline)
}
try {
    $sources = Invoke-RestMethod -Uri "$url/viewer/sources" -TimeoutSec 10 -NoProxy
    $jobs = Invoke-RestMethod -Uri "$url/api/jobs" -TimeoutSec 20 -NoProxy
    [pscustomobject]@{url=$url; mode=$sources.mode; total_jobs=$jobs.total;
        sources=$sources.sources} | ConvertTo-Json -Depth 6
} catch {
    throw "Harbor viewer is unavailable. Start it or inspect logs in $viewerDirectory. $($_.Exception.Message)"
}
