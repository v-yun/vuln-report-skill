# -*- coding: utf-8 -*-
"""真实浏览器打开附件HTML解密工具,填入密文,点解密,截图"""
import subprocess, time, json, urllib.request, base64, pathlib, sys
import websocket

PROFILE = r'<workdir>\edge_profile'
URL = 'file:///C:/Users/13222/Desktop/yakit_poc/' + '%E8%A7%A3%E5%AF%86%E8%84%9A%E6%9C%AC/' + '%E5%A4%AA%E4%BF%9DE%E9%94%A6%E5%9B%8A%E8%A7%A3%E5%AF%86%E5%B7%A5%E5%85%B7.html'
PORT = 19223

proc = subprocess.Popen([
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    f'--remote-debugging-port={PORT}', f'--user-data-dir={PROFILE}',
    '--window-size=1280,900', '--no-first-run', '--no-default-browser-check', URL
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(6)

tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))
ws_url = next(t['webSocketDebuggerUrl'] for t in tabs if t['type'] == 'page')
ws = websocket.create_connection(ws_url, timeout=20)

def send(method, params=None, i=[0]):
    i[0] += 1
    ws.send(json.dumps({'id': i[0], 'method': method, 'params': params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get('id') == i[0]:
            return msg.get('result', {})

def evl(expr):
    return send('Runtime.evaluate', {'expression': expr, 'returnByValue': True})['result'].get('value')

# 等自检出结果
for _ in range(20):
    if evl("document.getElementById('selftest').textContent.includes('PASS')"): break
    time.sleep(0.5)

# 填 PoC 密文并解密
ct = 'S5rNm5vUWm/F4FxqHplvfhMG5ubWR96mN/9NKeOp8HztARi5nc7ijTY2tb0OU+GOvzy6km/LQAj3D7vI2F8++2KeKbfZshdKtgT///clMzidxIMggXWrXZRyBP5G3ZXTb9+bazZ8lwyy9BzrKPiq6ixFeaQJGtlgHXek6K8Sh28uq6bQ24fZ0nga0ZTzdQNK'
evl(f"document.getElementById('inp').value='{ct}'")
evl('doDec()')
time.sleep(1)
out1 = evl("document.getElementById('out').textContent")
print('解密输出:', out1[:100])

shot1 = send('Page.captureScreenshot', {'format': 'png'})['data']
pathlib.Path(r'<workdir>\poc_raw\shot_tool1.png').write_bytes(base64.b64decode(shot1))
print('shot_tool1 saved')

# 第二发: ecardno
evl("document.getElementById('inp').value='vF+gZwFNfYoQ59HqM7pEz+vowLvOjWmeyiVqacyQ2CHkyS7XwWhg/+95mr58SNAW'")
evl('doDec()')
time.sleep(1)
print('ecardno解密输出:', evl("document.getElementById('out').textContent")[:60])
shot2 = send('Page.captureScreenshot', {'format': 'png'})['data']
pathlib.Path(r'<workdir>\poc_raw\shot_tool2.png').write_bytes(base64.b64decode(shot2))
print('shot_tool2 saved')

ws.close()
proc.terminate()
