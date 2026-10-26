# Optional helper: install the XG-Reading skill into a Codex-style skill directory.
# Running the skill directly from the repository (or from a copied skill folder)
# does not require this script.
param(
    [ValidateSet("Junction", "Copy")]
    [string]$Mode = "Junction",
    [string]$TargetSkillDir = (Join-Path $HOME ".codex\skills\xg-reading"),
    [switch]$ReplaceExisting
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $MyInvocation.MyCommand.Path))
$SourceSkill = [System.IO.Path]::GetFullPath((Join-Path $RepositoryRoot "skill\xg-reading"))
$TargetSkill = [System.IO.Path]::GetFullPath($TargetSkillDir)
$DefaultOutputs = Join-Path $RepositoryRoot "outputs"
$ConfigName = "xg-reading.local.json"

function Normalize-Path([string]$PathValue) {
    return [System.IO.Path]::GetFullPath($PathValue).TrimEnd([char]'\', [char]'/')
}

function Test-SamePath([string]$Left, [string]$Right) {
    return (Normalize-Path $Left) -ieq (Normalize-Path $Right)
}

function Test-PathWithin([string]$Child, [string]$Parent) {
    $childNorm = Normalize-Path $Child
    $parentNorm = Normalize-Path $Parent
    if ($childNorm -ieq $parentNorm) { return $true }
    $prefix = $parentNorm + [System.IO.Path]::DirectorySeparatorChar
    return $childNorm.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)
}

function Assert-SkillIdentity([string]$SkillPath, [string]$Label) {
    foreach ($relative in @("SKILL.md", "run.py", "assets\reference.docx")) {
        $candidate = Join-Path $SkillPath $relative
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            throw "$Label does not look like an XG-Reading skill: missing $candidate"
        }
    }
}

function Read-LocalConfig([string]$SkillPath) {
    $path = Join-Path $SkillPath $ConfigName
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return @{} }
    try {
        $data = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        throw "Existing local config cannot be parsed: $path"
    }
    if ($null -eq $data) { return @{} }
    $map = @{}
    foreach ($property in $data.PSObject.Properties) { $map[$property.Name] = $property.Value }
    return $map
}

function Write-LocalConfig([string]$SkillPath, [hashtable]$Config) {
    $path = Join-Path $SkillPath $ConfigName
    ($Config | ConvertTo-Json) | Set-Content -LiteralPath $path -Encoding utf8
}

function Remove-LinkOnly([string]$LinkPath) {
    # Delete the reparse point itself; never recurse into its target.
    [System.IO.Directory]::Delete($LinkPath, $false)
}

function Backup-Target([string]$TargetPath) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backup = "$TargetPath.backup-$stamp"
    Rename-Item -LiteralPath $TargetPath -NewName (Split-Path -Leaf $backup)
    return $backup
}

if (-not (Test-Path -LiteralPath $SourceSkill -PathType Container)) {
    throw "Cannot find XG-Reading skill source: $SourceSkill"
}
Assert-SkillIdentity -SkillPath $SourceSkill -Label "Skill source"

