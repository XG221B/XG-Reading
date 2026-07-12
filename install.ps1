param(
    [ValidateSet("Junction", "Copy")]
    [string]$Mode = "Junction",
    [switch]$ReplaceExisting
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SourceSkill = Join-Path $RepositoryRoot "skill\xg-reading"
$TargetSkill = Join-Path $HOME ".codex\skills\xg-reading"

if (-not (Test-Path -LiteralPath $SourceSkill)) {
    throw "Cannot find XG-Reading skill source: $SourceSkill"
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $TargetSkill) | Out-Null

if (Test-Path -LiteralPath $TargetSkill) {
    $existing = Get-Item -LiteralPath $TargetSkill -Force
    $isMatchingJunction = $existing.LinkType -eq "Junction" -and $existing.Target -contains $SourceSkill
    $canReuse = $Mode -eq "Junction" -and $isMatchingJunction
    if (-not $canReuse -and -not $ReplaceExisting) {
        throw "Existing skill found at $TargetSkill. Re-run with -ReplaceExisting after backing up any local changes."
    }
    if (-not $canReuse) {
        Remove-Item -LiteralPath $TargetSkill -Recurse -Force
    }
}

if ($Mode -eq "Junction") {
    if (-not (Test-Path -LiteralPath $TargetSkill)) {
        New-Item -ItemType Junction -Path $TargetSkill -Target $SourceSkill | Out-Null
    }
} else {
    Copy-Item -LiteralPath $SourceSkill -Destination $TargetSkill -Recurse -Force
    $LocalConfig = Join-Path $TargetSkill "xg-reading.local.json"
    @{ repository_root = $RepositoryRoot } | ConvertTo-Json | Set-Content -LiteralPath $LocalConfig -Encoding utf8
}

Write-Host "XG-Reading installed from: $RepositoryRoot"
Write-Host "Paper outputs will be created in: $(Join-Path $RepositoryRoot 'outputs')"
