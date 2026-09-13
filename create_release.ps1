$token = $env:GITHUB_TOKEN
if (-not $token) {
    Write-Host "Error: GITHUB_TOKEN environment variable not set"
    exit 1
}
$repo = "wcr20140908/MyScreenDraw"
$tag = "v6.0.0-beta.1"

$releaseNotes = Get-Content "release-notes-v6.0.0-beta.1.md" -Raw -Encoding UTF8

$payload = @{
    tag_name = $tag
    name = "MyScreenDraw v6.0.0-beta.1 (Preview)"
    body = $releaseNotes
    draft = $false
    prerelease = $true
}

$jsonPayload = $payload | ConvertTo-Json -Depth 10
$utf8Bytes = [System.Text.Encoding]::UTF8.GetBytes($jsonPayload)

$headers = @{
    "Authorization" = "Bearer $token"
    "Accept" = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
    "User-Agent" = "PowerShell"
}

try {
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/releases" `
        -Method Post `
        -Headers $headers `
        -Body $utf8Bytes `
        -ContentType "application/json; charset=utf-8"

    Write-Host "✓ Release created successfully!"
    Write-Host "URL: $($release.html_url)"
    Write-Host "Release ID: $($release.id)"

    # Save for asset upload
    $release.id | Out-File "release_id.txt"
    ($release.upload_url -replace '\{.*\}', '') | Out-File "upload_url.txt"

    $release
} catch {
    Write-Host "Error creating release:"
    Write-Host $_.Exception.Message
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $reader.BaseStream.Position = 0
        $reader.DiscardBufferedData()
        $responseBody = $reader.ReadToEnd()
        Write-Host "Response: $responseBody"
    }
    exit 1
}
