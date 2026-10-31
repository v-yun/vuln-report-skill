$ErrorActionPreference = 'Stop'
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $true
$xl.DisplayAlerts = $false
try {
  $wb = $xl.Workbooks.Open('E:\asset_tmp.xlsx', 0, $true)
  $ws = $wb.Worksheets.Item(1)
  $xl.WindowState = -4137
  Start-Sleep -Milliseconds 2000
  $found = $ws.Cells.Find('asset.example.com')
  if ($found) {
    $row = $found.Row
    $found.Activate()
    $xl.ActiveWindow.ScrollRow = [Math]::Max(1, $row - 2)
    $xl.ActiveWindow.ScrollColumn = 1
    Start-Sleep -Milliseconds 2500
    & powershell -ExecutionPolicy Bypass -File <workdir>\yakit_ui\shot.ps1 <workdir>\poc_raw\shot_asset_excel1.png
    Write-Output "shot1 row $row"
    $found2 = $ws.Cells.Find('asset.example.com/sxexb/renewal/toIndex.html')
    if ($found2) {
      $found2.Activate()
      $xl.ActiveWindow.ScrollRow = [Math]::Max(1, $found2.Row - 2)
      $xl.ActiveWindow.ScrollColumn = 1
      Start-Sleep -Milliseconds 2000
      & powershell -ExecutionPolicy Bypass -File <workdir>\yakit_ui\shot.ps1 <workdir>\poc_raw\shot_asset_excel2.png
      Write-Output "shot2 row $($found2.Row)"
    }
  } else { Write-Output 'NOT FOUND' }
  $wb.Close($false)
} finally {
  $xl.Quit()
  [Runtime.InteropServices.Marshal]::ReleaseComObject($xl) | Out-Null
}