# Refuse targets that would delete or replace the source, the repository,
# their ancestors, or a filesystem/user root.
$targetNorm = Normalize-Path $TargetSkill
$sourceNorm = Normalize-Path $SourceSkill
$repoNorm = Normalize-Path $RepositoryRoot
$homeNorm = Normalize-Path $HOME
$driveRoot = [System.IO.Path]::GetPathRoot($targetNorm).TrimEnd([char]'\', [char]'/')
if (Test-SamePath $targetNorm $sourceNorm) { throw "Target must not equal the skill source: $TargetSkill" }
if (Test-SamePath $targetNorm $repoNorm) { throw "Target must not equal the repository root: $TargetSkill" }
if (Test-PathWithin $sourceNorm $targetNorm) { throw "Target must not be an ancestor of the skill source: $TargetSkill" }
if (Test-PathWithin $targetNorm $sourceNorm) { throw "Target must not be inside the skill source: $TargetSkill" }
if (Test-PathWithin $repoNorm $targetNorm) { throw "Target must not be an ancestor of the repository: $TargetSkill" }
if (Test-SamePath $targetNorm $driveRoot) { throw "Target must not be a drive root: $TargetSkill" }
if (Test-SamePath $targetNorm $homeNorm) { throw "Target must not be the user home directory: $TargetSkill" }

$targetParent = Split-Path -Parent $TargetSkill
New-Item -ItemType Directory -Force -Path $targetParent | Out-Null

$backup = $null
$existingConfig = @{}
$targetExists = Test-Path -LiteralPath $TargetSkill
if ($targetExists) {
    $existing = Get-Item -LiteralPath $TargetSkill -Force
    $isLink = $existing.LinkType -in @("Junction", "SymbolicLink")
    if ($isLink) {
        $linkTarget = @($existing.Target)[0]
        $canReuse = $Mode -eq "Junction" -and (Test-SamePath ([string]$linkTarget) $SourceSkill)
        if ($canReuse -and -not $ReplaceExisting) {
            Write-Host "Existing matching junction reused: $TargetSkill"
            Write-Host "Skill target: $TargetSkill"
            Write-Host "Default paper outputs: $DefaultOutputs"
            exit 0
        }
        if (-not $canReuse -and -not $ReplaceExisting) {
            throw "Existing link points elsewhere: $TargetSkill. Re-run with -ReplaceExisting after backing up any local changes."
        }
        Remove-LinkOnly -LinkPath $TargetSkill
        $targetExists = $false
    } else {
        Assert-SkillIdentity -SkillPath $TargetSkill -Label "Existing target"
        if (-not $ReplaceExisting) {
            throw "Existing skill found at $TargetSkill. Re-run with -ReplaceExisting after backing up any local changes."
        }
        $existingConfig = Read-LocalConfig -SkillPath $TargetSkill
        $backup = Backup-Target -TargetPath $TargetSkill
        $targetExists = $false
        Write-Host "Previous installation moved to: $backup"
    }
}

if ($Mode -eq "Junction") {
    try {
        New-Item -ItemType Junction -Path $TargetSkill -Target $SourceSkill | Out-Null
    } catch {
        if ($backup -and (Test-Path -LiteralPath $backup)) {
            Rename-Item -LiteralPath $backup -NewName (Split-Path -Leaf $TargetSkill)
        }
        throw
    }
} else {
    $staging = Join-Path $targetParent ("xg-reading.staging-" + [guid]::NewGuid().ToString("N"))
    try {
        Copy-Item -LiteralPath $SourceSkill -Destination $staging -Recurse -Force
        $copiedConfig = Join-Path $staging $ConfigName
        if (Test-Path -LiteralPath $copiedConfig) { Remove-Item -LiteralPath $copiedConfig -Force }
        Assert-SkillIdentity -SkillPath $staging -Label "Staged copy"
        $mergedConfig = @{}
        foreach ($key in $existingConfig.Keys) { $mergedConfig[$key] = $existingConfig[$key] }
        $mergedConfig["repository_root"] = $RepositoryRoot
        Write-LocalConfig -SkillPath $staging -Config $mergedConfig
        Move-Item -LiteralPath $staging -Destination $TargetSkill
    } catch {
        if (Test-Path -LiteralPath $staging) {
            Remove-Item -LiteralPath $staging -Recurse -Force
        }
        if ($backup -and (Test-Path -LiteralPath $backup) -and -not (Test-Path -LiteralPath $TargetSkill)) {
            Rename-Item -LiteralPath $backup -NewName (Split-Path -Leaf $TargetSkill)
        }
        throw
    }
}

Write-Host "XG-Reading installed from: $RepositoryRoot"
Write-Host "Skill target: $TargetSkill"
if ($Mode -eq "Copy") {
    Write-Host "Copied install: repository_root is recorded in $(Join-Path $TargetSkill $ConfigName)"
    if ($existingConfig.ContainsKey("output_root")) {
        Write-Host "Preserved previous output_root: $($existingConfig["output_root"])"
    }
}
if ($backup) { Write-Host "Backup kept at: $backup" }
Write-Host "Default paper outputs: $DefaultOutputs"
Write-Host ('Check the environment with: <python> "{0}" doctor' -f (Join-Path $TargetSkill "run.py"))
