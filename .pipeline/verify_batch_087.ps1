# Batch_087 Music Fact Verification Script
# Goal: Verify 50 music markdown files against Bilibili API

$musicDir = "D:\数据收集\luotianyi-db\processed\rag\music"
$reportDir = "D:\数据收集\luotianyi-db\processed\rag\.pipeline\verification_reports"
$suspiciousDir = "D:\数据收集\luotianyi-db\processed\rag\suspicious_music\Batch_087"
$today = "2026-06-07"

$files = @(
    "yiwanwan-luotianyiofficial.md",
    "yiweixiaozhiming.md",
    "yixiagu.md",
    "yixiangqu.md",
    "yixiashigongfangfayanshijian.md",
    "yixinyiyi.md",
    "yixuezhongwenban.md",
    "yiyang.md",
    "yiyanweidingluotianyifeatyanhe.md",
    "yiyejianghu.md",
    "yiyi.md",
    "yiyudisike.md",
    "yiyuehefanjiao.md",
    "yiyuhongchen.md",
    "yiyuzheng.md",
    "yiyuzheng-zhongzhiban.md",
    "yizhe.md",
    "yizhenfengdeyangzi.md",
    "yizhenfengdeyangzi-2.md",
    "yizheng.md",
    "yizhever.md",
    "yizhihua.md",
    "yizhimaodedubaivcbenjia.md",
    "yizhizaiyiqi.md",
    "yizhonglian.md",
    "yizhongrenluotianyi.md",
    "ymca-luotianyi-ver.md",
    "yongbaomingtian.md",
    "yonggandexin-luotianyi-ver.md",
    "yonghenglian.md",
    "yonghengzhishangfengyi-anxiaosynthesizer-v-covernoaiy.md",
    "yongmix.md",
    "yongshengzhiyue.md",
    "yongwover.md",
    "yongwudaodegushi-luotianyiai.md",
    "yongxinxieshoukuqingge.md",
    "yongxinxieshoukuqinggeluotianyibanben.md",
    "yongzhezhige.md",
    "you.md",
    "you-2.md",
    "youbuyaowenroudiduidaiwo.md",
    "youcan-qingqiyouxiremixqingqiyouxip-remix.md",
    "youchangliuyanghechuyin.md",
    "youchun.md",
    "youchunmeng.md",
    "youdianzaogao.md",
    "youfengchun.md",
    "yougexingderenluotianyiban.md",
    "youhebuke.md",
    "youhebukeheshengbanzou.md"
)

function Parse-Metadata {
    param([string]$content)
    $meta = @{}

    # Extract BVID (视频ID)
    if ($content -match '\|\s*视频ID\s*\|\s*([^\|]+)\s*\|') {
        $bvid = $matches[1].Trim()
        if ($bvid -ne '') { $meta.bvid = $bvid }
    }

    # Extract title (曲名)
    if ($content -match '\|\s*曲名\s*\|\s*([^\|]+)\s*\|') {
        $meta.title = $matches[1].Trim()
    }

    # Extract title from heading
    if ($content -match '^##\s+(.+)$') {
        $meta.heading_title = $matches[1].Trim()
    }

    # Extract P主
    if ($content -match '\|\s*P主\s*\|\s*([^\|]+)\s*\|') {
        $meta.creator = $matches[1].Trim()
    }

    # Extract 发行日期
    if ($content -match '\|\s*发行日期\s*\|\s*([^\|]+)\s*\|') {
        $dateVal = $matches[1].Trim()
        if ($dateVal -ne '') { $meta.publish_date = $dateVal }
    }

    # Extract 播放量
    if ($content -match '\|\s*播放量\s*\|\s*([^\|]+)\s*\|') {
        $viewVal = $matches[1].Trim()
        if ($viewVal -ne '') { $meta.play_count = $viewVal }
    }

    # Extract 演唱
    if ($content -match '\|\s*演唱\s*\|\s*([^\|]+)\s*\|') {
        $meta.singer = $matches[1].Trim()
    }

    # Extract 引擎
    if ($content -match '\|\s*引擎\s*\|\s*([^\|]+)\s*\|') {
        $meta.engine = $matches[1].Trim()
    }

    return $meta
}

function Convert-UnixTimeToDate {
    param([long]$unixTime)
    $epoch = Get-Date "1970-01-01 00:00:00"
    return $epoch.AddSeconds($unixTime).ToString("yyyy-MM-dd")
}

function Parse-ViewCount {
    param([string]$viewStr)
    # Remove commas and spaces
    $cleanStr = $viewStr -replace '[,\s]', ''
    # Handle formats like "约86.8万", "86.8万", "1234567", etc.
    if ($cleanStr -match '约?([\d.]+)\s*万') {
        return [long]([double]$matches[1] * 10000)
    }
    if ($cleanStr -match '约?([\d.]+)\s*亿') {
        return [long]([double]$matches[1] * 100000000)
    }
    if ($cleanStr -match '([\d]+)') {
        return [long]$matches[1]
    }
    return 0
}

