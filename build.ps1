# Build and verify a clean portable Windows directory with PyInstaller.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root

function Assert-PathWithin([string]$Path, [string]$Boundary, [switch]$Recurse) {
    $absolute = [IO.Path]::GetFullPath($Path)
    $base = [IO.Path]::GetFullPath($Boundary).TrimEnd([IO.Path]::DirectorySeparatorChar)
    if (-not $absolute.StartsWith($base + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing filesystem operation outside ${base}: $absolute"
    }
    # Check existing ancestors, including the workspace and volume root.
    $cursor = $absolute
    while ($cursor) {
        try { $item = Get-Item -LiteralPath $cursor -Force -ErrorAction Stop }
        catch [System.Management.Automation.ItemNotFoundException] { $item = $null }
        if ($item -and ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Refusing reparse point: $cursor"
        }
        $cursor = [IO.Path]::GetDirectoryName($cursor)
    }
    if ($Recurse -and (Test-Path -LiteralPath $absolute -PathType Container)) {
        # Inspect each level before descent; never traverse a link to discover it.
        $pending = New-Object 'System.Collections.Generic.Stack[string]'
        $pending.Push($absolute)
        while ($pending.Count) {
            foreach ($child in (Get-ChildItem -LiteralPath $pending.Pop() -Force)) {
                if ($child.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                    throw "Refusing reparse point in cleanup tree: $($child.FullName)"
                }
                if ($child.PSIsContainer) { $pending.Push($child.FullName) }
            }
        }
    }
    return $absolute
}

function Invoke-Smoke([string]$Executable, [string]$Directory) {
    # Hidden only affects the initial window state; Qt must also stay offscreen.
    $previousPlatform = $env:QT_QPA_PLATFORM
    $previousKeyboard = $env:MYSCREENDRAW_NO_KEYBOARD
    $process = $null
    try {
        $env:QT_QPA_PLATFORM = 'offscreen'
        $env:MYSCREENDRAW_NO_KEYBOARD = '1'
        $process = Start-Process -FilePath $Executable -ArgumentList '--smoke-ui' -WorkingDirectory $Directory -WindowStyle Hidden -PassThru
        $null = $process.Handle # Retain the native handle for ExitCode on Windows PowerShell.
        if (-not $process.WaitForExit(60000)) {
            Stop-Process -Id $process.Id -Force
            $process.WaitForExit()
            throw 'Frozen executable smoke timed out'
        }
        if ($process.ExitCode -ne 0) { throw "Frozen executable smoke failed: $($process.ExitCode)" }
    } finally {
        # Restore caller state even when process startup or handle disposal fails.
        $env:QT_QPA_PLATFORM = $previousPlatform
        $env:MYSCREENDRAW_NO_KEYBOARD = $previousKeyboard
        if ($null -ne $process) { $process.Dispose() }
    }
}

$version = (& python -c "from version import VERSION; print(VERSION)").Trim()
if ($LASTEXITCODE -ne 0 -or $version -ne "6.0.1") {
    throw "Release build requires version 6.0.1, found '$version'"
}

# Never package checked-out runtime data or stale PyInstaller output.
foreach ($relative in @("build", "dist")) {
    $path = Assert-PathWithin (Join-Path $root $relative) $root -Recurse
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
    }
}

$buildDir = Assert-PathWithin (Join-Path $root 'build') $root
[IO.Directory]::CreateDirectory($buildDir) | Out-Null
$sourceSnapshot = Assert-PathWithin (Join-Path $buildDir 'release-source.json') $buildDir
python -B release_artifact.py snapshot --root $root --output $sourceSnapshot
if ($LASTEXITCODE -ne 0) { throw 'Could not snapshot release source' }

# Offscreen is mandatory here, not a convenience: the suite constructs DrawingCanvas
# (which calls showFullScreen in __init__), so running it on the real platform throws
# fullscreen windows across the user's desktop for the whole run. The touch-injection
# tier is worse -- it hijacks the screen by design and must never start unasked.
$previousPlatform = $env:QT_QPA_PLATFORM
$env:QT_QPA_PLATFORM = "offscreen"
# Windows PowerShell 5.1 turns each stderr line from a native exe into an ErrorRecord,
# so under $ErrorActionPreference = "Stop" a harmless warning aborts the build before
# $LASTEXITCODE is ever read -- and offscreen Qt always warns about the font directory.
# unittest reports its verdict through the exit code, so let that decide, not stderr.
$previousErrorAction = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    python -m pytest -q --ignore=tests/test_touch_injection.py --ignore=tests/test_multitouch_injection.py --ignore=tests/test_multitouch.py
    $testsExit = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previousErrorAction
    $env:QT_QPA_PLATFORM = $previousPlatform
}
if ($testsExit -ne 0) {
    throw "Tests failed (exit code $testsExit); refusing to build a release package"
}
python -m PyInstaller --noconfirm --clean MyScreenDraw.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed"
}

