$sourceCounts = @{}
$files = Get-ChildItem "music" -Filter "*.md"
foreach ($f in $files) {
  $content = Get-Content $f.FullName -Raw
  $sections = [regex]::Matches($content, "### 来源")
  if ($sections.Count -eq 0) {
    $key = "0 sources section"
  } else {
    $sectionText = $content.Substring($sections[0].Index)
    $items = [regex]::Matches($sectionText, "\[.*?\]\(https?://[^)]+\)")
    $count = $items.Count
    if ($count -eq 1) { $key = "1 source" }
    elseif ($count -eq 2) { $key = "2 sources" }
    elseif ($count -eq 3) { $key = "3 sources" }
    elseif ($count -eq 4) { $key = "4 sources" }
    elseif ($count -ge 5 -and $count -le 7) { $key = "5-7 sources" }
    else { $key = "8+ sources" }
  }
  if (-not $sourceCounts.ContainsKey($key)) { $sourceCounts[$key] = 0 }
  $sourceCounts[$key]++
}
$sourceCounts.Keys | Sort-Object | ForEach-Object { $k = $_; $v = $sourceCounts[$k]; Write-Output "${k}: ${v}" }
