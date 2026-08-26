param(
  [string]$Root = "E:\AAA_software\Deepseek\deepseek-harness\packages",
  [string]$Pattern,
  [string]$Extra = ""
)
function Get-SrcDirs($root) {
  $result = @(); $stack = New-Object System.Collections.Stack; $stack.Push($root)
  while ($stack.Count -gt 0) {
    $dir = $stack.Pop()
    try { $children = Get-ChildItem $dir -Directory -Force -ErrorAction Stop } catch { continue }
    foreach ($c in $children) {
      if ($c.Name -eq 'node_modules') { continue }
      if ($c.Name -eq 'src') { $result += $c.FullName }
      $stack.Push($c.FullName)
    }
  }
  return $result
}
$dirs = Get-SrcDirs $Root
$files = @()
foreach ($d in $dirs) { $files += Get-ChildItem $d -Recurse -File -Include *.ts,*.tsx | Where-Object { $_.FullName -notmatch 'node_modules' } }
if ($Extra) { $files = $files | Where-Object { $_.FullName -match $Extra } }
$files | Select-String -Pattern $Pattern | ForEach-Object { "$($_.Path.Replace('E:\AAA_software\Deepseek\deepseek-harness\','')) L$($_.LineNumber): $($_.Line.Trim())" }
