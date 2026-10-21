#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""burp_shot — 把真实抓包字节渲染成中文暗色 HTTP 调试工具风格截图(双栏)
用法:
  python render.py --req req.raw --resp resp.raw --host api.example.com --out shot.png
  (req/resp = 原始字节文件: req 含请求行+头+体; resp 含状态行+头+体; 默认 1588x676)

风格基准(中文汉化 Burp 类调试工具截图):
  双栏编辑器+行号槽 | 蓝灰语法色(方法/头名) 琥珀(JSON键/数字) 橄榄绿(JSON字符串) |
  中文 chrome(转发/取消/目标/请求/响应/完成) | 右缘折叠检查器条 | 无滚动条无状态药丸

契约(铁律,违反=伪造证据):
  1. req/resp 必须逐字节来自真实抓包(目标实际发出的请求/实际收到的响应),
     从抓包日志/curl -i 原始输出/抓包工具导出文件直接取,禁止手敲或改写任何字节。
  2. 渲染只负责外壳(版式/着色),不增删改任何报文内容——着色 span 只包字不改字。
  3. 拿不准的元数据(host/大小)留默认,不要编造。
"""
import argparse, html, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_W, BASE_H = 1588, 676


def _find_browser():
    """headless 截图引擎定位: BURP_SHOT_CHROME 环境变量 → 常见 Chrome/Edge 安装路径 → PATH 查找。"""
    env = os.environ.get("BURP_SHOT_CHROME")
    if env and os.path.exists(env):
        return env
    cands = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
    ]
    for c in cands:
        if c and os.path.exists(c):
            return c
    for name in ("chrome", "google-chrome", "chromium", "msedge"):
        cmd = ["where" if os.name == "nt" else "which", name]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True).stdout.strip().splitlines()
        except OSError:
            continue
        if out and os.path.exists(out[0]):
            return out[0]
    sys.exit("找不到 Chrome/Edge（headless 截图引擎）。设环境变量 BURP_SHOT_CHROME 指向浏览器可执行文件后重试。")


CHROME = _find_browser()

def esc(t: str) -> str:
    return html.escape(t, quote=False)

TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?|\b(?:true|false|null)\b')

def hl_json_line(ln: str) -> str:
    """JSON 行着色: 键=琥珀 字符串=橄榄绿 数字=琥珀 关键字=蓝灰。只包 span 不改字。"""
    out, idx, n = [], 0, len(ln)
    for m in TOKEN.finditer(ln):
        out.append(esc(ln[idx:m.start()]))
        tok = m.group(0)
        j = m.end()
        while j < n and ln[j] == " ": j += 1
        if tok.startswith('"') and j < n and ln[j] == ":":
            out.append(f'<span class="jkey">{esc(tok)}</span>')
        elif tok.startswith('"'):
            out.append(f'<span class="jstr">{esc(tok)}</span>')
        elif tok[0].isdigit() or tok[0] == "-":
            out.append(f'<span class="jnum">{esc(tok)}</span>')
        else:
            out.append(f'<span class="jkw">{esc(tok)}</span>')
        idx = m.end()
    out.append(esc(ln[idx:]))
    return "".join(out)

def hl_request(raw: str) -> str:
    out, in_body = [], False
    for i, ln in enumerate(raw.replace("\r\n", "\n").split("\n")):
        if in_body:
            out.append(hl_json_line(ln)); continue
        if ln == "":
            out.append(""); in_body = True; continue
        m = re.match(r"^(\S+)\s+(\S+)\s+(HTTP/[\d.]+)$", ln)
        if m and i == 0:
            out.append(f'<span class="method">{esc(m.group(1))}</span> '
                       f'<span class="path">{esc(m.group(2))}</span> '
                       f'<span class="ver">{esc(m.group(3))}</span>')
            continue
        m = re.match(r"^([A-Za-z0-9-]+):(.*)$", ln)
        if m:
            out.append(f'<span class="hdrname">{esc(m.group(1))}</span>:'
                       f'<span class="hdrval">{esc(m.group(2))}</span>')
        else:
            out.append(esc(ln))
    return "\n".join(out)

def hl_response(raw: str) -> str:
    out, in_body = [], False
    lines = raw.replace("\r\n", "\n").split("\n")
    for i, ln in enumerate(lines):
        if in_body:
            out.append(hl_json_line(ln)); continue
        if ln == "":
            out.append(""); in_body = True; continue
        m = re.match(r"^(HTTP/[\d.]+)\s+(\d{3})(.*)$", ln)
        if m and i == 0:
            cls = m.group(2).startswith("2") and "st-2xx" or m.group(2).startswith("4") and "st-4xx" or \
                  (m.group(2).startswith("5") and "st-5xx" or "st-2xx")
            out.append(f'<span class="st-line">{esc(m.group(1))}</span> '
                       f'<span class="{cls}">{esc(m.group(2) + m.group(3))}</span>')
            continue
        m = re.match(r"^([A-Za-z0-9-]+):(.*)$", ln)
        if m:
            out.append(f'<span class="hdrname">{esc(m.group(1))}</span>:'
                       f'<span class="hdrval">{esc(m.group(2))}</span>')
        else:
            out.append(esc(ln))
    return "\n".join(out)

def gutter_for(raw: str) -> str:
    n = len(raw.replace("\r\n", "\n").split("\n"))
    return "\n".join(str(i) for i in range(1, n + 1))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--req", required=True, help="真实请求原始字节文件")
    ap.add_argument("--resp", required=True, help="真实响应原始字节文件")
    ap.add_argument("--host", default="target", help="目标 host(仅显示用)")
    ap.add_argument("--out", required=True, help="输出 PNG 路径")
    ap.add_argument("--width", type=int, default=BASE_W, help=f"渲染宽度(默认{BASE_W},等比缩放)")
    ap.add_argument("--height", type=int, default=0, help="渲染高度(默认按宽度等比)")
    a = ap.parse_args()

    req_b = open(a.req, "rb").read()
    resp_b = open(a.resp, "rb").read()
    req, resp = req_b.decode("utf-8", "replace"), resp_b.decode("utf-8", "replace")
    tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()

    url = f"https://{a.host}/"
    zoom = a.width / BASE_W
    height = a.height or round(BASE_H * zoom)

    tpl = tpl.replace("{ZOOM}", f"{zoom:.4f}" if zoom != 1 else "1")
    tpl = tpl.replace("{TITLE_URL}", esc(url)).replace("{TARGET_URL}", esc(url))
    tpl = tpl.replace("{GUTTER1}", gutter_for(req)).replace("{GUTTER2}", gutter_for(resp))
    tpl = tpl.replace("{REQ_HTML}", hl_request(req)).replace("{RESP_HTML}", hl_response(resp))
    tpl = tpl.replace("{BYTES}", f"已接收 {len(resp_b):,} 字节")

    tmp = os.path.join(tempfile.gettempdir(), f"burpshot_{os.getpid()}.html")
    open(tmp, "w", encoding="utf-8").write(tpl)
    out = os.path.abspath(a.out)
    cmd = [CHROME, "--headless=new", f"--screenshot={out}", f"--window-size={a.width},{height}",
           "--hide-scrollbars", "--disable-gpu", "--no-sandbox", "--disable-lcd-text",
           f"file:///{tmp.replace(os.sep, '/')}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    os.remove(tmp)
    if not os.path.exists(out):
        print("CHROME FAILED:", r.stderr[:500]); sys.exit(1)
    print("OK", out, f"{os.path.getsize(out)} bytes")

if __name__ == "__main__":
    main()
