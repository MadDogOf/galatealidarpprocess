# clean_outputs.ps1 — Wipe output/ and rebuild the canonical folder tree.
#
# Does NOT touch input/, source code, SMPL-X weights, or any git state.
#
# Usage (PowerShell):
#   .\clean_outputs.ps1               # interactive confirmation
#   .\clean_outputs.ps1 -Yes          # skip confirmation
#   .\clean_outputs.ps1 -DryRun       # list what would be deleted, delete nothing

param(
    [switch]$Yes,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$ROOT       = $PSScriptRoot
$OUTPUT_DIR = Join-Path $ROOT "output"

if (-not (Test-Path $OUTPUT_DIR)) {
    Write-Host "No output/ directory found at $OUTPUT_DIR - nothing to clean."
    exit 0
}

# ── List what's there ────────────────────────────────────────────────────────
$files = Get-ChildItem -Path $OUTPUT_DIR -Recurse -File -ErrorAction SilentlyContinue
if (-not $files -or $files.Count -eq 0) {
    Write-Host "output/ is already empty."
    exit 0
}

Write-Host ""
Write-Host "The following files under output/ will be removed:"
Write-Host ("-" * 60)

foreach ($f in $files) {
    $rel = $f.FullName.Substring($ROOT.Length + 1)
    Write-Host "  $rel"
}

$totalSize = ($files | Measure-Object -Property Length -Sum).Sum
$sizeMB = [math]::Round($totalSize / 1MB, 2)

Write-Host ("-" * 60)
Write-Host ("Total: {0} file(s), {1} MB" -f $files.Count, $sizeMB)
Write-Host ""

# ── Dry-run stop ─────────────────────────────────────────────────────────────
if ($DryRun) {
    Write-Host "-DryRun: nothing removed."
    exit 0
}

# ── Confirmation ─────────────────────────────────────────────────────────────
if (-not $Yes) {
    $ans = Read-Host "Delete all of the above? [y/N]"
    if ($ans -notmatch '^[yY]') {
        Write-Host "Aborted."
        exit 0
    }
}

# ── Wipe and rebuild the canonical tree ──────────────────────────────────────
Remove-Item -Recurse -Force $OUTPUT_DIR

New-Item -ItemType Directory -Force -Path (Join-Path $OUTPUT_DIR "images")         | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $OUTPUT_DIR "models\aligned") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $OUTPUT_DIR "models\final")   | Out-Null

Write-Host ""
Write-Host "[done] output/ cleaned."
Write-Host "  Rebuilt canonical layout:"
Write-Host "    output/"
Write-Host "    |-- images/"
Write-Host "    \\-- models/"
Write-Host "        |-- aligned/"
Write-Host "        \\-- final/"
