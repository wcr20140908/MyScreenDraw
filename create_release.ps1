param([Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{40}$')][string]$Commit)
$ErrorActionPreference = 'Stop'
# PS 5.1 progress rendering makes multi-MB uploads CPU-bound.
$ProgressPreference = 'SilentlyContinue'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root
$token = $env:GITHUB_TOKEN
if (-not $token) { throw 'GITHUB_TOKEN environment variable not set' }
$repo = 'wcr20140908/MyScreenDraw'
$version = (& python -c "from version import VERSION; print(VERSION)").Trim()
if ($LASTEXITCODE -ne 0 -or $version -ne '6.0.0-beta.7') { throw 'Unexpected release version' }
$tag = "v$version"
$asset = "MyScreenDraw-$tag-windows-x64.zip"
$assetPath = Join-Path $root $asset
$notesPath = Join-Path $root "release-notes-$tag.md"
if (-not (Test-Path -LiteralPath $assetPath -PathType Leaf)) { throw "Missing release asset: $asset" }
$notes = [IO.File]::ReadAllText($notesPath, [Text.Encoding]::UTF8)
python -c "import sys; from main import validate_update_zip; validate_update_zip(sys.argv[1])" $assetPath
if ($LASTEXITCODE -ne 0) { throw 'Update archive validation failed' }
$hash = (Get-FileHash -LiteralPath $assetPath -Algorithm SHA256).Hash.ToLowerInvariant()
$checksumPath = "$assetPath.sha256"
"$hash  $asset" | Set-Content -LiteralPath $checksumPath -Encoding ascii
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
$payload = @{
    tag_name = $tag
    target_commitish = $Commit
    name = "MyScreenDraw $tag (Preview)"
    body = $notes
    draft = $true
    prerelease = $true
} | ConvertTo-Json -Depth 10
$release = Invoke-RestMethod -Uri "$api/releases" -Method Post -Headers $headers -Body ([Text.Encoding]::UTF8.GetBytes($payload)) -ContentType 'application/json; charset=utf-8'
$upload = $release.upload_url -replace '\{.*\}', ''
foreach ($path in @($assetPath, $checksumPath)) {
    $name = Split-Path -Leaf $path
    $mime = if ($path.EndsWith('.zip')) { 'application/zip' } else { 'text/plain' }
    $uploaded = Invoke-RestMethod -Uri ($upload + '?name=' + [uri]::EscapeDataString($name)) -Method Post -Headers $headers -ContentType $mime -InFile $path
    if ($uploaded.state -ne 'uploaded' -or $uploaded.size -ne (Get-Item -LiteralPath $path).Length) { throw "Asset upload verification failed: $name" }
}
$published = Invoke-RestMethod -Uri "$api/releases/$($release.id)" -Method Patch -Headers $headers -Body '{"draft":false}' -ContentType 'application/json'
Write-Host "Release published: $($published.html_url)"
Write-Host "ZIP SHA-256: $hash"
