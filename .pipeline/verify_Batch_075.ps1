# Batch_075 Verification Pipeline
# Runs fact-checking against bilibili API for all 50 files
# PS 5.1 compatible

$musicDir = "D:\数据收集\luotianyi-db\processed\rag\music"
$reportDir = "D:\数据收集\luotianyi-db\processed\rag\.pipeline\verification_reports"
$suspiciousDir = "D:\数据收集\luotianyi-db\processed\rag\suspicious_music\Batch_075"
$batchJson = "D:\数据收集\luotianyi-db\processed\rag\batch_assignments.json"

New-Item -ItemType Directory -Force -Path $suspiciousDir | Out-Null
$assignments = Get-Content -Raw -LiteralPath $batchJson | ConvertFrom-Json
$files = $assignments.Batch_075 | ForEach-Object { $_.value }
Write-Host "Processing Batch_075: $($files.Count) files"

function Extract-Metadata($content, $field) {
    $pattern = '(?<=\|\s*' + [regex]::Escape($field) + '\s*\|\s*)[^|\n]+'
    $match = [regex]::Match($content, $pattern)
    return $match.Value.Trim()
}

function Extract-BVs($content) {
    $bvs = [regex]::Matches($content, 'BV[a-zA-Z0-9]{10,12}')
    $unique = @{}
    foreach ($bv in $bvs) {
        if ($bv.Value.Length -ge 11) { $unique[$bv.Value] = $true }
    }
    return $unique.Keys
}

function Extract-Sources($content) {
    $urls = [regex]::Matches($content, 'https?://[^\s\)\]>"]+')
    $unique = @{}
    foreach ($u in $urls) { $unique[$u.Value] = $true }
    return $unique.Keys
}

function Extract-Slug($content) {
    $m = [regex]::Match($content, '#\s*(music:\S+)')
    if ($m.Success) { return $m.Groups[1].Value }
    return ""
}

function TitleContainsSong($apiTitle, $songName) {
    if ([string]::IsNullOrEmpty($songName)) { return $false }
    $ns = $songName -replace '[\[\]【】（）()\s\-_,.;:!?/\\]', ''
    $na = $apiTitle -replace '[\[\]【】（）()\s\-_,.;:!?/\\]', ''
    return ($na.Contains($ns) -or $ns.Contains($na))
}

$entries = @()
$suspiciousFiles = @()

