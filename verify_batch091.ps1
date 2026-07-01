# Batch_091 Verification Script
param(
    [string]$MusicDir = "D:\数据收集\luotianyi-db\processed\rag\music",
    [string]$ReportDir = "D:\数据收集\luotianyi-db\processed\rag\.pipeline\verification_reports",
    [string]$SuspiciousDir = "D:\数据收集\luotianyi-db\processed\rag\suspicious_music\Batch_091",
    [string]$BatchFile = "D:\数据收集\luotianyi-db\processed\rag\batch_assignments.json"
)

# Ensure target dirs exist
if (-not (Test-Path -LiteralPath $ReportDir)) { New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null }
if (-not (Test-Path -LiteralPath $SuspiciousDir)) { New-Item -ItemType Directory -Path $SuspiciousDir -Force | Out-Null }

$json = Get-Content -LiteralPath $BatchFile -Raw
$obj = $json | ConvertFrom-Json
$batch091 = $obj.Batch_091

$results = @()

# Helper: extract metadata from markdown file
function Extract-Metadata {
    param([string]$FilePath)
    $content = Get-Content -LiteralPath $FilePath -Encoding utf8 -Raw
    $meta = @{
        title = ""
        creator = ""
        singer = ""
        bvid = ""
        play_count = ""
        engine = ""
        publish_date = ""
        source = ""
    }
    
    # Extract title from ## line
    if ($content -match '^##\s+(.+)$') {
        $meta.title = $matches[1].Trim()
    }
    
    # Extract fields from markdown table
    # P主 (creator)
    if ($content -match '\|\s*P主\s*\|\s*(.+?)\s*\|') {
        $meta.creator = $matches[1].Trim()
    }
    
    # 演唱 (singer)
    if ($content -match '\|\s*演唱\s*\|\s*(.+?)\s*\|') {
        $meta.singer = $matches[1].Trim()
    }
    
    # 视频ID (BVID)
    if ($content -match '\|\s*视频ID\s*\|\s*(.+?)\s*\|') {
        $bvid = $matches[1].Trim()
        if ($bvid -match '(BV\w+)') {
            $meta.bvid = $matches[1]
        }
    }
    
    # Also check for AV/BV in source links
    if (-not $meta.bvid) {
        if ($content -match 'bilibili\.com/video/(BV\w+)') {
            $meta.bvid = $matches[1]
        }
        elseif ($content -match 'bilibili\.com/video/av(\d+)') {
            $meta.source = "av$($matches[1])"
        }
    }
    
    # 播放量
    if ($content -match '\|\s*播放量\s*\|\s*(.+?)\s*\|') {
        $meta.play_count = $matches[1].Trim()
    }
    
    # 引擎
    if ($content -match '\|\s*引擎\s*\|\s*(.+?)\s*\|') {
        $meta.engine = $matches[1].Trim()
    }
    
    # 发行日期
    if ($content -match '\|\s*发行日期\s*\|\s*(.+?)\s*\|') {
        $meta.publish_date = $matches[1].Trim()
    }
    
    return $meta
}

# Helper: normalize strings for comparison
function Normalize-Str {
    param([string]$s)
    return $s.Trim().ToLowerInvariant() -replace '\s+', ' ' -replace '[^\w\s]', ''
}

# Helper: compare if two names are similar
function Similar-Name {
    param([string]$a, [string]$b)
    $na = Normalize-Str $a
    $nb = Normalize-Str $b
    if ($na -eq $nb) { return $true }
    # Check containment
    if ($na -and $nb -and ($na.Contains($nb) -or $nb.Contains($na))) { return $true }
    return $false
}

# Also try approximate file match
function Find-File {
    param([string]$FileName)
    $fullpath = Join-Path $MusicDir $FileName
    if (Test-Path -LiteralPath $fullpath) {
        return @{Path=$fullpath; Name=$FileName}
    }
    return $null
}

$count = 0
$total = $batch091.Count

