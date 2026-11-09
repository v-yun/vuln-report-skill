#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""white_shot — 把真实抓包字节渲染成白底报告风格截图（客户交付默认款）
与 yakit_shot 同契约：req/resp 逐字节来自真实抓包，渲染只做外壳，改一字节=伪造证据。
用法: python render.py --req req.raw --resp resp.raw --host api.example.com --out shot.png [--title "POST /x 登录"]
立法：国内客户交付统一白底款，深色调试工具风仅平台口味点名时用。"""
import argparse, html, os, subprocess, sys, tempfile

EDGE_CANDIDATES = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
]

CSS = """
body{margin:0;background:#fff;font-family:'Microsoft YaHei',sans-serif}
.hdr{border-bottom:2px solid #2b579a;padding:10px 16px 8px}
.hdr .t{color:#1f3864;font-size:15px;font-weight:600;font-family:Consolas,monospace}
.hdr .s{color:#666;font-size:11.5px;margin-top:2px}
.sec{padding:10px 16px 0}
.sec .lab{color:#2b579a;font-size:12px;font-weight:600;margin-bottom:4px}
pre{margin:0;font-family:Consolas,'Courier New',monospace;font-size:13px;line-height:1.5;
    white-space:pre-wrap;word-break:break-all;color:#1a1a1a;background:#fafbfd;
    border:1px solid #e3e6ee;padding:10px 12px}
.m0{color:#881280;font-weight:600}.u{color:#1a1aa6}
.st{color:#0b7500;font-weight:600}.err{color:#b00020;font-weight:600}
.note{color:#888;font-size:10.5px;padding:8px 16px 12px}
"""

def find_browser():
    env = os.environ.get('WHITE_SHOT_BROWSER')
    if env and os.path.exists(env):
        return env
    for c in EDGE_CANDIDATES:
        if c and os.path.exists(c):
            return c
    return None


def colorize(text):
    """最小着色：请求行/响应行加粗变色，状态码按成败着色。只包不改字。"""
    lines = html.escape(text, quote=False).split('\n')
    out = []
    for i, ln in enumerate(lines):
        if i == 0:
            parts = ln.split(' ')
            if len(parts) >= 2 and parts[0] in ('GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'):
                out.append(f'<span class="m0">{parts[0]}</span> <span class="u">{" ".join(parts[1:])}</span>')
                continue
            if ln.startswith('HTTP/'):
                segs = ln.split(' ', 2)
                cls = 'st' if (len(segs) > 1 and segs[1].startswith('2')) else 'err'
                out.append(f'<span class="{cls}">{ln}</span>')
                continue
        out.append(ln)
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--req', required=True)
    ap.add_argument('--resp', required=True)
    ap.add_argument('--host', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--title', default='')
    ap.add_argument('--sub', default='')
    ap.add_argument('--height', type=int, default=560)
    ap.add_argument('--width', type=int, default=860)  # 860px@5.5in≈157dpi，13px字≈6pt，与验收过的yakit密度一致
    args = ap.parse_args()

    req = open(args.req, encoding='utf-8', errors='replace').read().rstrip('\n')
    resp = open(args.resp, encoding='utf-8', errors='replace').read().rstrip('\n')
    first = req.split('\n', 1)[0]
    title = args.title or first
    sub = args.sub or f'Host: {args.host} · 请求/响应为真实抓包原文'

    page_html = f"""<html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div class="hdr"><div class="t">{html.escape(title)}</div><div class="s">{html.escape(sub)}</div></div>
<div class="sec"><div class="lab">Request</div><pre>{colorize(req)}</pre></div>
<div class="sec"><div class="lab">Response</div><pre>{colorize(resp)}</pre></div>
<div class="note">报文为测试时抓包原文，未做任何字节改动</div>
</body></html>"""

    browser = find_browser()
    assert browser, 'no edge/chrome found'
    with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False, encoding='utf-8') as f:
        f.write(page_html)
        tmp = f.name
    r = subprocess.run([browser, '--headless', f'--screenshot={os.path.abspath(args.out)}',
                        f'--window-size={args.width},{args.height}', 'file:///' + tmp.replace('\\', '/')],
                       capture_output=True, text=True)
    os.unlink(tmp)
    ok = os.path.exists(args.out) and os.path.getsize(args.out) > 5000
    print('OK' if ok else f'FAIL {r.returncode} {r.stderr[:120]}', os.path.abspath(args.out))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
