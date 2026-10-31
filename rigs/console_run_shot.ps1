$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = 'cmd.exe'
$psi.Arguments = '/k title sxexb_crypto.js 解密脚本运行 & mode con cols=170 lines=45 & cd /d C:\Users\13222\Desktop\yakit_poc\解密脚本 & echo ============ 太保E锦囊解密脚本 sxexb_crypto.js 实跑 ============ & echo. & echo [1] 解密 PoC 报文里的 requestBodyJson： & node sxexb_crypto.js dec S5rNm5vUWm/F4FxqHplvfhMG5ubWR96mN/9NKeOp8HztARi5nc7ijTY2tb0OU+GOvzy6km/LQAj3D7vI2F8++2KeKbfZshdKtgT///clMzidxIMggXWrXZRyBP5G3ZXTb9+bazZ8lwyy9BzrKPiq6ixFeaQJGtlgHXek6K8Sh28uq6bQ24fZ0nga0ZTzdQNK & echo. & echo [2] 解密响应里的 ecardno： & node sxexb_crypto.js dec vF+gZwFNfYoQ59HqM7pEz+vowLvOjWmeyiVqacyQ2CHkyS7XwWhg/+95mr58SNAW & echo. & echo [3] 构造 P0010023 请求体： & node sxexb_crypto.js build P0010023 YATC0171 gxmsb_72'
$psi.WindowStyle = 'Normal'
$p = [System.Diagnostics.Process]::Start($psi)
Start-Sleep -Seconds 7
& powershell -ExecutionPolicy Bypass -File <workdir>\yakit_ui\shot.ps1 <workdir>\poc_raw\shot_decrypt2.png
Write-Output "shot taken"
Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
