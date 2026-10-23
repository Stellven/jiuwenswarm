param([switch]$Build, [switch]$Research, [switch]$Stop)

$ErrorActionPreference = 'Stop'
$distribution = 'Ubuntu'
$runtimeDirectory = Join-Path $env:LOCALAPPDATA 'AI4Research\runtime'
$ownerPath = Join-Path $runtimeDirectory 'wsl-host.json'
$keeper = $null
if (Test-Path -LiteralPath $ownerPath) {
    $owner = Get-Content -LiteralPath $ownerPath -Raw | ConvertFrom-Json
    $candidate = Get-Process -Id $owner.processId -ErrorAction SilentlyContinue
    if ($candidate -and $candidate.ProcessName -eq 'wsl' -and
        $candidate.StartTime.ToUniversalTime().ToString('o') -eq $owner.startedAt) {
        $keeper = $candidate
    }
}

if ($Stop) {
    & wsl.exe -d $distribution -u root --exec docker stop --timeout 45 ai4r-web-play-app-1
    if ($LASTEXITCODE -ne 0) { throw 'The app could not be stopped.' }
    if ($keeper) { Stop-Process -Id $keeper.Id }
    if (Test-Path -LiteralPath $ownerPath) { Remove-Item -LiteralPath $ownerPath }
    return
}

if (-not $keeper) {
    # WSL system services alone need not keep the distribution alive after
    # its launching terminal closes. Own one inert host for the local app.
    New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null
    $keeper = Start-Process -FilePath 'wsl.exe' -ArgumentList @(
        '-d', $distribution, '-u', 'root', '--exec', '/bin/sleep', 'infinity'
    ) -WindowStyle Hidden -PassThru
    @{ processId = $keeper.Id; startedAt = $keeper.StartTime.ToUniversalTime().ToString('o') } |
        ConvertTo-Json | Set-Content -LiteralPath $ownerPath -Encoding UTF8
}

$repository = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$linuxRepository = (& wsl.exe -d $distribution -u root --exec wslpath -a $repository).Trim()
if ($LASTEXITCODE -ne 0 -or -not $linuxRepository.StartsWith('/')) {
    throw 'Could not resolve the checkout in WSL Ubuntu.'
}
$launchOptions = @()
if ($Build) { $launchOptions += '--build' }
if ($Research) { $launchOptions += '--research' }
& wsl.exe -d $distribution -u root --exec bash "$linuxRepository/deploy/m1/start-local.sh" @launchOptions
if ($LASTEXITCODE -ne 0) { throw 'Local app startup failed. See the error above.' }