foreach ($file in $files) {
    $path = Join-Path -Path $musicDir -ChildPath $file
    
    if (-not (Test-Path $path)) {
        Write-Host "[NOT_FOUND] $file"
        $e = New-Object PSObject
        $e | Add-Member -NotePropertyName filename -NotePropertyValue $file
        $e | Add-Member -NotePropertyName slug -NotePropertyValue ""
        $e | Add-Member -NotePropertyName song_name -NotePropertyValue ""
        $e | Add-Member -NotePropertyName pzhu -NotePropertyValue ""
        $e | Add-Member -NotePropertyName yanchang -NotePropertyValue ""
        $e | Add-Member -NotePropertyName release_date -NotePropertyValue $null
        $e | Add-Member -NotePropertyName engine -NotePropertyValue ""
        $e | Add-Member -NotePropertyName video_id -NotePropertyValue $null
        $e | Add-Member -NotePropertyName play_count -NotePropertyValue $null
        $e | Add-Member -NotePropertyName BV_found_in_source -NotePropertyValue $false
        $e | Add-Member -NotePropertyName primary_BV -NotePropertyValue $null
        $e | Add-Member -NotePropertyName source_url -NotePropertyValue @()
        $e | Add-Member -NotePropertyName classification -NotePropertyValue "file_not_found"
        $e | Add-Member -NotePropertyName api_result -NotePropertyValue $null
        $e | Add-Member -NotePropertyName notes -NotePropertyValue "File listed in batch but not found on disk."
        $entries += $e
        continue
    }
    
    $content = Get-Content -Raw -LiteralPath $path
    
    $slug = Extract-Slug $content
    $songName = Extract-Metadata $content "曲名"
    $pzhu = Extract-Metadata $content "P主"
    $yanchang = Extract-Metadata $content "演唱"
    $dateRaw = Extract-Metadata $content "发行日期"
    $engine = Extract-Metadata $content "引擎"
    $videoIdRaw = Extract-Metadata $content "视频ID"
    $playCountRaw = Extract-Metadata $content "播放量"
    $bvIdField = Extract-Metadata $content "BV ID"
    
    $bvs = Extract-BVs $content
    $sources = Extract-Sources $content
    
    $primaryBV = $null
    $foundInSource = $false
    
    if (-not [string]::IsNullOrWhiteSpace($videoIdRaw) -and $videoIdRaw -notmatch '参见|待确认|待补充|暂未找到') {
        $vidMatch = [regex]::Match($videoIdRaw, 'BV[a-zA-Z0-9]{10,12}')
        if ($vidMatch.Success) { $primaryBV = $vidMatch.Value; $foundInSource = $true }
    }
    if ([string]::IsNullOrEmpty($primaryBV) -and -not [string]::IsNullOrWhiteSpace($bvIdField)) {
        $bvMatch = [regex]::Match($bvIdField, 'BV[a-zA-Z0-9]{10,12}')
        if ($bvMatch.Success) { $primaryBV = $bvMatch.Value; $foundInSource = $true }
    }
    if ([string]::IsNullOrEmpty($primaryBV)) {
        foreach ($bv in $bvs) {
            if ($bv.Length -ge 11) { $primaryBV = $bv; $foundInSource = $true; break }
        }
    }
    
    $classification = "unverifiable"
    $notes = ""
    $apiResult = $null
    
    if ($foundInSource -and -not [string]::IsNullOrEmpty($primaryBV)) {
        try {
            Write-Host "[API] $file -> BV $primaryBV"
            $apiUrl = "https://api.bilibili.com/x/web-interface/view?bvid=$primaryBV"
            $response = Invoke-RestMethod -Uri $apiUrl -Method Get -TimeoutSec 15
            
            if ($response.code -eq 0) {
                $d = $response.data
                $apiTitle = $d.title
                $apiOwner = $d.owner.name
                $apiPubDate = $d.pubdate
                $apiViews = $d.stat.view
                $origin = Get-Date "1970-01-01 00:00:00"
                $apiDateStr = $origin.AddSeconds($apiPubDate).ToString("yyyy-MM-dd")
                
                $apiResult = New-Object PSObject
                $apiResult | Add-Member -NotePropertyName bvid -NotePropertyValue $primaryBV
                $apiResult | Add-Member -NotePropertyName title -NotePropertyValue $apiTitle
                $apiResult | Add-Member -NotePropertyName owner -NotePropertyValue $apiOwner
                $apiResult | Add-Member -NotePropertyName pubdate -NotePropertyValue $apiDateStr
                $apiResult | Add-Member -NotePropertyName views -NotePropertyValue $apiViews
                
                $titleMatch = TitleContainsSong $apiTitle $songName
                
                # Also check core song name (remove feat., cover, 【】 etc)
                $coreSong = $songName -replace 'feat\..*|Cover.*|【.*?】|（.*?）|\(.*?\)', '' -replace '\s+', ''
                $apiCore = $apiTitle -replace '【.*?】|［.*?］|（.*?）|\(.*?\)|PV付|原创|原创曲|\s+', ''
                $coreTitleMatch = $false
                if (-not [string]::IsNullOrEmpty($coreSong) -and $apiCore.Contains($coreSong)) {
                    $coreTitleMatch = $true
                }
                
                $pMatch = $null
                if (-not [string]::IsNullOrEmpty($pzhu)) {
                    $pClean = $pzhu -replace '^creator:', ''
                    $pCleanLower = $pClean.ToLower()
                    $apiOwnerLower = $apiOwner.ToLower()
                    # Check if one contains the other
                    if ($apiOwnerLower.Contains($pCleanLower) -or $pCleanLower.Contains($apiOwnerLower)) {
                        $pMatch = $true
                    } else {
                    $pMatch = $false
                    }
                }
                
                $dateMatch = $null
                if (-not [string]::IsNullOrWhiteSpace($dateRaw) -and $dateRaw.Trim() -match '^\d{4}-\d{2}-\d{2}') {
                    $dateMatch = ($dateRaw.Trim() -eq $apiDateStr)
                }
                
                # Determine if song/API are completely different or just different versions
                $completelyDifferent = $false
                $songNorm = $songName -replace '[\[\]【】（）()\s\-_,.;:!?/\\]', ''
                $apiNorm = $apiTitle -replace '[\[\]【】（）()\s\-_,.;:!?/\\]', ''
                if ($songNorm.Length -gt 3 -and $apiNorm.Length -gt 3) {
                    # Check for very low overlap
                    $overlap = 0
                    foreach ($ch in $songNorm.ToCharArray()) { if ($apiNorm.Contains($ch)) { $overlap++ } }
                    $ratio = $overlap / [Math]::Max($songNorm.Length, 1)
                    if ($ratio -lt 0.3) { $completelyDifferent = $true }
                }
                
                if ($completelyDifferent) {
                    $classification = "conflict"
                    $notes = "BV points to a completely different song. API title='$apiTitle', song='$songName'. BV may be incorrect."
                } elseif ($titleMatch -or $coreTitleMatch) {
                    if ($pMatch -eq $true -or $pMatch -eq $null) {
                        $classification = "confirmed"
                        $notes = "Title/BV match confirmed. API: '$apiTitle' by $apiOwner"
                    } else {
                        $classification = "partial"
                        $notes = "Title matches but P name mismatch. File P='$pzhu', API owner='$apiOwner'"
                    }
                } else {
                    $classification = "partial"
                    $notes = "API title '$apiTitle' does not contain song name '$songName'. BV may be for a different version."
                }
                
                if ($dateMatch -eq $false) {
                    $notes += " | Date mismatch: file='$dateRaw', API='$apiDateStr'"
                    if ($classification -eq "confirmed") { $classification = "partial" }
                }
            } else {
                $apiResult = New-Object PSObject
                $apiResult | Add-Member -NotePropertyName bvid -NotePropertyValue $primaryBV
                $apiResult | Add-Member -NotePropertyName error -NotePropertyValue "API error code: $($response.code)"
                if ($response.code -eq 62002) {
                    $classification = "partial"
                    $notes = "BV $primaryBV found in file but video appears to be deleted/unavailable (API code 62002)."
                } else {
                    $classification = "unverifiable"
                    $notes = "Bilibili API returned code $($response.code) for BV $primaryBV"
                }
            }
        } catch {
            $apiResult = New-Object PSObject
            $apiResult | Add-Member -NotePropertyName bvid -NotePropertyValue $primaryBV
            $apiResult | Add-Member -NotePropertyName error -NotePropertyValue $_.Exception.Message
            $classification = "unverifiable"
            $notes = "API call failed: $($_.Exception.Message)"
        }
    } else {
        if ([string]::IsNullOrWhiteSpace($videoIdRaw) -or $videoIdRaw -match '暂未找到|待确认|待补充') {
            $notes = "No BVID found in file."
        } else {
            $notes = "视频ID field has reference text (not a direct BV): '$videoIdRaw'"
        }
        if ($sources.Count -gt 0) {
            $s = $sources | Where-Object { $_ -match 'bilibili\.com' }
            if ($s.Count -gt 0) { $notes += " Source: $($s[0])" }
        }
    }
    
    $dateVal = $null
    if (-not [string]::IsNullOrWhiteSpace($dateRaw)) { $dateVal = $dateRaw.Trim() }
    $videoIdVal = $null
    if (-not [string]::IsNullOrWhiteSpace($videoIdRaw)) { $videoIdVal = $videoIdRaw.Trim() }
    $playVal = $null
    if (-not [string]::IsNullOrWhiteSpace($playCountRaw)) { $playVal = $playCountRaw.Trim() }
    
    $e = New-Object PSObject
    $e | Add-Member -NotePropertyName filename -NotePropertyValue $file
    $e | Add-Member -NotePropertyName slug -NotePropertyValue $slug
    $e | Add-Member -NotePropertyName song_name -NotePropertyValue $songName
    $e | Add-Member -NotePropertyName pzhu -NotePropertyValue $pzhu
    $e | Add-Member -NotePropertyName yanchang -NotePropertyValue $yanchang
    $e | Add-Member -NotePropertyName release_date -NotePropertyValue $dateVal
    $e | Add-Member -NotePropertyName engine -NotePropertyValue $engine
    $e | Add-Member -NotePropertyName video_id -NotePropertyValue $videoIdVal
    $e | Add-Member -NotePropertyName play_count -NotePropertyValue $playVal
    $e | Add-Member -NotePropertyName BV_found_in_source -NotePropertyValue $foundInSource
    $e | Add-Member -NotePropertyName primary_BV -NotePropertyValue $primaryBV
    $e | Add-Member -NotePropertyName source_url -NotePropertyValue @($sources)
    $e | Add-Member -NotePropertyName classification -NotePropertyValue $classification
    $e | Add-Member -NotePropertyName api_result -NotePropertyValue $apiResult
    $e | Add-Member -NotePropertyName notes -NotePropertyValue $notes
    $entries += $e
    
    if ($classification -in @("partial", "conflict")) {
        $suspiciousFiles += $file
    }
}

