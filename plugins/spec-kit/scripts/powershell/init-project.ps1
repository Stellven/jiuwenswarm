# Initialize project-owned state without copying plugin resources or overwriting files.
[CmdletBinding()]
param(
    [string]$ProjectRoot = (Get-Location).Path,
    [switch]$Json
)
$ErrorActionPreference = 'Stop'
$resolved = Resolve-Path -LiteralPath $ProjectRoot -ErrorAction Stop
if (-not (Test-Path -LiteralPath $resolved.Path -PathType Container)) {
    throw 'ProjectRoot must be an existing directory.'
}
$project = $resolved.Path
$specify = Join-Path $project '.specify'
foreach ($directory in @($specify, (Join-Path $specify 'memory'), (Join-Path $specify 'templates/overrides'), (Join-Path $project 'docs/code/Missions'))) {
    [System.IO.Directory]::CreateDirectory($directory) | Out-Null
}
$constitution = Join-Path $specify 'memory/constitution.md'
$created = @()
$encoding = New-Object System.Text.UTF8Encoding($false)
if (-not (Test-Path -LiteralPath $constitution)) {
    $template = Join-Path $PSScriptRoot '../../templates/constitution-template.md'
    [System.IO.File]::WriteAllText($constitution, [System.IO.File]::ReadAllText($template, [System.Text.Encoding]::UTF8), $encoding)
    $created += '.specify/memory/constitution.md'
}
$ignore = Join-Path $specify '.gitignore'
if (-not (Test-Path -LiteralPath $ignore)) {
    [System.IO.File]::WriteAllText($ignore, "# Per-checkout feature selection`nfeature.json`n", $encoding)
    $created += '.specify/.gitignore'
}
$result = [PSCustomObject]@{ PROJECT_ROOT = $project; CREATED_FILES = @($created); CONSTITUTION = $constitution }
if ($Json) { $result | ConvertTo-Json -Compress } else { $result }
