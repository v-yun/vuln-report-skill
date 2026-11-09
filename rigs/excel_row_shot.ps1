# Generic rig: Excel COM open xlsx, Find keyword rows, scroll & screenshot each (v2 parameterized, ASCII-only, no battle data)
# Usage: .\excel_row_shot.ps1 -Xlsx 'E:\asset_tmp.xlsx' -Keywords 'demo.example.com','api.example.com' -OutPngs 'shot1.png','shot2.png'
# CN-path pitfall: PowerShell 5.1 GBK console cannot open CN paths via COM - copy xlsx to an ASCII path first (e.g. E:\asset_tmp.xlsx).
param(
  [Parameter(Mandatory=$true)][string]$Xlsx,
  [Parameter(Mandatory=$true)][string[]]$Keywords,
  [Parameter(Mandatory=$true)][string[]]$OutPngs,
  [int]$ScrollBack = 2
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Shot([string]$path) {
  $b = New-Object System.Drawing.Bitmap([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height)
  $g = [System.Drawing.Graphics]::FromImage($b)
  $g.CopyFromScreen(0, 0, 0, 0, $b.Size)
  $b.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose(); $b.Dispose()
}

$xl = New-Object -ComObject Excel.Application
$xl.Visible = $true
$xl.DisplayAlerts = $false
try {
  $wb = $xl.Workbooks.Open($Xlsx, 0, $true)
  $ws = $wb.Worksheets.Item(1)
  $xl.WindowState = -4137
  Start-Sleep -Milliseconds 2000
  for ($i = 0; $i -lt $Keywords.Count; $i++) {
    $found = $ws.Cells.Find($Keywords[$i])
    if ($found) {
      $found.Activate()
      $xl.ActiveWindow.ScrollRow = [Math]::Max(1, $found.Row - $ScrollBack)
      $xl.ActiveWindow.ScrollColumn = 1
      Start-Sleep -Milliseconds 2500
      Shot $OutPngs[$i]
      Write-Output ("shot {0} row {1}" -f $OutPngs[$i], $found.Row)
    } else { Write-Output ("NOT FOUND: " + $Keywords[$i]) }
  }
  $wb.Close($false)
} finally {
  $xl.Quit()
  [Runtime.InteropServices.Marshal]::ReleaseComObject($xl) | Out-Null
}
