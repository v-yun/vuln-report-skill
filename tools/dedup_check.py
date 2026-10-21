# -*- coding: utf-8 -*-
"""dedup_check — 提交前四视图撞车检查

Bugcrowd 提交自动比全库防 dup（98% 置信度）的本地版：写报告前/落稿时跑一次，
与「漏洞报告全库 + sessions findings 台账」比对四视图指纹，命中给撞车警告。
dup 的代价：多数平台撞车直接判重复、白干还扣声望，交前必查。

四视图（Bugcrowd 同款思路，纯本地零 LLM）：
  loc    资产位置：host + 路径模式（数字/长hex/uuid 归一为 {id}）
  repro  复现形状：HTTP 请求块的 method + host + 路径模式 + 参数名集合（值不参与）
  desc   描述 SimHash64（char-3gram，md5 特征，进程间确定）
  typ    漏洞类型词 + CWE 号

用法：
  python dedup_check.py <draft.md|draft.docx>            # 成稿查重（md/docx 都吃）
  python dedup_check.py --title "..." --asset "..." --vuln-type "越权"   # 落稿前快查
  python dedup_check.py <draft> --json                    # 机器可读输出
指纹缓存：fingerprints.json（按 mtime+size 增量更新，二次运行秒出，路径随语料定位）
"""
import hashlib
import json
import os
import re
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ── 语料定位（可移植）：DEDUP_CORPUS 环境变量 > 当前目录 漏洞报告/ ──
if os.environ.get("DEDUP_CORPUS"):
    CORPUS_ROOT = os.environ["DEDUP_CORPUS"]
    SESSIONS_DIR = os.environ.get("DEDUP_SESSIONS") or ""
    _CACHE_DIR = os.environ.get("DEDUP_CACHE") or os.path.join(tempfile.gettempdir(), "dedup_cache")
else:
    CORPUS_ROOT = os.path.join(os.getcwd(), "漏洞报告")
    SESSIONS_DIR = ""
    _CACHE_DIR = os.path.join(tempfile.gettempdir(), "dedup_cache")
CACHE_PATH = os.path.join(_CACHE_DIR, "fingerprints.json")

# ── 文本抽取 ──

def extract_text(path):
    try:
        if path.lower().endswith(".docx"):
            import docx
            d = docx.Document(path)
            parts = [p.text for p in d.paragraphs]
            for t in d.tables:
                for row in t.rows:
                    for c in row.cells:
                        parts.append(c.text)
            return "\n".join(parts)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return ""


# ── 视图 1：loc（host + 归一化路径） ──

URL_RE = re.compile(r"https?://([A-Za-z0-9.\-]+(?:\.\w+)+)(:\d+)?(/[^\s\"'<>）)、,，]*)?")
HEX_RE = re.compile(r"^[0-9a-fA-F]{8,}$")


def norm_seg(seg):
    s = seg.split("?")[0].split("#")[0]
    parts = [p for p in s.split("/") if p != ""]
    out = []
    for p in parts:
        if p.isdigit() and len(p) >= 2:
            out.append("{id}")
        elif HEX_RE.match(p) or len(p) >= 16 and p.isdigit():
            out.append("{id}")
        elif re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-", p):
            out.append("{uuid}")
        else:
            out.append(p.lower())
    return "/" + "/".join(out)


def view_loc(text):
    locs = set()
    for m in URL_RE.finditer(text):
        host = m.group(1).lower()
        path = norm_seg(m.group(3) or "/")
        locs.add(host + path)
        locs.add(host)  # 裸 host 也算（同资产不同路径的强弱信号）
    return {x for x in locs if "." in x and not x.endswith(".jpg") and not x.endswith(".png")}


# ── 视图 2：repro（method+host+路径模式+参数名集） ──

REQLINE_RE = re.compile(r"^(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s+(\S+)\s+HTTP", re.M | re.I)
HOSTHDR_RE = re.compile(r"^Host:\s*(\S+)", re.M | re.I)


