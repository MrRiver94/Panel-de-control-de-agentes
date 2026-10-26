param([switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
$projectDirectory = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$pythonExecutable = Join-Path $projectDirectory 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExecutable)) { throw 'Falta backend/.venv; consulta docs/LOCAL_APP.md.' }
Push-Location $projectDirectory
try {
    if (-not $SkipBuild) {
        & node --preserve-symlinks --preserve-symlinks-main frontend/build.mjs
        if ($LASTEXITCODE -ne 0) { throw 'Falló la construcción del panel.' }
    }
    & $pythonExecutable scripts/collect-licenses.py
    if ($LASTEXITCODE -ne 0) { throw 'Faltan licencias para distribuir.' }
    & $pythonExecutable -m PyInstaller --noconfirm --distpath releases --workpath .build/pyinstaller packaging/slimeops.spec
    if ($LASTEXITCODE -ne 0) { throw 'Falló el empaquetado del ejecutable.' }
    $bundleDirectory = Join-Path $projectDirectory 'releases\SlimeOps'
    Copy-Item -LiteralPath (Join-Path $projectDirectory 'packaging\LEEME.txt') -Destination $bundleDirectory
    Copy-Item -LiteralPath (Join-Path $projectDirectory 'packaging\THIRD_PARTY_NOTICES.md') -Destination $bundleDirectory
    & $pythonExecutable scripts/check-portable.py (Join-Path $bundleDirectory 'SlimeOps.exe')
    if ($LASTEXITCODE -ne 0) { throw 'Fallo la comprobacion del ejecutable portatil.' }
    $archivePath = Join-Path $projectDirectory 'releases\SlimeOps-Windows-x64.zip'
    Compress-Archive -LiteralPath $bundleDirectory -DestinationPath $archivePath -Force
    $checksum = Get-FileHash -LiteralPath $archivePath -Algorithm SHA256
    "$($checksum.Hash.ToLower())  SlimeOps-Windows-x64.zip" | Set-Content -LiteralPath "$archivePath.sha256" -Encoding ASCII
    $checksum | Select-Object Hash, Path
    Write-Host "Aplicacion portatil: $bundleDirectory\SlimeOps.exe"
} finally {
    Pop-Location
}