$package = Assert-PathWithin (Join-Path $root "dist\MyScreenDraw") $root -Recurse
$exe = Join-Path $package "MyScreenDraw.exe"
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "PyInstaller did not produce $exe"
}

# Keep notices visible beside the executable as well as bundled by the spec.
Copy-Item -LiteralPath (Join-Path $root "LICENSE") -Destination $package -Force
Copy-Item -LiteralPath (Join-Path $root "THIRD_PARTY_LICENSES.txt") -Destination $package -Force
[IO.Directory]::CreateDirectory((Assert-PathWithin (Join-Path $package "data") $package)) | Out-Null
[IO.Directory]::CreateDirectory((Assert-PathWithin (Join-Path $package "exports") $package)) | Out-Null

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
    if (-not (Test-Path -LiteralPath (Join-Path $package $relative) -PathType Leaf)) {
        throw "Release package is missing $relative"
    }
}

# A package must not inherit local user data, caches, source, or old logs.
$forbidden = Get-ChildItem -LiteralPath $package -Recurse -File -Force | Where-Object {
    $_.Name -match '^(config\.json|roster\.json|events\.jsonl|app\.log)$' -or
    $_.Extension -in @('.py', '.pyc', '.jsonl', '.tmp', '.png', '.jpg', '.jpeg') -or
    $_.FullName -match '\\autosave\\' -or
    $_.FullName -match '\\screenshots\\'
}
if ($forbidden) {
    throw "Release package contains user/runtime files: $($forbidden.FullName -join ', ')"
}

# Bind acceptance to the executable that was exercised, not a later replacement.
$hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
Invoke-Smoke $exe $package
if ((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant() -ne $hash) {
    throw 'Staging executable changed during smoke'
}

# Smoke creates runtime logs by design; remove all verification data before release.
foreach ($runtimeFile in @("data\config.json", "data\roster.json", "data\events.jsonl", "data\app.log")) {
    $target = Assert-PathWithin (Join-Path $package $runtimeFile) $package
    if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Force }
}
$runtimeAutosave = Assert-PathWithin (Join-Path $package "data\autosave") $package -Recurse
if (Test-Path -LiteralPath $runtimeAutosave) { Remove-Item -LiteralPath $runtimeAutosave -Recurse -Force }

$package = Assert-PathWithin $package $root -Recurse
$forbiddenAfterSmoke = Get-ChildItem -LiteralPath $package -Recurse -File -Force | Where-Object {
    $_.Name -match '^(config\.json|roster\.json|events\.jsonl|app\.log)$' -or
    $_.Extension -in @('.py', '.pyc', '.jsonl', '.tmp', '.png', '.jpg', '.jpeg') -or
    $_.FullName -match '\\autosave\\|\\screenshots\\'
}
if ($forbiddenAfterSmoke) {
    throw "Release package contains runtime or private files after smoke: $($forbiddenAfterSmoke.FullName -join ', ')"
}


