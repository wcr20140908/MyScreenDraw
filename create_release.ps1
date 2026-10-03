param([Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{40}$')][string]$Commit)
$ErrorActionPreference = 'Stop'
# PS 5.1 progress rendering makes multi-MB uploads CPU-bound.
$ProgressPreference = 'SilentlyContinue'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root
$repo = 'wcr20140908/MyScreenDraw'
$version = (& python -c "from version import VERSION; print(VERSION)").Trim()
if ($LASTEXITCODE -ne 0 -or $version -ne '6.0.0') { throw 'Unexpected release version' }
$tag = "v$version"
$asset = "MyScreenDraw-$tag-windows-x64.zip"
$assetPath = Join-Path $root $asset
$notesPath = Join-Path $root "release-notes-$tag.md"
if (-not (Test-Path -LiteralPath $assetPath -PathType Leaf)) { throw "Missing release asset: $asset" }
$notes = [IO.File]::ReadAllText($notesPath, [Text.Encoding]::UTF8)
$checksumPath = "$assetPath.sha256"
$receiptPath = Join-Path $root ("build\release-receipts\$asset.json")
# Read-only gates: never repair checksums/receipts to bless an unaccepted package.
$verificationJson = python -B release_artifact.py verify --zip $assetPath --version $version --root $root --checksum $checksumPath --receipt $receiptPath --commit $Commit
if ($LASTEXITCODE -ne 0) { throw 'Release artifact/source/commit verification failed' }
$verified = $verificationJson | ConvertFrom-Json
$hash = $verified.zip_sha256
$token = $env:GITHUB_TOKEN
if (-not $token) { throw 'GITHUB_TOKEN environment variable not set' }
$headers = @{
    Authorization = "Bearer $token"
    Accept = 'application/vnd.github+json'
    'X-GitHub-Api-Version' = '2022-11-28'
    'User-Agent' = 'MyScreenDraw-release'
}
$api = "https://api.github.com/repos/$repo"
# Refuse to overwrite an existing release or asset. A failed upload leaves a draft.
$existing = $null
try { $existing = Invoke-RestMethod -Uri "$api/releases/tags/$tag" -Headers $headers }
catch { if (-not $_.Exception.Response -or [int]$_.Exception.Response.StatusCode -ne 404) { throw } }
if ($existing) { throw "Release $tag already exists; refusing to overwrite" }
# A remote tag already pointing elsewhere must not override target_commitish.
$remoteCommit = Invoke-RestMethod -Uri "$api/commits/$Commit" -Headers $headers
if ($remoteCommit.sha -ne $Commit) { throw 'Release commit is not available on GitHub' }
$remoteTag = $null
try { $remoteTag = Invoke-RestMethod -Uri "$api/commits/$tag" -Headers $headers }
catch { if (-not $_.Exception.Response -or [int]$_.Exception.Response.StatusCode -ne 404) { throw } }
if ($remoteTag -and $remoteTag.sha -ne $Commit) { throw 'Remote release tag points at a different commit' }
$payload = @{
    tag_name = $tag
    target_commitish = $Commit
    name = "MyScreenDraw $tag"
    body = $notes
    draft = $true
    prerelease = $false
} | ConvertTo-Json -Depth 10
$release = Invoke-RestMethod -Uri "$api/releases" -Method Post -Headers $headers -Body ([Text.Encoding]::UTF8.GetBytes($payload)) -ContentType 'application/json; charset=utf-8'
$upload = $release.upload_url -replace '\{.*\}', ''
foreach ($path in @($assetPath, $checksumPath)) {
    $name = Split-Path -Leaf $path
    $mime = if ($path.EndsWith('.zip')) { 'application/zip' } else { 'text/plain' }
    $uploaded = Invoke-RestMethod -Uri ($upload + '?name=' + [uri]::EscapeDataString($name)) -Method Post -Headers $headers -ContentType $mime -InFile $path
    if ($uploaded.state -ne 'uploaded' -or $uploaded.size -ne (Get-Item -LiteralPath $path).Length) { throw "Asset upload verification failed: $name" }
}
# Changed inputs during upload leave a draft rather than publishing stale evidence.
python -B release_artifact.py verify --zip $assetPath --version $version --root $root --checksum $checksumPath --receipt $receiptPath --commit $Commit
if ($LASTEXITCODE -ne 0) { throw 'Release inputs changed; draft left unpublished' }
$published = Invoke-RestMethod -Uri "$api/releases/$($release.id)" -Method Patch -Headers $headers -Body '{"draft":false}' -ContentType 'application/json'
Write-Host "Release published: $($published.html_url)"
Write-Host "ZIP SHA-256: $hash"
