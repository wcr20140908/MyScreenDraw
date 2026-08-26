# Build and verify a clean portable Windows directory with PyInstaller.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$version = (& python -c "from version import VERSION; print(VERSION)").Trim()
if ($version -ne "5.2.1") {
    throw "Release build requires version 5.2.1, found '$version'"
}

# Never package checked-out runtime data or stale PyInstaller output.
foreach ($path in @("build", "dist")) {
    if (Test-Path $path) {
        Remove-Item -Recurse -Force $path
    }
}

# Offscreen is mandatory here, not a convenience: the suite constructs DrawingCanvas
# (which calls showFullScreen in __init__), so running it on the real platform throws
# fullscreen windows across the user's desktop for the whole run. The touch-injection
# tier is worse -- it hijacks the screen by design and must never start unasked.
$previousPlatform = $env:QT_QPA_PLATFORM
$env:QT_QPA_PLATFORM = "offscreen"
try {
    python -m unittest discover -s tests
    $testsExit = $LASTEXITCODE
} finally {
    $env:QT_QPA_PLATFORM = $previousPlatform
}
if ($testsExit -ne 0) {
    throw "Tests failed; refusing to build a release package"
}
python -m PyInstaller --noconfirm --clean MyScreenDraw.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed"
}

$package = Join-Path $root "dist\MyScreenDraw"
$exe = Join-Path $package "MyScreenDraw.exe"
if (-not (Test-Path $exe)) {
    throw "PyInstaller did not produce $exe"
}

# Keep notices visible beside the executable as well as bundled by the spec.
Copy-Item (Join-Path $root "LICENSE") $package -Force
Copy-Item (Join-Path $root "THIRD_PARTY_LICENSES.txt") $package -Force
New-Item -ItemType Directory -Path (Join-Path $package "data") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $package "exports") -Force | Out-Null

$required = @(
    "LICENSE",
    "THIRD_PARTY_LICENSES.txt",
    "_internal\PyQt6\Qt6\plugins\platforms\qwindows.dll",
    "_internal\PyQt6\Qt6\plugins\imageformats\qjpeg.dll",
    "_internal\PyQt6\Qt6\plugins\imageformats\qpdf.dll",
    "_internal\PyQt6\Qt6\plugins\imageformats\qsvg.dll",
    "_internal\PyQt6\Qt6\bin\Qt6Pdf.dll",
    "_internal\PyQt6\Qt6\bin\Qt6Svg.dll"
)
foreach ($relative in $required) {
    if (-not (Test-Path (Join-Path $package $relative))) {
        throw "Release package is missing $relative"
    }
}

# A package must not inherit local user data, caches, source, or old logs.
$forbidden = Get-ChildItem -Path $package -Recurse -File | Where-Object {
    $_.Name -match '^(config\.json|roster\.json|events\.jsonl|app\.log)$' -or
    $_.Extension -in @('.py', '.pyc', '.jsonl', '.tmp', '.png', '.jpg', '.jpeg') -or
    $_.FullName -match '\\autosave\\' -or
    $_.FullName -match '\\screenshots\\'
}
if ($forbidden) {
    throw "Release package contains user/runtime files: $($forbidden.FullName -join ', ')"
}

# --smoke-ui constructs the production windows and exits without entering the GUI loop.
$smoke = Start-Process -FilePath $exe -ArgumentList "--smoke-ui" -WorkingDirectory $package -PassThru -Wait
if ($smoke.ExitCode -ne 0) {
    throw "Frozen executable UI smoke check failed with exit code $($smoke.ExitCode)"
}

# Smoke creates runtime logs by design; remove all verification data before release.
foreach ($runtimeFile in @("data\config.json", "data\roster.json", "data\events.jsonl", "data\app.log")) {
    $target = Join-Path $package $runtimeFile
    if (Test-Path $target) { Remove-Item -Force $target }
}
$runtimeAutosave = Join-Path $package "data\autosave"
if (Test-Path $runtimeAutosave) { Remove-Item -Recurse -Force $runtimeAutosave }

$forbiddenAfterSmoke = Get-ChildItem -Path $package -Recurse -File | Where-Object {
    $_.Name -match '^(config\.json|roster\.json|events\.jsonl|app\.log)$' -or
    $_.Extension -in @('.py', '.pyc', '.jsonl', '.tmp', '.png', '.jpg', '.jpeg') -or
    $_.FullName -match '\\autosave\\|\\screenshots\\'
}
if ($forbiddenAfterSmoke) {
    throw "Release package contains runtime or private files after smoke: $($forbiddenAfterSmoke.FullName -join ', ')"
}

$hash = (Get-FileHash -Algorithm SHA256 $exe).Hash.ToLowerInvariant()
$manifest = [ordered]@{
    app_version = $version
    executable = "MyScreenDraw.exe"
    sha256 = $hash
    built_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    package_type = "PyInstaller onedir portable"
}
$manifest | ConvertTo-Json | Set-Content (Join-Path $package "RELEASE-MANIFEST.json") -Encoding utf8
Write-Host "Portable build verified: $package (v$version, SHA-256 $hash)"