def view_repro(text):
    reps = set()
    hosts = HOSTHDR_RE.findall(text)
    for m in REQLINE_RE.finditer(text):
        method = m.group(1).upper()
        target = m.group(2)
        if target.startswith("http"):
            hm = re.match(r"https?://([^/]+)(\S*)", target)
            if not hm:
                continue
            host, path = hm.group(1).lower(), hm.group(2)
        else:
            host = (hosts[0].lower() if hosts else "")
            path = target
        pp = norm_seg(path if path.startswith("/") else "/" + path)
        params = sorted(re.findall(r"[?&;]([A-Za-z_][\w]*)=", path))
        reps.add(method + " " + host.split(":")[0] + pp + ("?" + ",".join(params) if params else ""))
    return reps


# ── 视图 3：desc SimHash64 ──

def _feat_hash(s):
    h = hashlib.md5(s.encode("utf-8", "ignore")).digest()
    return int.from_bytes(h[:8], "big")


def simhash64(text, n=3):
    t = re.sub(r"\s+", "", text)
    if len(t) < n:
        return 0
    bits = [0] * 64
    for i in range(len(t) - n + 1):
        h = _feat_hash(t[i:i + n])
        for b in range(64):
            bits[b] += 1 if (h >> b) & 1 else -1
    v = 0
    for b in range(64):
        if bits[b] > 0:
            v |= 1 << b
    return v


def hamming(a, b):
    return bin(a ^ b).count("1")


# ── 视图 4：类型词 + CWE ──

TYPE_WORDS = [
    "越权", "未授权", "水平越权", "垂直越权", "IDOR", "RCE", "命令执行", "远程代码执行",
    "SQL注入", "SQLi", "注入", "XSS", "存储型", "反射型", "SSRF", "伪造", "上传",
    "接管", "账户接管", "ATO", "信息泄露", "敏感信息", "泄露", "绕过", "认证绕过",
    "逻辑漏洞", "业务逻辑", "任意文件读取", "文件读取", "目录遍历", "反序列化",
    "CORS", "CSRF", "重放", "短信轰炸", "验证码", "撞库", "越权查询",
]


def view_typ(text):
    t = set()
    low = text
    for w in TYPE_WORDS:
        if w.lower() in low.lower():
            t.add(w.upper())
    for c in re.findall(r"CWE-\d+", text, re.I):
        t.add(c.upper())
    return t


# ── 指纹组装 ──

def fingerprint(text):
    return {
        "loc": sorted(view_loc(text)),
        "repro": sorted(view_repro(text)),
        "desc": simhash64(text),
        "typ": sorted(view_typ(text)),
    }


def fingerprint_quick(title, asset, vuln_type):
    text = " ".join(x for x in [title, asset, vuln_type] if x)
    return {
        "loc": sorted(view_loc(text)),
        "repro": [],
        "desc": simhash64(text),
        "typ": sorted(view_typ(text)),
    }


# ── 语料加载（mtime 增量缓存） ──

def corpus_files():
    files = []
    for root, _, names in os.walk(CORPUS_ROOT):
        for n in names:
            if n.lower().endswith((".docx", ".md")) and not n.startswith("~$"):
                files.append(os.path.join(root, n))
    return files


def load_cache():
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(cache):
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception:
        pass


def build_corpus():
    cache = load_cache()
    changed = False
    corpus = []
    for p in corpus_files():
        try:
            st = os.stat(p)
        except OSError:
            continue
        key = "%d_%d" % (int(st.st_mtime), st.st_size)
        hit = cache.get(p)
        if hit and hit.get("_k") == key:
            corpus.append((p, hit))
            continue
        fp = fingerprint(extract_text(p))
        fp["_k"] = key
        cache[p] = fp
        corpus.append((p, fp))
        changed = True
    # findings 台账（sessions/*.findings.jsonl）：字段级拼接当文本
    try:
        for n in os.listdir(SESSIONS_DIR):
            if not n.endswith(".findings.jsonl"):
                continue
            p = os.path.join(SESSIONS_DIR, n)
            st = os.stat(p)
            key = "%d_%d" % (int(st.st_mtime), st.st_size)
            hit = cache.get(p)
            if hit and hit.get("_k") == key:
                corpus.append((p, hit))
                continue
            rows = []
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        r = json.loads(line)
                    except Exception:
                        continue
                    rows.append(" ".join(str(r.get(k, "")) for k in
                                         ("title", "asset", "vuln_type", "impact", "poc", "evidence")))
            fp = fingerprint("\n".join(rows))
            fp["_k"] = key
            cache[p] = fp
            corpus.append((p, fp))
            changed = True
    except OSError:
        pass
    if changed:
        save_cache(cache)
    return corpus


