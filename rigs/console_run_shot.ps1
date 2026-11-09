# Generic rig: run command in visible cmd window, screenshot, kill (v2 parameterized, ASCII-only, no battle data)
# Usage: .\console_run_shot.ps1 -Title 'demo script run' -CmdLine 'node demo.js dec DEMO_CIPHERTEXT' -WorkDir 'C:\demo' -Out 'shot.png' [-WaitSec 7]
# CmdLine is appended after 'cmd /k title ... &' - keep it a single line, pre-escaped.
param(
  [Parameter(Mandatory=$true)][string]$Title,
  [Parameter(Mandatory=$true)][string]$CmdLine,
  [string]$WorkDir = $PWD.Path,
  [Parameter(Mandatory=$true)][string]$Out,
  [int]$WaitSec = 7
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

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = 'cmd.exe'
$psi.WorkingDirectory = $WorkDir
$psi.Arguments = "/k title $Title & $CmdLine"
$psi.WindowStyle = 'Normal'
$p = [System.Diagnostics.Process]::Start($psi)
Start-Sleep -Seconds $WaitSec
Shot $Out
Write-Output "shot taken: $Out"
Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
