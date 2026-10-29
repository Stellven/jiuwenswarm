param(
    [ValidateSet('capabilities','replay','status','planner','builder','benchmark','completion','executor','ml-readiness','all')]
    [string]$Group = 'capabilities',
    [string]$Image = 'ai4r-verify:local',
    [string]$Output,
    [string]$Case,
    [ValidateRange(1,10)][int]$RepeatCount = 1,
    [ValidateRange(10,1200)][int]$TimeoutSeconds = 600,
    [switch]$Build
)
$ErrorActionPreference = 'Stop'
$sourceRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
if ($Build) {
    & docker build -f (Join-Path $PSScriptRoot 'Dockerfile.app') --target verify -t $Image $sourceRoot
    if ($LASTEXITCODE -ne 0) { throw 'Verification image build failed.' }
}
$rawImage = & docker image inspect $Image
if ($LASTEXITCODE -ne 0) { throw 'Local verification image unavailable; use -Build or select -Image.' }
$imageInfo = ($rawImage | ConvertFrom-Json)[0]
if ($imageInfo.Os -ne 'linux') { throw 'These checks require the Linux verification image.' }
if (-not $Output) {
    $Output = Join-Path ([IO.Path]::GetTempPath()) ('ai4r-checks-' + [guid]::NewGuid().ToString('N'))
}
$outputRoot = [IO.Path]::GetFullPath($Output)
if ($sourceRoot.Contains(',') -or $outputRoot.Contains(',')) { throw 'Docker bind paths must not contain commas.' }
if (Test-Path -LiteralPath $outputRoot) { throw 'Select a new output directory; previous evidence is never overwritten.' }
New-Item -ItemType Directory -Path $outputRoot | Out-Null
$utf8 = New-Object System.Text.UTF8Encoding($false)
$failed = $false
for ($repeatIndex = 1; $repeatIndex -le $RepeatCount; $repeatIndex++) {
    $destination = Join-Path $outputRoot ('repeat-{0:d2}' -f $repeatIndex)
    New-Item -ItemType Directory -Path $destination | Out-Null
    $arguments = @('run','--rm','--init','--network','none','--memory','4g','--pids-limit','256',
        '--workdir','/workspace','--tmpfs','/workspace/logs:rw,nosuid,nodev,size=64m',
        '--tmpfs','/resources:rw,nosuid,nodev,mode=0711',
        '--mount',"type=bind,source=$sourceRoot,target=/workspace,readonly",
        '--mount',"type=bind,source=$destination,target=/evidence",
        '-e','PYTHONPATH=/workspace',$imageInfo.Id,'python','/workspace/deploy/m1/capsule_checks.py',
        '--group',$Group,'--output','/evidence','--timeout-s',"$TimeoutSeconds")
    if ($Case) { $arguments += @('--case',$Case) }
    $hostReceipt = [ordered]@{schema='ai4r-check-launch:1'; image_tag=$Image; image_id=$imageInfo.Id;
        os=$imageInfo.Os; architecture=$imageInfo.Architecture; source_root=$sourceRoot;
        repeat_index=$repeatIndex; docker_argv=$arguments}
    [IO.File]::WriteAllText((Join-Path $destination 'launch.json'),($hostReceipt | ConvertTo-Json -Depth 8),$utf8)
    & docker @arguments
    if ($LASTEXITCODE -ne 0) { $failed = $true }
}
Write-Output "Evidence: $outputRoot"
if ($failed) { throw 'One or more checks failed or did not finish; inspect each result.json and pytest.log.' }