foreach ($item in $batch091) {
    $requestedFile = $item.value
    $count++
    Write-Host "[$count/$total] Processing: $requestedFile"
    
    $fileInfo = Find-File $requestedFile
    if (-not $fileInfo) {
        Write-Host "  -> FILE NOT FOUND"
        $results += [PSCustomObject]@{
            file = $requestedFile
            file_metadata = $null
            api_data = $null
            bvid = ""
            classification = "file_not_found"
            issues = @("File does not exist in music directory")
        }
        continue
    }
    
    $actualFile = $fileInfo.Name
    $filePath = $fileInfo.Path
    
    # Extract metadata
    $meta = Extract-Metadata $filePath
    
    $issues = @()
    $bvid = $meta.bvid
    $apiData = $null
    
    $fileMetaForReport = @{
        title = $meta.title
        creator = $meta.creator
        singer = $meta.singer
        engine = $meta.engine
    }
    if ($meta.bvid) { $fileMetaForReport.bvid = $meta.bvid }
    if ($meta.play_count) { $fileMetaForReport.play_count = $meta.play_count }
    if ($meta.publish_date) { $fileMetaForReport.publish_date = $meta.publish_date }
    
    if ($bvid) {
        # Call bilibili API
        $apiUrl = "https://api.bilibili.com/x/web-interface/view?bvid=$bvid"
        try {
            $response = Invoke-RestMethod -Uri $apiUrl -Method Get -TimeoutSec 15
            if ($response.code -eq 0 -and $response.data) {
                $data = $response.data
                $pubDate = [System.DateTimeOffset]::FromUnixTimeSeconds($data.pubdate).ToString("yyyy-MM-dd")
                $ownerName = $data.owner.name
                $apiTitle = $data.title
                
                $apiData = @{
                    bvid = $data.bvid
                    title = $apiTitle
                    owner = $ownerName
                    view = $data.stat.view
                    like = $data.stat.like
                    danmaku = $data.stat.danmaku
                    pubdate = $pubDate
                    ts = $data.pubdate
                    duration = $data.duration
                }
                
                # Compare
                # 1. Title comparison
                $fileTitleNorm = Normalize-Str $meta.title
                $apiTitleNorm = Normalize-Str $apiTitle
                $titleOk = $false
                if ($fileTitleNorm -and $apiTitleNorm) {
                    if ($fileTitleNorm -eq $apiTitleNorm -or $apiTitleNorm.Contains($fileTitleNorm) -or $fileTitleNorm.Contains($apiTitleNorm)) {
                        $titleOk = $true
                    }
                }
                if (-not $titleOk -and $fileTitleNorm -and $apiTitleNorm) {
                    $issues += "Title mismatch: file='$($meta.title)' vs api='$apiTitle'"
                }
                
                # 2. Creator comparison  
                $fileCreator = $meta.creator -replace '^creator:', ''
                $apiCreator = $ownerName
                $creatorOk = $false
                if ($fileCreator -and $apiCreator) {
                    if (Similar-Name $fileCreator $apiCreator) {
                        $creatorOk = $true
                    }
                }
                if (-not $creatorOk -and $fileCreator -and $apiCreator) {
                    $issues += "Creator mismatch: file='$($meta.creator)' vs api='$apiCreator'"
                }
                
                # 3. Date comparison (if present in file)
                if ($meta.publish_date) {
                    # Try to normalize date
                    $fileDate = $meta.publish_date.Trim()
                    if ($fileDate -match '\d{4}-\d{2}-\d{2}') {
                        if ($matches[0] -ne $pubDate) {
                            $issues += "Date mismatch: file='$fileDate' vs api='$pubDate'"
                        }
                    }
                }
                
                # 4. Play count comparison (if present)
                if ($meta.play_count -and $meta.play_count -ne '未知' -and $meta.play_count -ne '') {
                    $pc = $meta.play_count -replace '[^0-9.]', ''
                    if ($pc -and $data.stat.view) {
                        $fileViews = [double]$pc * 10000  # 约3.1万 -> 31000
                        # Loose comparison
                        $ratio = [Math]::Abs($fileViews - $data.stat.view) / [Math]::Max($fileViews, $data.stat.view)
                        if ($ratio -gt 0.3) {
                            $issues += "Play count mismatch: file='$($meta.play_count)' vs api=$($data.stat.view)"
                        }
                    }
                }
                
            } else {
                $apiData = $null
                $issues += "Bilibili API returned error for $bvid"
            }
        } catch {
            $apiData = $null
            $issues += "API request failed for $bvid"
        }
    } else {
        $issues += "No BVID found in file"
    }
    
    # Classification
    $classification = ""
    if ($apiData -ne $null) {
        if ($issues.Count -eq 0) {
            $classification = "confirmed"
        } else {
            $classification = "partial"
        }
    } elseif ($issues -contains "No BVID found in file") {
        $classification = "unverifiable"
    } else {
        $classification = "conflict"
    }
    
    $resultEntry = @{
        file = $actualFile
        file_metadata = $fileMetaForReport
        api_data = $apiData
        bvid = $bvid
        classification = $classification
        issues = $issues
    }
    
    $results += [PSCustomObject]$resultEntry
    
    if ($classification -eq "partial" -or $classification -eq "conflict") {
        Write-Host "  -> $classification - Issues: $($issues -join '; ')"
        # Copy suspicious file
        Copy-Item -LiteralPath $filePath -Destination (Join-Path $SuspiciousDir $actualFile) -Force
    } elseif ($classification -eq "file_not_found") {
        Write-Host "  -> file_not_found"
    } else {
        Write-Host "  -> $classification"
    }
    
    # Rate limiting
    Start-Sleep -Milliseconds 300
}

# Summary
$summary = @{
    confirmed = ($results | Where-Object { $_.classification -eq "confirmed" }).Count
    partial = ($results | Where-Object { $_.classification -eq "partial" }).Count
    unverifiable = ($results | Where-Object { $_.classification -eq "unverifiable" }).Count
    conflict = ($results | Where-Object { $_.classification -eq "conflict" }).Count
    file_not_found = ($results | Where-Object { $_.classification -eq "file_not_found" }).Count
}

$suspiciousFiles = $results | Where-Object { $_.classification -in @("partial", "conflict") } | ForEach-Object { $_.file }

# Build report
$report = @{
    batch_id = "Batch_091"
    verified_date = "2026-06-08"
    total_files = $total
    summary = $summary
    suspicious_files = @($suspiciousFiles)
    details = @($results)
}

# Save report
$reportPath = Join-Path $ReportDir "Batch_091_verification.json"
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $reportPath -Encoding utf8

Write-Host ""
Write-Host "========================================"
Write-Host "Batch_091 Verification Complete"
Write-Host "========================================"
Write-Host "Total: $total"
Write-Host "Confirmed: $($summary.confirmed)"
Write-Host "Partial: $($summary.partial)"
Write-Host "Unverifiable: $($summary.unverifiable)"
Write-Host "Conflict: $($summary.conflict)"
Write-Host "File Not Found: $($summary.file_not_found)"
if ($suspiciousFiles.Count -gt 0) {
    Write-Host "Suspicious files copied to: $SuspiciousDir"
    $suspiciousFiles | ForEach-Object { Write-Host "  - $_" }
}
Write-Host "Report saved to: $reportPath"
