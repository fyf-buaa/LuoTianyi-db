# Batch_085 Verification Script
# Verifies 50 music markdown files against bilibili API
$musicDir = "D:\数据收集\luotianyi-db\processed\rag\music"
$reportDir = "D:\数据收集\luotianyi-db\processed\rag\.pipeline\verification_reports"
$suspiciousDir = "D:\数据收集\luotianyi-db\processed\rag\suspicious_music\Batch_085"
$batchFile = "D:\数据收集\luotianyi-db\processed\rag\batch_assignments.json"
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$reportFile = Join-Path $reportDir "Batch_085_verification_$timestamp.json"

# Load Batch_085 file list
$batchJson = Get-Content -Raw $batchFile | ConvertFrom-Json
$batchFiles = $batchJson.Batch_085 | ForEach-Object { $_.value }
Write-Host "Loaded $($batchFiles.Count) files from Batch_085"

# Results storage
$results = @()
$totalBVApiCalls = 0
$apiErrors = 0

foreach ($fileName in $batchFiles) {
    $filePath = Join-Path $musicDir $fileName
    $result = [PSCustomObject]@{
        fileName = $fileName
        slug = ""
        title = ""
        bvid = ""
        avNumber = ""
        apiBvid = ""
        apiTitle = ""
        apiUploader = ""
        apiViews = 0
        apiPublishDate = ""
        filePublishDate = ""
        fileCreator = ""
        fileTitle = ""
        apiStatus = "not_checked"
        classification = ""
        issues = @()
        apiResponseRaw = $null
    }
    
    # Check file exists
    if (-not (Test-Path -LiteralPath $filePath)) {
        $result.classification = "file_not_found"
        $result.issues += "File not found on disk"
        $results += $result
        continue
    }
    
    # Read file content
    $content = Get-Content -Raw -LiteralPath $filePath
    if (-not $content) {
        $result.classification = "file_not_found"
        $result.issues += "Could not read file"
        $results += $result
        continue
    }
    
    # Extract slug from first line (# music:slug)
    if ($content -match "^# music:(\S+)") {
        $result.slug = $matches[1]
    }
    
    # Extract title from second line (## title)
    if ($content -match "^##\s+(.+)$") {
        $result.title = $matches[1]
        $result.fileTitle = $matches[1]
    }
    
    # Extract fields from the markdown table
    # Title (曲名)
    if ($content -match '\|\s*曲名\s*\|\s*(.+?)\s*\|') {
        $result.fileTitle = $matches[1]
    }
    
    # P主/Creator
    if ($content -match '\|\s*P主\s*\|\s*(.+?)\s*\|') {
        $result.fileCreator = $matches[1]
    }
    
    # 发行日期
    if ($content -match '\|\s*发行日期\s*\|\s*(.+?)\s*\|') {
        $result.filePublishDate = $matches[1]
    }
    
    # 视频ID / BVID
    $bvid = ""
    $avMatch = $false
    if ($content -match '\|\s*视频ID\s*\|\s*(BV\w+)\s*\|') {
        $bvid = $matches[1].Trim()
        $result.bvid = $bvid
    }
    
    # Also check for AV numbers
    if ($content -match '\|\s*视频ID\s*\|\s*(av\d+)\s*\|') {
        $avNum = $matches[1].Trim()
        $result.avNumber = $avNum
        $avMatch = $true
    }
    
    # Also check for combined format: "BVxxxxx / avxxxxx"
    if ($content -match '\|\s*视频ID\s*\|\s*(BV\w+)\s*/\s*(av\d+)\s*\|') {
        $bvid = $matches[1].Trim()
        $result.bvid = $bvid
        $result.avNumber = $matches[2].Trim()
    }
    elseif ($content -match '\|\s*视频ID\s*\|\s*(av\d+)\s*/\s*(BV\w+)\s*\|') {
        $result.avNumber = $matches[1].Trim()
        $bvid = $matches[2].Trim()
        $result.bvid = $bvid
    }
    
    # Check links in source section for BVID
    if (-not $bvid) {
        if ($content -match 'bilibili\.com/video/(BV\w+)') {
            $bvid = $matches[1]
            $result.bvid = $bvid
        }
        elseif ($content -match 'bilibili\.com/video/(av\d+)') {
            $avNum = $matches[1]
            $result.avNumber = $avNum
            $avMatch = $true
        }
    }
    
    # If we have an AV number but no BV, set BV to AV for API call
    if (-not $bvid -and $avMatch -and $result.avNumber) {
        $bvid = $result.avNumber
    }
    
    # If no BVID found, classify as unverifiable
    if (-not $bvid) {
        $result.classification = "unverifiable"
        $result.issues += "No BVID or AV number found in file"
        $result.apiStatus = "skipped"
        $results += $result
        continue
    }
    
    # Call bilibili API
    $totalBVApiCalls++
    $isAvNumber = $bvid -match '^av\d+$'
    if ($isAvNumber) {
        $aid = [int]($bvid -replace 'av', '')
        $apiUrl = "https://api.bilibili.com/x/web-interface/view?aid=$aid"
        Write-Host "  Calling API for aid=$aid ($($result.fileTitle))..."
    }
    else {
        $apiUrl = "https://api.bilibili.com/x/web-interface/view?bvid=$bvid"
    }
    
    try {
        Write-Host "  Calling API for $bvid ($($result.fileTitle))..."
        $apiResponse = Invoke-RestMethod -Uri $apiUrl -Method Get -TimeoutSec 15 -ErrorAction Stop
        
        if ($apiResponse.code -ne 0) {
            $result.apiStatus = "error"
            $result.issues += "API returned error code $($apiResponse.code): $($apiResponse.message)"
            $result.classification = "unverifiable"
            $apiErrors++
            $results += $result
            continue
        }
        
        $data = $apiResponse.data
        $result.apiBvid = $data.bvid
        $result.apiTitle = $data.title
        $result.apiUploader = $data.owner.name
        $result.apiViews = $data.stat.view
        if ($data.pubdate) {
            $epoch = $data.pubdate
            $pubDate = [DateTimeOffset]::FromUnixTimeSeconds($epoch).LocalDateTime.ToString("yyyy-MM-dd")
            $result.apiPublishDate = $pubDate
        }
        $result.apiResponseRaw = @{
            bvid = $data.bvid
            title = $data.title
            owner = $data.owner.name
            mid = $data.owner.mid
            pubdate = $data.pubdate
            views = $data.stat.view
            danmaku = $data.stat.danmaku
            likes = $data.stat.like
            coins = $data.stat.coin
            favorites = $data.stat.favorite
            share = $data.stat.share
            tid = $data.tid
            tname = $data.tname
        }
        
        # Now classify the result
        # Start by assuming confirmed, add issues as we find them
        $result.apiStatus = "success"
        $issues = @()
        
        # Check title match
        $fileTitleClean = $result.fileTitle -replace '\s|-|_|\.|,|·|：|\(|\)|（|）|feat\.?|Feat\.?|FEAT\.?|cover|Cover|COVER|ver\.?|Ver\.?|VER\.?|VOCALOID|vocaloid', ''
        $apiTitleClean = $data.title -replace '\s|-|_|\.|,|·|：|\(|\)|（|）|feat\.?|Feat\.?|FEAT\.?|cover|Cover|COVER|ver\.?|Ver\.?|VER\.?|VOCALOID|vocaloid', ''
        $fileTitleLower = $fileTitleClean.ToLower()
        $apiTitleLower = $apiTitleClean.ToLower()
        
        $titleSimilar = $fileTitleLower -eq $apiTitleLower -or 
                        $fileTitleLower -match [regex]::Escape($apiTitleLower.Substring(0, [Math]::Min(4, $apiTitleLower.Length))) -or
                        $apiTitleLower -match [regex]::Escape($fileTitleLower.Substring(0, [Math]::Min(4, $fileTitleLower.Length))) -or
                        $apiTitleLower.Contains($fileTitleLower) -or
                        $fileTitleLower.Contains($apiTitleLower)
        
        if (-not $titleSimilar) {
            $issues += "Title mismatch: file='$($result.fileTitle)' vs api='$($data.title)'"
        }
        
        # Check publish date
        if ($result.filePublishDate -and $result.filePublishDate.Trim() -ne '' -and $pubDate) {
            if ($result.filePublishDate.Trim() -ne $pubDate) {
                $issues += "Date mismatch: file='$($result.filePublishDate)' vs api='$pubDate'"
            }
        }
        
        # Check BV match
        if ($result.bvid -and $result.bvid -ne $data.bvid) {
            $issues += "BV mismatch: file='$($result.bvid)' vs api='$($data.bvid)'"
        }
        
        # Check AV number
        if ($result.avNumber) {
            $expectedAid = [int]($result.avNumber -replace 'av', '')
            if ($data.aid -and $data.aid -ne $expectedAid) {
                $issues += "AV mismatch: file='$($result.avNumber)' vs api='av$($data.aid)'"
            }
        }
        
        # If we used an AV for the API call, store the returned BV
        if ($isAvNumber -and $data.bvid) {
            $result.bvid = $data.bvid
            $result.apiBvid = $data.bvid
        }
        
        # Classify based on issues
        if ($issues.Count -eq 0) {
            $result.classification = "confirmed"
        }
        elseif ($issues.Count -le 2) {
            $result.classification = "partial"
        }
        else {
            $result.classification = "conflict"
        }
        
        $result.issues = $issues
        
    }
    catch {
        $result.apiStatus = "error"
        $result.classification = "unverifiable"
        $result.issues += "API call failed: $_"
        $apiErrors++
        Write-Host "    API Error for $bvid : $_"
    }
    
    $results += $result
}

