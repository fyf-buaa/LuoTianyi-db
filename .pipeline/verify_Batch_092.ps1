# Batch_092 Verification Script
# Calls bilibili API for each file's BVID and verifies metadata

$musicDir = "D:\数据收集\luotianyi-db\processed\rag\music"
$reportDir = "D:\数据收集\luotianyi-db\processed\rag\.pipeline\verification_reports"
$suspiciousDir = "D:\数据收集\luotianyi-db\processed\rag\suspicious_music\Batch_092"
$today = "2026-06-08"

# Ensure directories exist
if (!(Test-Path $reportDir)) { New-Item -ItemType Directory -Path $reportDir -Force }
if (!(Test-Path $suspiciousDir)) { New-Item -ItemType Directory -Path $suspiciousDir -Force }

# Batch_092 file list
$files = @(
    "zhainanriji.md","zhaixuejiadeziwoxiuyang.md","zhaiyueguang.md","zhaizhaibuleshui.md",
    "zhanchangzhiwai.md","zhanfang.md","zhanfangbaisedehua.md","zhangfengshaonianluotianyivvyanhevv.md",
    "zhangganxing.md","zhanggeaitaopaodetianshiace-studiocovernoaiy.md","zhangmengbuxing.md",
    "zhangxiangsiqu.md","zhangxiaobei-wocongrenjianzouguovocaloid-cover.md","zhangxindemozhou.md",
    "zhangxingshi.md","zhangxinqiuci.md","zhangxinzhongdemingyun.md","zhangyi.md","zhangyuxiaowanzi.md",
    "zhangzhongleyuan-2.md","zhangzhongleyuan-3.md","zhangzhou.md","zhantai.md","zhanyi.md",
    "zhaodaota.md","zhaomi.md","zhaoshixun-fugedemo.md","zhaoshixun-luotianyi-ver.md",
    "zhaoyangzhaoyang.md","zhaozeyiciriluo.md","zhazuofanzi-tongkeke.md","zhazuolv.md",
    "zheciwodasuanyuanliangshijie.md","zhejiushizhongguofeat-luotianyi-yanhe-lezhenglongya.md",
    "zhekexiaoyoumeimiaodeshijieweiwocunzai.md","zhemekeaizhenshibaoqian.md",
    "zhemingziyitingjiuhenguai.md","zhengtushixingchendahai.md",
    "zhengyumoke-luotianyiluoyanghuaiatonyp.md","zhengyumoke-luotianyizhaolurenjianvocaloid-cover.md",
    "zhengzhuansongdeweilai.md","zhengzongjundefuchouwei.md",
    "zhenjiliuhuashiananyinyou-are-a-ghost-i-am-a-ghostmix.md","zhenkongfuyou.md",
    "zhenkongyangqiguan.md","zhentou.md","zhenxiafei.md","zhenxiang.md","zhenyu.md","zhenzhu.md"
)

function ConvertFrom-UnixTimestamp {
    param([long]$Timestamp)
    $epoch = Get-Date -Date "1970-01-01" -Format "yyyy-MM-dd"
    $dt = (Get-Date "1970-01-01").AddSeconds($Timestamp)
    return $dt.ToString("yyyy-MM-dd")
}

function Get-BilibiliVideoInfo {
    param([string]$BVID)
    $url = "https://api.bilibili.com/x/web-interface/view?bvid=$BVID"
    try {
        $response = Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 15 -ErrorAction Stop
        if ($response.code -eq 0 -and $response.data) {
            $data = $response.data
            $pubDate = ConvertFrom-UnixTimestamp -Timestamp $data.pubdate
            $viewCount = $data.stat.view
            $title = $data.title
            $uploader = $data.owner.name
            $duration = $data.duration
            return @{
                BVID = $data.bvid
                Title = $title
                Uploader = $uploader
                PubDate = $pubDate
                ViewCount = $viewCount
                Duration = $duration
                Success = $true
            }
        } else {
            return @{
                BVID = $BVID
                Success = $false
                Error = "API returned code $($response.code): $($response.message)"
            }
        }
    } catch {
        return @{
            BVID = $BVID
            Success = $false
            Error = $_.Exception.Message
        }
    }
}

