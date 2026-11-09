# 报告截图 rig（攻防战役实战固化，已参数化重写——现场数据/硬编码路径全部出清）
- screen_capture.ps1   — 全屏截图（参数=输出png路径）
- excel_row_shot.ps1   — Excel COM 打开真实表格 Find 关键词跳行截图（参数=-Xlsx/-Keywords/-OutPngs；中文路径需先拷到 ASCII 路径）
- console_run_shot.ps1 — 可见 cmd 窗口跑命令并截图（参数=-Title/-CmdLine/-WorkDir/-Out；脚本运行证据）
- browser_cdp_shot.py  — CDP 驱动真实浏览器：打开 URL→可选等元素(--wait-js)→可选填值点按钮(--eval)→截图（HTML工具运行证据；需 websocket-client）
- ocr3.ps1             — Windows OCR 读图（环境读不了图时的降级链）

> rig 是参数化骨架：战役用的时候现场传参（URL/关键词/命令/输出路径），禁止把当轮的密文/域名/工号/本机路径写死回 rig——曾实锤：现场值被写死入库，固化前必参数化+敏感词扫描。