# Summarize classifications
$classCounts = $results | Group-Object classification | ForEach-Object { 
    [PSCustomObject]@{ Classification = $_.Name; Count = $_.Count }
}

Write-Host "`n===== VERIFICATION SUMMARY ====="
Write-Host "Total files: $($batchFiles.Count)"
Write-Host "API calls made: $totalBVApiCalls"
Write-Host "API errors: $apiErrors"
foreach ($cc in $classCounts) {
    Write-Host "  $($cc.Classification): $($cc.Count)"
}

# Build report
$report = [PSCustomObject]@{
    reportType = "Batch_085_Verification"
    batchName = "Batch_085"
    generatedAt = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    totalFiles = $batchFiles.Count
    apiCallsMade = $totalBVApiCalls
    apiErrors = $apiErrors
    classificationSummary = $classCounts
    results = $results
}

# Save report
$reportJson = $report | ConvertTo-Json -Depth 10
$reportJson | Out-File -FilePath $reportFile -Encoding utf8
Write-Host "`nReport saved to: $reportFile"

# Copy suspicious files (conflict or partial)
$suspiciousFiles = $results | Where-Object { $_.classification -eq "conflict" -or $_.classification -eq "partial" }
if ($suspiciousFiles.Count -gt 0) {
    Write-Host "`nCopying $($suspiciousFiles.Count) suspicious files to $suspiciousDir ..."
    foreach ($sf in $suspiciousFiles) {
        $srcPath = Join-Path $musicDir $sf.fileName
        $dstPath = Join-Path $suspiciousDir $sf.fileName
        if (Test-Path -LiteralPath $srcPath) {
            Copy-Item -LiteralPath $srcPath -Destination $dstPath -Force
            Write-Host "  Copied: $($sf.fileName) ($($sf.classification))"
        }
    }
}
else {
    Write-Host "`nNo suspicious files to copy."
}

Write-Host "`n===== DETAILED RESULTS ====="
foreach ($r in $results) {
    $statusIcon = switch ($r.classification) {
        "confirmed" { "[OK]" }
        "partial" { "[~]" }
        "conflict" { "[X]" }
        "unverifiable" { "[?]" }
        "file_not_found" { "[!]" }
    }
    Write-Host "$statusIcon $($r.fileName) -> $($r.classification)"
    if ($r.bvid) { Write-Host "       BV: $($r.bvid)" }
    if ($r.issues.Count -gt 0) {
        foreach ($issue in $r.issues) {
            Write-Host "       Issue: $issue"
        }
    }
}

Write-Host "`nDone."
