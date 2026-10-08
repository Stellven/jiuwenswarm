# Small Windows entry point for the supported local WSL container.
[CmdletBinding()]
param(
    [ValidateSet('Start', 'Status', 'Open', 'Stop', 'Rebuild')]
    [string]$Action = 'Status',
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_. -]{0,127}$')]
    [string]$Distro = 'Ubuntu',
    [ValidatePattern('^/[^\r\n\x00]*$')]
    [string]$DefinitionEvidenceDirectory = '/var/lib/ai4research-trial/definition-evidence-LOCAL-3'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$TrialUrl = 'http://127.0.0.1:4311/intent-trial'
$ReadinessUrl = 'http://127.0.0.1:4311/api/intent-trial/readiness'

function Get-LinuxScript {
    $LinuxPaths = @(& wsl.exe -d $Distro -u root --exec wslpath -a -u $PSScriptRoot)
    if ($LASTEXITCODE -ne 0 -or $LinuxPaths.Count -ne 1 -or $LinuxPaths[0] -notmatch '^/[^\r\n\x00]*$') {
        throw 'The repository path could not be resolved in the selected WSL distribution.'
    }
    return $LinuxPaths[0].TrimEnd('/') + '/local.sh'
}

function Invoke-LocalAction([string]$Name) {
    & wsl.exe -d $Distro -u root --exec /bin/sh $LinuxScript $Name $DefinitionEvidenceDirectory
    if ($LASTEXITCODE -ne 0) {
        throw "Local action '$Name' failed. The diagnostic above describes the observed state."
    }
}

function Read-PrivateSession {
    # Capture the private pipe: never send this value to the console or a URL.
    $PrivateLines = @(& wsl.exe -d $Distro -u root --exec env TRIAL_TOKEN_PIPE=clipboard-v1 /bin/sh $LinuxScript token $DefinitionEvidenceDirectory)
    if ($LASTEXITCODE -ne 0 -or $PrivateLines.Count -ne 1 -or $PrivateLines[0] -notmatch '^[A-Za-z0-9_-]{32,1024}$') {
        $PrivateLines = $null
        throw 'The private application session is unavailable. Start the application first.'
    }
    return [string]$PrivateLines[0]
}

function ConvertTo-WindowsArgument([string]$Value) {
    # Start-Process joins ArgumentList on Windows; use CRT-safe argv quoting.
    if ($Value -notmatch '[\s"]') {
        return $Value
    }
    $Escaped = [regex]::Replace($Value, '(\\*)"', '$1$1\"')
    $Escaped = [regex]::Replace($Escaped, '(\\+)$', '$1$1')
    return '"' + $Escaped + '"'
}

function Start-OwnedKeepalive {
    Invoke-LocalAction 'prepare-keeper'
    $WslExecutable = (Get-Command wsl.exe -ErrorAction Stop).Source
    $HelperArguments = @('-d', $Distro, '-u', 'root', '--exec', '/bin/sh', $LinuxScript, 'keepalive', $DefinitionEvidenceDirectory)
    $QuotedArguments = @($HelperArguments | ForEach-Object { ConvertTo-WindowsArgument $_ })
    # A locked Linux helper owns only this project's lifetime, with no secrets.
    # Duplicate starts exit promptly because the same private flock is held.
    Start-Process -FilePath $WslExecutable -ArgumentList ($QuotedArguments -join ' ') -WindowStyle Hidden
    Start-Sleep -Milliseconds 300
}

function Test-WindowsLoopback {
    $PrivateSession = $null
    try {
        $PrivateSession = Read-PrivateSession
        $Health = Invoke-RestMethod -Uri $ReadinessUrl -Method Get -Headers @{ Authorization = "Bearer $PrivateSession" } -TimeoutSec 10 -MaximumRedirection 0
        if ($Health.scope -ne 'TRIAL-1' -or $Health.mock -ne $false) {
            throw 'The loopback response is not the supported real TRIAL application.'
        }
        # The complete reply stays private; account fields are never emitted.
        Write-Output '{"windows_loopback":"authenticated","scope":"TRIAL-1"}'
    }
    catch {
        throw 'Windows loopback access could not authenticate the local application. Check port4311 conflicts and WSL localhost forwarding; nothing was stopped.'
    }
    finally {
        $PrivateSession = $null
        $Health = $null
    }
}

function Test-UnrelatedWindowsPort {
    if (-not (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue)) {
        return
    }
    $Listeners = @(Get-NetTCPConnection -State Listen -LocalPort 4311 -ErrorAction SilentlyContinue)
    foreach ($Listener in $Listeners) {
        $Owner = Get-Process -Id $Listener.OwningProcess -ErrorAction SilentlyContinue
        if ($null -ne $Owner -and $Owner.ProcessName -notmatch '^(wslhost|wslrelay|wslservice|System)$') {
            throw 'Windows port4311 is occupied by another process. Nothing was stopped.'
        }
    }
}

try {
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
        throw 'WSL is unavailable on this Windows host.'
    }
    $LinuxScript = Get-LinuxScript
    switch ($Action) {
        'Start' {
            Test-UnrelatedWindowsPort
            Start-OwnedKeepalive
            Invoke-LocalAction 'start'
            Start-OwnedKeepalive
            Test-WindowsLoopback
            Write-Output 'Run the Open action to copy the local session and open the native page.'
        }
        'Rebuild' {
            Test-UnrelatedWindowsPort
            Start-OwnedKeepalive
            Invoke-LocalAction 'rebuild'
            Start-OwnedKeepalive
            Test-WindowsLoopback
        }
        'Status' {
            Invoke-LocalAction 'status'
            Test-WindowsLoopback
        }
        'Open' {
            Test-WindowsLoopback
            $PrivateSession = $null
            try {
                $PrivateSession = Read-PrivateSession
                Set-Clipboard -Value $PrivateSession
            }
            finally {
                $PrivateSession = $null
            }
            Start-Process -FilePath $TrialUrl
            Write-Output 'The local session was copied to the clipboard. Paste it into the page session field, click Connect, then use the application model-account login if needed.'
        }
        'Stop' {
            Invoke-LocalAction 'stop'
        }
    }
}
catch {
    # Stable local messages only: never print native provider payloads.
    Write-Error -Message $_.Exception.Message -ErrorAction Continue
    exit 1
}