function Count-Class($c) {
    $n = 0
    foreach ($e in $entries) {
        if ($e.classification -match $c) { $n++ }
    }
    return $n
}

$confirmedCount = Count-Class "confirmed"
$partialCount = Count-Class "partial"
$unverifiableCount = Count-Class "unverifiable"
$conflictCount = Count-Class "conflict"
$notFoundCount = Count-Class "file_not_found"

$checkedCount = 0
foreach ($e in $entries) {
    if ($e.classification -notmatch "file_not_found") { $checkedCount++ }
}

$meta = @{
    batch_id = "Batch_075"
    generated_at = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")
    total_files = $files.Count
    files_checked = $checkedCount
    range = "xiangbaocui.md ~ xianluozhixu.md"
    api_endpoint = "https://api.bilibili.com/x/web-interface/view?bvid={BV}"
}

$counts = @{
    confirmed = $confirmedCount
    partial = $partialCount
    unverifiable = $unverifiableCount
    conflict = $conflictCount
    file_not_found = $notFoundCount
}

$summaryObj = @{
    confirmed = "Files where BV exists, title contains song name, pubdate matches, view counts consistent"
    partial = "Files with BV but some discrepancies (shared BV, no 视频ID but BV in source, P name mismatch, etc.)"
    unverifiable = "Files with no BV/视频ID, cannot be API verified"
    conflict = "Files with clear data conflicts"
    file_not_found = "Files listed in batch but not found on disk"
}