function Test-StringSimilar {
    param([string]$a, [string]$b)
    # Simple fuzzy matching: check if one contains the other after normalization
    $an = $a -replace '[\[\]【】《》\(\)（）「」\s#]', '' -replace '[a-zA-Z]', ''
    $bn = $b -replace '[\[\]【】《》\(\)（）「」\s#]', '' -replace '[a-zA-Z]', ''
    if ($an.Length -eq 0 -or $bn.Length -eq 0) { return $false }
    return $an.Contains($bn) -or $bn.Contains($an) -or $an -eq $bn
}

function Normalize-CreatorName {
    param([string]$name)
    # Remove creator: prefix
    $n = $name -replace '^creator:', ''
    # Remove parenthetical aliases like "(可乐君)" or "（可乐君）"
    $n = $n -replace '[\(（][^\)）]*[\)）]', ''
    # Remove spaces
    $n = $n -replace '\s+', ''
    return $n.ToLower()
}

function Test-ViewCountSimilar {
    param([string]$fileView, [long]$apiView)
    $parsedView = Parse-ViewCount -viewStr $fileView
    if ($parsedView -eq 0) { return $null } # unknown
    $ratio = [Math]::Abs($parsedView - $apiView) / [Math]::Max($parsedView, 1)
    return $ratio -lt 0.3  # Allow 30% tolerance
}

function Test-DateSimilar {
    param([string]$fileDate, [string]$apiDate)
    if ([string]::IsNullOrEmpty($fileDate)) { return $null }
    return $fileDate -eq $apiDate
}

function Get-BilibiliInfo {
    param([string]$bvid)
    $url = "https://api.bilibili.com/x/web-interface/view?bvid=$bvid"
    try {
        $resp = Invoke-RestMethod -Uri $url -Method Get -UserAgent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" -TimeoutSec 15
        if ($resp.code -eq 0) {
            $d = $resp.data
            return @{
                bvid = $d.bvid
                title = $d.title
                owner = $d.owner.name
                pubdate = Convert-UnixTimeToDate -unixTime $d.pubdate
                view = $d.stat.view
                like = $d.stat.like
                danmaku = $d.stat.danmaku
                duration = $d.duration
                ts = $d.pubdate
            }
        }
        return $null
    } catch {
        return $null
    }
}

# Main processing
$results = @()
$suspiciousFiles = @()

