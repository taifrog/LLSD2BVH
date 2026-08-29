#Requires -Version 5.1
# LLSD2BVH onedir ビルドスクリプト
# Usage: powershell -ExecutionPolicy Bypass -File tools/build_exe.ps1
#        powershell -ExecutionPolicy Bypass -File tools/build_exe.ps1 -NoZip
param([switch]$NoZip)

$ErrorActionPreference = "Stop"

if ($PSScriptRoot) { $root = (Resolve-Path "$PSScriptRoot\..").Path } else { $root = (Resolve-Path ".").Path }
Set-Location $root
Write-Host "[build] root: $root"

# 1. Clean
foreach ($d in @("build","dist")) {
    if (Test-Path $d) {
        Write-Host "[build] removing $d"
        Remove-Item -Recurse -Force $d
    }
}

# 2. Build
Write-Host "[build] pyinstaller LLSD2BVH.spec"
pyinstaller --noconfirm --clean LLSD2BVH.spec
if ($LASTEXITCODE -ne 0) { throw "pyinstaller failed: $LASTEXITCODE" }

$exe = Join-Path $root "dist\LLSD2BVH\LLSD2BVH.exe"
if (!(Test-Path $exe)) { throw "exe not found: $exe" }
$size = (Get-ChildItem $exe).Length / 1MB
Write-Host "[build] exe: $exe ($([math]::Round($size,1)) MB)"
$dirSize = (Get-ChildItem -Recurse "dist\LLSD2BVH" | Measure-Object -Property Length -Sum).Sum / 1MB
Write-Host "[build] onedir total: $([math]::Round($dirSize,1)) MB"

# 2b. 外部差し替え用に exe 横にも skeleton をコピー（内蔵は _internal 内にある）
$skelSrc = Join-Path $root "avatar_skeleton.xml"
$skelDst = Join-Path $root "dist\LLSD2BVH\avatar_skeleton.xml"
if (Test-Path $skelSrc) {
    Copy-Item $skelSrc $skelDst -Force
    Write-Host "[build] copied avatar_skeleton.xml next to exe for override"
}

# 3. Zip (任意)
if (-not $NoZip) {
    $ver = "0.1.0"
    try {
        $toml = Get-Content "$root\pyproject.toml" -Raw
        if ($toml -match 'version\s*=\s*"([^"]+)"') { $ver = $Matches[1] }
    } catch {}
    $zip = Join-Path $root "dist\LLSD2BVH_v${ver}.zip"
    if (Test-Path $zip) { Remove-Item $zip -Force }
    Write-Host "[build] zipping -> $zip"
    Compress-Archive -Path "dist\LLSD2BVH" -DestinationPath $zip -CompressionLevel Optimal
    $zsize = (Get-ChildItem $zip).Length / 1MB
    Write-Host "[build] zip: $zip ($([math]::Round($zsize,1)) MB)"
}

Write-Host "[build] done."
