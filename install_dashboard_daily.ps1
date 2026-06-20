param(
    [string]$CodexHome = "$env:USERPROFILE\.codex",
    [string]$ResearchRoot = "D:\ResearchManagement"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceSkillRoot = Join-Path $packageRoot 'skill\maintain-research-dashboard'
$sourceDashboardRoot = Join-Path $packageRoot 'dashboard-scaffold\research-dashboard'
$targetSkillRoot = Join-Path $CodexHome 'skills\maintain-research-dashboard'
$targetDashboardRoot = Join-Path $ResearchRoot 'research-dashboard'

if (-not (Test-Path -LiteralPath $sourceSkillRoot)) {
    throw "Source skill folder not found: $sourceSkillRoot"
}
if (-not (Test-Path -LiteralPath $sourceDashboardRoot)) {
    throw "Source dashboard scaffold not found: $sourceDashboardRoot"
}

$skillsRoot = Join-Path $CodexHome 'skills'
foreach ($dir in @($skillsRoot, $ResearchRoot, $targetSkillRoot, $targetDashboardRoot)) {
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}

function Copy-TreeWithoutPycache {
    param(
        [string]$SourceRoot,
        [string]$TargetRoot
    )
    Get-ChildItem -LiteralPath $SourceRoot -Recurse -Force | Where-Object {
        $_.FullName -notlike '*\__pycache__\*' -and $_.Name -ne '__pycache__'
    } | ForEach-Object {
        $target = $_.FullName.Replace($SourceRoot, $TargetRoot)
        if ($_.PSIsContainer) {
            if (-not (Test-Path -LiteralPath $target)) {
                New-Item -ItemType Directory -Path $target -Force | Out-Null
            }
        } else {
            $parent = Split-Path -Parent $target
            if (-not (Test-Path -LiteralPath $parent)) {
                New-Item -ItemType Directory -Path $parent -Force | Out-Null
            }
            Copy-Item -LiteralPath $_.FullName -Destination $target -Force
        }
    }
}

Copy-TreeWithoutPycache -SourceRoot $sourceSkillRoot -TargetRoot $targetSkillRoot
Copy-TreeWithoutPycache -SourceRoot $sourceDashboardRoot -TargetRoot $targetDashboardRoot

$dashboardRoot = Join-Path $ResearchRoot 'research-dashboard'
$pathReplacements = @(
    @('D:\ResearchManagement\research-dashboard', $dashboardRoot),
    @('D:\ResearchManagement', $ResearchRoot)
)
$textExtensions = @('.md', '.yaml', '.yml', '.json', '.py', '.js', '.ps1')
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
Get-ChildItem -LiteralPath @($targetSkillRoot, $targetDashboardRoot) -Recurse -File | Where-Object {
    $textExtensions -contains $_.Extension.ToLowerInvariant()
} | ForEach-Object {
    $content = Get-Content -LiteralPath $_.FullName -Raw -Encoding UTF8
    foreach ($replacement in $pathReplacements) {
        $content = $content.Replace($replacement[0], $replacement[1])
    }
    [System.IO.File]::WriteAllText($_.FullName, $content, $utf8NoBom)
}

foreach ($dir in @('daily-reports', 'exports', 'merged-projects', 'tasks', 'archived-projects')) {
    $target = Join-Path $targetDashboardRoot $dir
    if (-not (Test-Path -LiteralPath $target)) {
        New-Item -ItemType Directory -Path $target -Force | Out-Null
    }
}

$smtpTemplate = Join-Path $targetDashboardRoot 'config\smtp-mail.local.template.json'
$smtpLocal = Join-Path $targetDashboardRoot 'config\smtp-mail.local.json'
if ((Test-Path -LiteralPath $smtpTemplate) -and (-not (Test-Path -LiteralPath $smtpLocal))) {
    Copy-Item -LiteralPath $smtpTemplate -Destination $smtpLocal -Force
}

Write-Host "Installed skill to $targetSkillRoot"
Write-Host "Installed dashboard scaffold to $targetDashboardRoot"
Write-Host "Next: read $packageRoot\AGENT_HANDOFF.md"