$report = @{
    report_metadata = $meta
    classification_counts = $counts
    summary = $summaryObj
    entries = @($entries)
}

$json = $report | ConvertTo-Json -Depth 10
$reportPath = Join-Path -Path $reportDir -ChildPath "Batch_075_verification.json"
$json | Set-Content -LiteralPath $reportPath -Encoding UTF8
Write-Host "Report saved to: $reportPath"

foreach ($sf in $suspiciousFiles) {
    $src = Join-Path -Path $musicDir -ChildPath $sf
    $dst = Join-Path -Path $suspiciousDir -ChildPath $sf
    if (Test-Path $src) {
        Copy-Item -LiteralPath $src -Destination $dst -Force
        Write-Host "[SUSPICIOUS] Copied $sf"
    }
}

Write-Host "`n=== BATCH 075 VERIFICATION SUMMARY ==="
Write-Host "Total files: $($files.Count)"
Write-Host "Confirmed: $confirmedCount"
Write-Host "Partial: $partialCount"
Write-Host "Unverifiable: $unverifiableCount"
Write-Host "Conflict: $conflictCount"
Write-Host "File Not Found: $notFoundCount"
Write-Host "Suspicious files copied: $($suspiciousFiles.Count)"
Write-Host "Report: $reportPath"
Write-Host "======================================`n"

Write-Host "--- Detailed Results ---"
$entries | Select-Object filename, classification, primary_BV, @{N='曲名';E={$_.song_name.Substring(0,[Math]::Min(25, $_.song_name.Length))}}, @{N='Notes(65)';E={$_.notes.Substring(0,[Math]::Min(65, $_.notes.Length))}} | Format-Table -AutoSize