# Main verification
$results = @()
$totalWithBVID = 0
$totalNoBVID = 0
$fileNotFoundCount = 0

foreach ($file in $files) {
    $path = Join-Path $musicDir $file
    $fileResult = @{
        file = $file
        slug = ""
        title = ""
        api_result = $null
        fields = @{}
        file_found = $false
        has_bvid = $false
        verdict = ""
        suspicious = $false
        issues = @()
    }

    if (!(Test-Path $path)) {
        $fileResult.file_found = $false
        $fileResult.verdict = "file_not_found"
        $fileNotFoundCount++
        $results += $fileResult
        continue
    }

    $fileResult.file_found = $true
    $content = Get-Content $path -Raw

    # Extract slug
    if ($content -match '# music:(.+)') { $fileResult.slug = "music:$($matches[1])" }
    
    # Extract title (second line ##)
    if ($content -match '^## (.+)') { $fileResult.title = $matches[1].Trim() }
    
    # Extract BVID - look for BV pattern
    $bvid = ""
    if ($content -match 'BV[0-9A-Za-z]{10}') { $bvid = $matches[0] }
    
    # Extract other fields
    $fields = @{}
    # Title from table
    if ($content -match '\| 曲名 \| (.+)') { $fields.title_local = $matches[1] }
    if ($content -match '\| P主 \| (.+)') { $fields.pzhu = $matches[1] }
    if ($content -match '\| 演唱 \| (.+)') { $fields.singer = $matches[1] }
    if ($content -match '\| 播放量 \| ([0-9,]+)') { $fields.playcount = $matches[1] }
    if ($content -match '\| 发行日期 \| ([0-9\-]+)') { $fields.release_date = $matches[1] }
    if ($content -match '\| 引擎 \| (.+)') { $fields.engine = $matches[1] }
    if ($content -match '\| 风格 \| (.+)') { $fields.style = $matches[1] }
    if ($content -match '\| 标签 \| (.+)') { $fields.tags = $matches[1] }
    if ($content -match '\| 首发平台 \| (.+)') { $fields.platform = $matches[1] }
    $fileResult.fields = $fields

    if ([string]::IsNullOrEmpty($bvid)) {
        $totalNoBVID++
        # No BVID - check if there's any verifiable data
        $hasData = $false
        foreach ($key in $fields.Keys) {
            if (![string]::IsNullOrEmpty($fields[$key])) { $hasData = $true; break }
        }
        if ($hasData) {
            $fileResult.verdict = "unverifiable"
            $fileResult.issues += "No BVID found; unverifiable via API"
        } else {
            $fileResult.verdict = "unverifiable"
            $fileResult.issues += "No BVID and minimal metadata"
        }
    } else {
        $totalWithBVID++
        $fileResult.has_bvid = $true
        # Call bilibili API
        Write-Host "Calling API for $file ($bvid)..."
        $apiInfo = Get-BilibiliVideoInfo -BVID $bvid
        
        if ($apiInfo.Success) {
            $fileResult.api_result = $apiInfo
            # Compare fields
            $diffCount = 0
            $fieldResults = @{}
            
            # Compare title
            $apiTitle = $apiInfo.Title
            $localTitle = if ($fields.title_local) { $fields.title_local } else { $fileResult.title }
            
            # Check for discrepancies
            $issues = @()
            
            # Compare view count (parse local, compare to API)
            if ($fields.playcount) {
                $localView = [int]($fields.playcount -replace ',', '')
                $apiView = $apiInfo.ViewCount
                $diff = [math]::Abs($localView - $apiView)
                if ($diff -gt 100 -and ($diff / [math]::Max($localView, 1)) -gt 0.1) {
                    $issues += "View count mismatch: local=$localView, api=$apiView"
                    $diffCount++
                }
            }
            
            # Compare release date
            if ($fields.release_date -and $apiInfo.PubDate) {
                if ($fields.release_date -ne $apiInfo.PubDate) {
                    $issues += "Date mismatch: local=$($fields.release_date), api=$($apiInfo.PubDate)"
                    $diffCount++
                }
            }
            
            # Compare uploader with P主
            if ($fields.pzhu) {
                $pzhuClean = $fields.pzhu -replace 'creator:', ''
                $apiUploader = $apiInfo.Uploader
                if ($pzhuClean -ne $apiUploader -and $pzhuClean -notmatch $apiUploader -and $apiUploader -notmatch $pzhuClean) {
                    $issues += "Uploader mismatch: local='$pzhuClean', api='$apiUploader'"
                    $diffCount++
                }
            }
            
            if ($diffCount -eq 0) {
                $fileResult.verdict = "confirmed"
                $fileResult.suspicious = $false
            } elseif ($diffCount -le 1) {
                $fileResult.verdict = "partial"
                $fileResult.suspicious = $true
            } else {
                $fileResult.verdict = "conflict"
                $fileResult.suspicious = $true
            }
            $fileResult.issues = $issues
        } else {
            # API failed - but we have BVID
            $fileResult.verdict = "unverifiable"
            $fileResult.issues += "API call failed: $($apiInfo.Error)"
            $fileResult.api_result = $apiInfo
        }
    }
    
    $results += $fileResult
}