$manifest = [ordered]@{
    app_version = $version
    executable = "MyScreenDraw.exe"
    sha256 = $hash
    hash_algorithm = "SHA-256"
    signature = "none"
    built_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    package_type = "PyInstaller onedir portable"
}
$manifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $package "RELEASE-MANIFEST.json") -Encoding utf8
# A failed build must never overwrite a previously accepted archive.
$zipPath = Assert-PathWithin (Join-Path $root ("MyScreenDraw-v{0}-windows-x64.zip" -f $version)) $root
$checksumPath = Assert-PathWithin "$zipPath.sha256" $root
$receiptPath = Assert-PathWithin (Join-Path $buildDir ("release-receipts\" + [IO.Path]::GetFileName($zipPath) + '.json')) $buildDir
$candidateDir = Assert-PathWithin (Join-Path $buildDir ('release-candidate-' + [guid]::NewGuid().ToString('N'))) $buildDir
[IO.Directory]::CreateDirectory($candidateDir) | Out-Null
$candidateZip = Assert-PathWithin (Join-Path $candidateDir 'candidate.zip') $candidateDir
$candidateChecksum = Assert-PathWithin (Join-Path $candidateDir 'candidate.sha256') $candidateDir
$candidateReceipt = Assert-PathWithin (Join-Path $candidateDir 'receipt.json') $candidateDir
$acceptancePath = Assert-PathWithin (Join-Path $candidateDir 'acceptance.json') $candidateDir
$verifyDir = Assert-PathWithin (Join-Path $candidateDir 'extracted') $candidateDir
$updateEntries = Get-ChildItem -LiteralPath $package -Force | Where-Object { $_.Name -notin @('data', 'exports') }
Compress-Archive -LiteralPath $updateEntries.FullName -DestinationPath $candidateZip -CompressionLevel Optimal
$validationJson = python -B release_artifact.py validate --zip $candidateZip --version $version
if ($LASTEXITCODE -ne 0) { throw 'Candidate ZIP failed release validation' }
$validation = $validationJson | ConvertFrom-Json
if ($validation.exe_sha256 -ne $hash) { throw 'ZIP executable differs from staging smoke executable' }
try {
    Expand-Archive -LiteralPath $candidateZip -DestinationPath $verifyDir
    python -B release_artifact.py check-extracted --zip $candidateZip --version $version --directory $verifyDir
    if ($LASTEXITCODE -ne 0) { throw 'Extracted files differ from candidate ZIP' }
    $extractedExe = Assert-PathWithin (Join-Path $verifyDir 'MyScreenDraw.exe') $verifyDir
    Invoke-Smoke $extractedExe $verifyDir
    if ((Get-FileHash -LiteralPath $extractedExe -Algorithm SHA256).Hash.ToLowerInvariant() -ne $hash) {
        throw 'Extracted EXE differs from staging smoke executable'
    }
} finally {
    $verifyDir = Assert-PathWithin $verifyDir $candidateDir -Recurse
    if (Test-Path -LiteralPath $verifyDir) { Remove-Item -LiteralPath $verifyDir -Recurse -Force }
}
# Written only after tests, both smoke processes, and full unzip verification succeeded.
@{
    schema = 1
    version = $version
    zip_sha256 = $validation.zip_sha256
    exe_sha256 = $hash
    checks = @{ unit_tests = $true; staging_smoke = $true; extracted_files = $true; extracted_smoke = $true }
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $acceptancePath -Encoding utf8
python -B release_artifact.py seal --zip $candidateZip --version $version --root $root --snapshot $sourceSnapshot --acceptance $acceptancePath --checksum $candidateChecksum --receipt $candidateReceipt
if ($LASTEXITCODE -ne 0) { throw 'Candidate sealing failed; formal artifacts left untouched' }

# Check both ends immediately before moving; the receipt is the last commit marker.
foreach ($source in @($candidateZip, $candidateChecksum, $candidateReceipt)) {
    $null = Assert-PathWithin $source $candidateDir
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Promotion source is not a file: $source" }
}
foreach ($destination in @($zipPath, $checksumPath, $receiptPath)) {
    $null = Assert-PathWithin $destination $root
    if (Test-Path -LiteralPath $destination -PathType Container) { throw "Destination is a directory: $destination" }
}
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($receiptPath)) | Out-Null
$candidateZip = Assert-PathWithin $candidateZip $candidateDir
$zipPath = Assert-PathWithin $zipPath $root
Move-Item -LiteralPath $candidateZip -Destination $zipPath -Force
$candidateChecksum = Assert-PathWithin $candidateChecksum $candidateDir
$checksumPath = Assert-PathWithin $checksumPath $root
Move-Item -LiteralPath $candidateChecksum -Destination $checksumPath -Force
$candidateReceipt = Assert-PathWithin $candidateReceipt $candidateDir
$receiptPath = Assert-PathWithin $receiptPath $buildDir
Move-Item -LiteralPath $candidateReceipt -Destination $receiptPath -Force
Write-Host "Portable build verified: $package (v$version, EXE SHA-256 $hash, ZIP SHA-256 $($validation.zip_sha256))"
