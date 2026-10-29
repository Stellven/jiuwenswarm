param([switch]$Build, [switch]$Research, [switch]$Stop, [string]$Profile, [string]$WslDistro)
$ErrorActionPreference = 'Stop'
$entry = Join-Path $PSScriptRoot 'ai4r.py'
$options = @()
if ($Profile) { $options += @('--profile', $Profile) }
if ($Stop) {
    & python $entry @options stop
    if ($LASTEXITCODE -ne 0) { throw 'AI4R stop failed; state is retained.' }
    return
}
$setupOptions = @()
if ($WslDistro) { $setupOptions += @('--wsl-distro', $WslDistro) }
& python $entry @options setup @setupOptions
if ($LASTEXITCODE -ne 0) { throw 'AI4R setup failed.' }
if ($Build) {
    $destination = Join-Path ([IO.Path]::GetTempPath()) ('ai4r-build-' + [guid]::NewGuid().ToString('N'))
    & python $entry @options build --output $destination
    if ($LASTEXITCODE -ne 0) { throw 'AI4R build failed.' }
}
& python $entry @options start
if ($LASTEXITCODE -ne 0) { throw 'AI4R startup needs attention; run doctor.' }