foreach ($file in $files) {
    Write-Host "Processing: $file"
    $filePath = Join-Path $musicDir $file
    $result = @{
        file = $file
        classification = ""
        api_data = $null
        file_metadata = $null
        issues = @()
        bvid = ""
    }

    # Check if file exists
    if (-not (Test-Path $filePath)) {
        $result.classification = "file_not_found"
        $results += $result
        continue
    }

    # Read and parse file
    $content = Get-Content $filePath -Encoding UTF8 -Raw
    $meta = Parse-Metadata -content $content
    $result.file_metadata = $meta

    # Extract BVID
    $bvid = ""
    if ($meta.ContainsKey('bvid')) {
        $bvid = $meta.bvid
        $result.bvid = $bvid
    }

    if ([string]::IsNullOrEmpty($bvid)) {
        # No BVID -> unverifiable
        $result.classification = "unverifiable"
        $result.issues += "No BVID found in file"
        $results += $result
        continue
    }

    # Call bilibili API
    $apiData = Get-BilibiliInfo -bvid $bvid
    if ($null -eq $apiData) {
        $result.classification = "unverifiable"
        $result.issues += "Bilibili API returned no data for BVID: $bvid"
        $results += $result
        continue
    }
    $result.api_data = $apiData

    # Compare fields
    $issues = @()
    $matchCount = 0
    $checks = 0

    # 1. Title comparison
    $fileTitle = if ($meta.ContainsKey('title')) { $meta.title } else { "" }
    $apiTitle = $apiData.title
    if (-not [string]::IsNullOrEmpty($fileTitle)) {
        $checks++
        $titleClean = $fileTitle -replace ' - .*$', '' # remove suffix like " - 洛天依Official"
        # Fuzzy title match: check if core title is contained in API title or vice versa
        $titleCore = $titleClean -replace '[（(].*[）)]', ''
        $t1 = ($apiTitle -match [Regex]::Escape($titleClean))
        $t2 = ($apiTitle -match [Regex]::Escape($titleCore))
        $t3 = Test-StringSimilar -a $fileTitle -b $apiTitle
        $titleMatch = $t1 -or $t2 -or $t3
        if ($titleMatch) {
            $matchCount++
        } else {
            $issues += "Title mismatch: file='$fileTitle' vs api='$apiTitle'"
        }
    }

    # 2. Creator/P主 comparison
    $fileCreator = if ($meta.ContainsKey('creator')) { $meta.creator } else { "" }
    $apiOwner = $apiData.owner
    if (-not [string]::IsNullOrEmpty($fileCreator)) {
        $checks++
        $fcNorm = Normalize-CreatorName -name $fileCreator
        $aoNorm = $apiOwner.ToLower() -replace '\s+', ''
        $creatorMatch = $fcNorm.Contains($aoNorm) -or $aoNorm.Contains($fcNorm) -or $fcNorm -eq $aoNorm
        if ($creatorMatch) {
            $matchCount++
        } else {
            $fcDisplay = $fileCreator -replace '^creator:', ''
            $issues += "Creator mismatch: file='$fcDisplay' vs api='$apiOwner'"
        }
    }

    # 3. Publish date comparison
    if ($meta.ContainsKey('publish_date') -and -not [string]::IsNullOrEmpty($meta.publish_date)) {
        $checks++
        $dateMatch = Test-DateSimilar -fileDate $meta.publish_date -apiDate $apiData.pubdate
        if ($dateMatch -eq $true) {
            $matchCount++
        } elseif ($dateMatch -eq $false) {
            $issues += "Date mismatch: file='$($meta.publish_date)' vs api='$($apiData.pubdate)'"
        }
    }

    # 4. View count comparison
    if ($meta.ContainsKey('play_count') -and -not [string]::IsNullOrEmpty($meta.play_count)) {
        $checks++
        $viewOk = Test-ViewCountSimilar -fileView $meta.play_count -apiView $apiData.view
        if ($viewOk -eq $true) {
            $matchCount++
        } elseif ($viewOk -eq $false) {
            $fileViewsParsed = Parse-ViewCount -viewStr $meta.play_count
            $issues += "View count mismatch: file='$($meta.play_count)' (parsed=$fileViewsParsed) vs api=$($apiData.view)"
        }
    }

    # Classification
    if ($checks -eq 0) {
        $result.classification = "unverifiable"
        $result.issues += "No comparable fields (title, creator, date, views all empty)"
    } elseif ($matchCount -eq $checks) {
        $result.classification = "confirmed"
    } elseif ($matchCount -gt 0) {
        $result.classification = "partial"
        $result.issues = $issues
    } else {
        $result.classification = "conflict"
        $result.issues = $issues
    }

    $results += $result

    # If suspicious (partial or conflict with BVID), add to suspicious list
    if ($result.classification -in @("partial", "conflict") -and -not [string]::IsNullOrEmpty($bvid)) {
        $suspiciousFiles += $file
    }

    # Rate limiting - be respectful to bilibili API
    Start-Sleep -Milliseconds 300
}

# Generate report
# Recalculate summary from details array to avoid PowerShell counting quirks with hashtable arrays
$summaryConfirmed = 0; $summaryPartial = 0; $summaryUnverifiable = 0; $summaryConflict = 0; $summaryNotFound = 0
foreach ($r in $results) {
    switch ($r.classification) {
        "confirmed" { $summaryConfirmed++ }
        "partial" { $summaryPartial++ }
        "unverifiable" { $summaryUnverifiable++ }
        "conflict" { $summaryConflict++ }
        "file_not_found" { $summaryNotFound++ }
    }
}

$report = @{
    batch_id = "Batch_087"
    verified_date = $today
    total_files = $files.Count
    summary = @{
        confirmed = $summaryConfirmed
        partial = $summaryPartial
        unverifiable = $summaryUnverifiable
        conflict = $summaryConflict
        file_not_found = $summaryNotFound
    }
    details = $results
    suspicious_files = @($suspiciousFiles)
}

$reportJson = $report | ConvertTo-Json -Depth 10
$reportPath = Join-Path $reportDir "Batch_087_verification_report.json"
$reportJson | Out-File $reportPath -Encoding UTF8
Write-Host "Report saved to: $reportPath"

# Copy suspicious files
Write-Host "`nCopying $($suspiciousFiles.Count) suspicious files to archive..."
foreach ($sf in $suspiciousFiles) {
    $src = Join-Path $musicDir $sf
    $dst = Join-Path $suspiciousDir $sf
    if (Test-Path $src) {
        Copy-Item $src $dst -Force
        Write-Host "  Copied: $sf"
    }
}

# Print summary
Write-Host "`n=========================================="
Write-Host "  Batch_087 Verification Complete"
Write-Host "=========================================="
Write-Host "  Total:      $($report.total_files)"
Write-Host "  Confirmed:  $($report.summary.confirmed)"
Write-Host "  Partial:    $($report.summary.partial)"
Write-Host "  Unverifiable: $($report.summary.unverifiable)"
Write-Host "  Conflict:   $($report.summary.conflict)"
Write-Host "  Not Found:  $($report.summary.file_not_found)"
Write-Host "  Suspicious: $($suspiciousFiles.Count)"
Write-Host "=========================================="

return $report
