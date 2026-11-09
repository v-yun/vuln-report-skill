# -*- coding: utf-8 -*-
"""CDP 驱动真实浏览器截图 rig（通用版：参数化，无战役现场数据）
用法: python browser_cdp_shot.py <url> <out.png> [--wait-js EXPR] [--eval EXPR ...] [--port N] [--profile DIR]
--wait-js 轮询执行 JS 到返回 true 再继续；--eval 依序执行（填值/点按钮）后截图。
示例: python browser_cdp_shot.py "file:///C:/tool/index.html" shot.png --wait-js "document.getElementById('selftest').textContent.includes('PASS')" --eval "document.getElementById('inp').value='DEMO_INPUT'" --eval "doRun()"
需 pip install websocket-client"""
import subprocess, time, json, urllib.request, base64, pathlib, argparse

ap = argparse.ArgumentParser()
ap.add_argument('url'); ap.add_argument('out')
ap.add_argument('--wait-js', dest='wait_js', default=None)
ap.add_argument('--eval', dest='evals', action='append', default=[])
ap.add_argument('--port', type=int, default=19223)
ap.add_argument('--profile', default=None)
a = ap.parse_args()

args = [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        f'--remote-debugging-port={a.port}', '--window-size=1280,900',
        '--no-first-run', '--no-default-browser-check']
if a.profile:
    args.append(f'--user-data-dir={a.profile}')
args.append(a.url)
proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(6)

tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{a.port}/json'))
ws_url = next(t['webSocketDebuggerUrl'] for t in tabs if t['type'] == 'page')
import websocket
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

# 等待条件（可选）
if a.wait_js:
    for _ in range(30):
        if evl(a.wait_js): break
        time.sleep(0.5)

for e in a.evals:
    evl(e)
    time.sleep(1)

shot = send('Page.captureScreenshot', {'format': 'png'})['data']
out = pathlib.Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(base64.b64decode(shot))
print('saved', a.out)
ws.close()
proc.terminate()
