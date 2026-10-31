#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""yakit_shot — 把真实抓包字节渲染成 Yakit Web Fuzzer 风格截图
用法: python render.py --req req.raw --resp resp.raw --host api.example.com --out shot.png [--ms 56]"""
import argparse, html, json, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

def find_browser():
    env = os.environ.get('YAKIT_SHOT_BROWSER')
    if env and os.path.exists(env):
        return env
    for c in [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
              r'C:\Program Files\Google\Chrome\Application\chrome.exe',
              r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe']:
        if c and os.path.exists(c):
            return c
    return None

def esc(s):
    return html.escape(s, quote=False)

def hl_json(text):
    def repl(m):
        t = m.group(0)
        if t.startswith('"'):
            rest = text[m.end():m.end() + 2]
            if rest.lstrip().startswith(':'):
                return '<span class="jk">%s</span>' % esc(t)
            return '<span class="js">%s</span>' % esc(t)
        if re.match(r'^-?\d', t):
            return '<span class="jn">%s</span>' % esc(t)
        if t in ('true', 'false', 'null'):
            return '<span class="jb">%s</span>' % esc(t)
        return esc(t)
    return re.sub(r'"(?:[^"\\]|\\.)*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null', repl, text)

def hl_form(text):
    """urlencoded表单体: 参数名蓝粗=值分色"""
    def repl(m):
        val = esc(m.group(2) or '')
        if len(val) > 40:
            return '<span class="fn">%s</span>=<span class="fv2">%s</span>' % (esc(m.group(1)), val)
        if val in ('', '123'):
            return '<span class="fn">%s</span>=<span class="fv3">%s</span>' % (esc(m.group(1)), val)
        return '<span class="fn">%s</span>=<span class="fv">%s</span>' % (esc(m.group(1)), val)
    result = re.sub(r'([a-zA-Z_][a-zA-Z0-9_]*)=([^&]*)', repl, text)
    result = result.replace('&', '<span class="amp">&amp;</span>')
    return result

def split_http(raw):
    s = raw.decode('utf-8', errors='replace')
    head, _, body = s.partition('\r\n\r\n')
    return head.split('\r\n'), body

def render_request(raw):
    lines, body = split_http(raw)
    out = []
    if lines:
        m = re.match(r'^(\S+) (\S+) (\S+)$', lines[0])
        if m:
            out.append('<span class="m">%s</span> <span class="path">%s</span> <span class="ver">%s</span>'
                       % (esc(m.group(1)), esc(m.group(2)), esc(m.group(3))))
        else:
            out.append(esc(lines[0]))
    for l in lines[1:]:
        if ':' in l:
            k, v = l.split(':', 1)
            out.append('<span class="hn">%s</span>:<span class="hv">%s</span>' % (esc(k), esc(v)))
        else:
            out.append(esc(l))
    out.append('')
    if body:
        if body.strip().startswith('{'):
            out.append(hl_json(body))
        elif '=' in body and '&' in body:
            out.append(hl_form(body))
        else:
            out.append(esc(body))
    return '\n'.join(out)

def render_response(raw):
    lines, body = split_http(raw)
    out = []
    if lines:
        out.append('<span class="st">%s</span>' % esc(lines[0]))
    for l in lines[1:10]:
        if ':' in l:
            k, v = l.split(':', 1)
            out.append('<span class="rhk">%s</span>:<span class="rhv">%s</span>' % (esc(k), esc(v)))
        elif l:
            out.append(esc(l))
    out.append('')
    if body:
        try:
            obj = json.loads(body)
            pretty = json.dumps(obj, ensure_ascii=False, indent=2)
            out.append(hl_json(pretty))
        except Exception:
            out.append(esc(body[:2000]))
    return '\n'.join(out)

def _log_call(a):
    # 出稿武器登记(2026-10-29 幽灵稿判例): 每次渲染落一行,谁在何时对哪个host出了图,盘上留痕
    try:
        import datetime
        logp = os.path.normpath(os.path.join(HERE, 'render_calls.log'))
        os.makedirs(os.path.dirname(logp), exist_ok=True)
        with open(logp, 'a', encoding='utf-8') as f:
            f.write('%s\tyakit_shot\t%s\t%s\t%s\n' % (
                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                a.host, os.path.abspath(a.req), os.path.abspath(a.out)))
    except Exception:
        pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--req', required=True)
    ap.add_argument('--resp', required=True)
    ap.add_argument('--host', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--width', type=int, default=863)
    ap.add_argument('--height', type=int, default=435)
    ap.add_argument('--ms', default='56')
    a = ap.parse_args()
    _log_call(a)

    req = open(a.req, 'rb').read()
    resp = open(a.resp, 'rb').read()
    tpl = open(os.path.join(HERE, 'template.html'), encoding='utf-8').read()

    m = re.match(r'^(\S+) (\S+) (\S+)$', req.decode('utf-8', errors='replace').split('\r\n')[0])
    method_path = (m.group(1) + ' ' + m.group(2)) if m else 'HTTP'
    status_m = re.match(r'^(\S+ \d+[^\r\n]*)', resp.decode('utf-8', errors='replace'))
    status = status_m.group(1) if status_m else 'HTTP/1.1 200 OK'

    fill = {
        '__URL__': esc('https://' + a.host + (('/' + m.group(2).lstrip('/')) if m else '')),
        '__REQUEST__': render_request(req),
        '__RESPONSE__': render_response(resp),
    }
    for k, v in fill.items():
        tpl = tpl.replace(k, v)

    tmp = tempfile.NamedTemporaryFile('w', suffix='.html', delete=False, encoding='utf-8')
    tmp.write(tpl); tmp.close()
    browser = find_browser()
    if not browser:
        print('no browser'); sys.exit(1)
    subprocess.run([browser, '--headless', '--disable-gpu', '--hide-scrollbars',
                    '--window-size=%d,%d' % (a.width, a.height),
                    '--default-background-color=FFFFFFFF',
                    '--screenshot=' + os.path.abspath(a.out),
                    'file:///' + tmp.name.replace('\\', '/')],
                   capture_output=True, timeout=90)
    ok = os.path.exists(a.out) and os.path.getsize(a.out) > 10000
    print('OK' if ok else 'FAIL', os.path.abspath(a.out))

if __name__ == '__main__':
    main()