# Build report
$confirmedCount = ($results | Where-Object { $_.verdict -eq "confirmed" }).Count
$partialCount = ($results | Where-Object { $_.verdict -eq "partial" }).Count
$conflictCount = ($results | Where-Object { $_.verdict -eq "conflict" }).Count
$unverifiableCount = ($results | Where-Object { $_.verdict -eq "unverifiable" }).Count
$fileNotFoundCount = ($results | Where-Object { $_.verdict -eq "file_not_found" }).Count
$suspiciousCount = ($results | Where-Object { $_.suspicious }).Count

# Copy suspicious files
$suspiciousFiles = $results | Where-Object { $_.suspicious }
foreach ($s in $suspiciousFiles) {
    $src = Join-Path $musicDir $s.file
    $dst = Join-Path $suspiciousDir $s.file
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination $dst -Force
        Write-Host "Copied suspicious: $($s.file)"
    }
}

# Generate JSON report
$report = @{
    report_metadata = @{
        title = "Batch_092 事实核查报告"
        batch = "Batch_092"
        generated = $today
        methodology = "对每个文件提取曲名、P主、发行日期、视频ID/BV ID、播放量等字段，通过bilibili API (https://api.bilibili.com/x/web-interface/view?bvid={BV}) 进行交叉验证"
        total_files = $files.Count
        summary = @{
            confirmed = $confirmedCount
            partial = $partialCount
            conflict = $conflictCount
            unverifiable = $unverifiableCount
            file_not_found = $fileNotFoundCount
            suspicious = $suspiciousCount
        }
    }
    results = @($results | ForEach-Object {
        $r = $_
        $facts = @()
        
        # Add title fact
        $facts += @{
            field = "曲名"
            original = if ($r.fields.title_local) { $r.fields.title_local } else { $r.title }
            verified = if ($r.api_result -and $r.api_result.Success) { $r.api_result.Title } else { "N/A" }
            sources = if ($r.api_result -and $r.api_result.Success) { @(@{label="bilibili API"; url="https://api.bilibili.com/x/web-interface/view?bvid=$($r.api_result.BVID)"; match=($r.verdict -ne "conflict" -and $r.verdict -ne "unverifiable")}) } else { @() }
            verdict = if ($r.verdict -eq "file_not_found") { "file_not_found" } elseif ($r.verdict -eq "unverifiable" -or !$r.api_result) { "unverifiable" } else { "confirmed" }
            confidence = if ($r.api_result -and $r.api_result.Success) { "HIGH" } else { "NONE" }
        }
        
        # Add uploader fact
        $facts += @{
            field = "UP主/P主"
            original = $r.fields.pzhu
            verified = if ($r.api_result -and $r.api_result.Success) { $r.api_result.Uploader } else { "N/A" }
            sources = if ($r.api_result -and $r.api_result.Success) { @(@{label="bilibili API"; url="https://api.bilibili.com/x/web-interface/view?bvid=$($r.api_result.BVID)"; match=($r.verdict -ne "conflict" -and $r.verdict -ne "unverifiable")}) } else { @() }
            verdict = if ($r.verdict -eq "file_not_found") { "file_not_found" } elseif ($r.verdict -eq "unverifiable" -or !$r.api_result) { "unverifiable" } else { "confirmed" }
            confidence = if ($r.api_result -and $r.api_result.Success) { "MEDIUM" } else { "NONE" }
        }
        
        # Add BVID/视频ID fact
        $facts += @{
            field = "视频ID"
            original = if ($r.has_bvid) { ($r.api_result.BVID) } else { "" }
            verified = if ($r.api_result -and $r.api_result.Success) { $r.api_result.BVID } else { "N/A" }
            sources = if ($r.api_result -and $r.api_result.Success) { @(@{label="bilibili API"; url="https://api.bilibili.com/x/web-interface/view?bvid=$($r.api_result.BVID)"; match=$true}) } else { @() }
            verdict = if ($r.verdict -eq "file_not_found") { "file_not_found" } elseif ($r.has_bvid) { "confirmed" } else { "unverifiable" }
            confidence = if ($r.api_result -and $r.api_result.Success) { "HIGH" } else { "NONE" }
        }
        
        # Add date fact
        $facts += @{
            field = "发行日期"
            original = $r.fields.release_date
            verified = if ($r.api_result -and $r.api_result.Success) { $r.api_result.PubDate } else { "N/A" }
            sources = if ($r.api_result -and $r.api_result.Success) { @(@{label="bilibili API"; url="https://api.bilibili.com/x/web-interface/view?bvid=$($r.api_result.BVID)"; match=($r.verdict -ne "conflict" -and $r.verdict -ne "unverifiable")}) } else { @() }
            verdict = if ($r.verdict -eq "file_not_found") { "file_not_found" } elseif ($r.verdict -eq "unverifiable" -or !$r.api_result) { "unverifiable" } else { "confirmed" }
            confidence = if ($r.api_result -and $r.api_result.Success) { "HIGH" } else { "NONE" }
        }
        
        # Add view count fact
        $facts += @{
            field = "播放量"
            original = $r.fields.playcount
            verified = if ($r.api_result -and $r.api_result.Success) { "$($r.api_result.ViewCount)" } else { "N/A" }
            sources = if ($r.api_result -and $r.api_result.Success) { @(@{label="bilibili API"; url="https://api.bilibili.com/x/web-interface/view?bvid=$($r.api_result.BVID)"; match=($r.verdict -ne "conflict" -and $r.verdict -ne "unverifiable")}) } else { @() }
            verdict = if ($r.verdict -eq "file_not_found") { "file_not_found" } elseif ($r.verdict -eq "unverifiable" -or !$r.api_result) { "unverifiable" } else { "confirmed" }
            confidence = if ($r.api_result -and $r.api_result.Success) { "HIGH" } else { "NONE" }
        }
        
        return @{
            file = $r.file
            slug = $r.slug
            title = $r.title
            facts = $facts
            overall_verdict = $r.verdict
            suspicious = $r.suspicious
            issues = $r.issues
        }
    })
}

$reportPath = Join-Path $reportDir "Batch_092_verification.json"
$report | ConvertTo-Json -Depth 6 | Set-Content -Path $reportPath -Encoding UTF8

Write-Host "========================================"
Write-Host "Batch_092 Verification Complete"
Write-Host "========================================"
Write-Host "Total files: $($files.Count)"
Write-Host "Confirmed: $confirmedCount"
Write-Host "Partial: $partialCount"
Write-Host "Conflict: $conflictCount"
Write-Host "Unverifiable: $unverifiableCount"
Write-Host "File not found: $fileNotFoundCount"
Write-Host "Suspicious files copied: $suspiciousCount"
Write-Host "Report saved to: $reportPath"
Write-Host "========================================"