# ── 比对与裁决 ──

def overlap(a, b):
    if not a or not b:
        return 0.0
    inter = len(set(a) & set(b))
    return inter / min(len(a), len(b))


def compare(fp, other):
    loc = overlap(fp["loc"], other["loc"])
    repro = overlap(fp["repro"], other["repro"])
    typ = overlap(fp["typ"], other["typ"])
    d = 1.0 - hamming(fp["desc"], other["desc"]) / 64.0
    desc = d if d >= 0.80 else 0.0  # hamming≤12 才算相似：报告同模板骨架常态 hamming≈14-16，收不紧全是假阳
    score = loc * 0.35 + repro * 0.30 + desc * 0.20 + typ * 0.15
    return score, {"loc": round(loc, 2), "repro": round(repro, 2), "desc": round(desc, 2), "typ": round(typ, 2)}


def run(fp, corpus, top=8, exclude=None):
    results = []
    for p, other in corpus:
        if exclude and os.path.normcase(os.path.abspath(p)) == os.path.normcase(os.path.abspath(exclude)):
            continue  # 草稿本身就在语料里（第 5 步更新场景）：不算自己撞自己
        score, views = compare(fp, other)
        if score > 0.15:
            results.append((score, p, views))
    results.sort(reverse=True)
    return results[:top]


def main():
    args = sys.argv[1:]
    as_json = "--json" in args
    args = [a for a in args if a != "--json"]
    if not args:
        print(__doc__)
        sys.exit(2)
    if args[0] == "--title":  # 快查模式
        kv = {}
        for i in range(0, len(args) - 1, 2):
            kv[args[i].lstrip("-")] = args[i + 1]
        fp = fingerprint_quick(kv.get("title", ""), kv.get("asset", ""), kv.get("vuln-type", ""))
    else:
        draft = args[0]
        if not os.path.exists(draft):
            print("[dedup] 草稿不存在: %s" % draft)
            sys.exit(2)
        text = extract_text(draft)
        if not text.strip():
            print("[dedup] 草稿无文本可抽（空文件或解析失败）")
            sys.exit(2)
        fp = fingerprint(text)

    corpus = build_corpus()
    exclude = None if args[0] == "--title" else args[0]
    results = run(fp, corpus, exclude=exclude)

    if as_json:
        print(json.dumps({"count": len(corpus), "hits": [
            {"score": round(s, 3), "file": p, "views": v} for s, p, v in results]}, ensure_ascii=False, indent=1))
        return

    print("[dedup] 语料 %d 份（漏洞报告 + findings 台账）· 指纹缓存 %s" % (len(corpus), CACHE_PATH))
    if not corpus:
        print("[警告] 语料库为空（%s）：查重无意义，本次不给出判定。" % CORPUS_ROOT)
        print("        语料=你自己的历史报告库。设环境变量 DEDUP_CORPUS 指向报告目录后重跑。")
        return
    if not results:
        print("[判定·未见撞车] 四视图无显著重合——可以写/交；交前仍过红队分离评审")
        return
    high = [r for r in results if r[0] >= 0.6]
    for score, path, views in results:
        flag = "HIGH" if score >= 0.6 else ("MID" if score >= 0.35 else "low")
        print("  [%s %.2f] %s  (loc=%s repro=%s desc=%s typ=%s)" % (flag, score, path, views["loc"], views["repro"], views["desc"], views["typ"]))
    if high:
        print("[判定·疑似撞车] %d 份 HIGH——停：并报进原报告（skill 第 6 步融合改写）或撤稿换资产/换类型，交上去就是 dup 罚声望" % len(high))
        sys.exit(1)
    # 判同口径：身份=源×sink——同一受控值进同一执行/渲染上下文才算同一洞；
    # 同资产/同 CWE/同 payload/同文件只是佐证，佐证重合≠撞车，防过度合并把两个真洞并成一个。
    print("[判定·需人工判读] 有 MID 级重合——判同问「源×sink 是否同一个」（同一受控值进同一执行/渲染上下文）："
          "源×sink 同一并报，仅资产/CWE/payload 重合=佐证不算撞车，各自独立交")


if __name__ == "__main__":
    main()
