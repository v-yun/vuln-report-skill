#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""submit_gate.py — 交单物理闸

背景：提交白干的三大死因 = dup / OoS 受理失败 / 注水 informative，全部是交前可查没查。
不靠自觉，脚本不过 = 不许出稿。

用法：
    python tools/submit_gate.py <报告.md> [--why "G2③=客户交付无判例库:理由"]   # 豁免阀：某项不适用时带一句话理由放行（留痕可追责，不是静默跳过）

闸是防跳步的底，不是审批制——平台体系/报告形态不适用某项时（客户交付无过审先验、申诉评论无 scope 节…），用 --why 明示豁免并写进侧栏，比硬凑字过关诚实。

检查项（缺一=拒）：
  G1 定级行干净（结论一行）；推导进 <报告名>.gate.md 侧栏：平台体系（平台分级表/VRT/outcomes/判例带）优先、平台无体系才 CVSS 兜底——**推导禁入报告正文**
  G2 受理门三行（侧栏）：scope 原文映射(≥30字引文) / 近90天同类判例(收或不收+出处) / dup密度(数字或"查无披露库"明示)
  G3 危害 L 级标注：L0-L7 实验阶梯至少一级标注在危害/Impact 声明处
  G4 过审先验：`先验 N%` 或明示"查不到判例→降级为评论素材/不交"
  G5 禁编造引文：引号句全部来自存档文件（report 内 "引文" 若带 archived 标记则放行，
     否则要求 grep 存档命中——此处只做存在性提醒，交前逐条人工对源文件验命中）

退出码：0=放行出稿  1=拒（缺项清单打到 stdout）
"""
import io
import os
import re
import sys

try:  # GBK 控制台打印 ✗/对勾 会 UnicodeEncodeError 崩闸——闸崩=闸失效
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

CVSS_RE = re.compile(r"AV:[NALP]\s*/\s*AC:[LH]", re.I)
L_RE = re.compile(r"\bL[0-7]\b")
PRIOR_RE = re.compile(r"先验\s*[：:=≈~]?\s*(\d{1,3})\s*%|prior[s]?\s*[:=≈~]?\s*(\d{1,3})\s*%", re.I)
SCOPE_RE = re.compile(r'scope\s*原文|in-scope.{0,40}(原文|verbatim)', re.I)
QUOTE_RE = re.compile(r"[“\"]([^“”\"]{30,})[”\"]")

SEV_SECTION_RE = re.compile(r"(severity\s+rationale|定级依据|定级理由)", re.I)
PRECEDENT_RE = re.compile(r"(判例|precedent|同类.{0,8}(报告|判)|VRT|评分表|bounty\s*table)", re.I)
DUP_RE = re.compile(r"(dup.{0,12}(密度|density|率)|撞车.{0,10}(密度|率)|查无.{0,6}(披露|判例)库|未披露.{0,4}报告库)", re.I)
VERDICT90_RE = re.compile(r"(近\s*90\s*天|90\s*days?|近期.{0,4}判例| disclosed\s+reports?)", re.I)


def main() -> int:
    args = sys.argv[1:]
    whys = []
    while "--why" in args:
        i = args.index("--why")
        whys.append(args[i + 1] if i + 1 < len(args) else "")
        del args[i:i + 2]
    if not args:
        print(__doc__)
        return 2
    path = args[0]
    if not os.path.exists(path):
        print(f"[gate] 文件不存在: {path}")
        return 2
    text = io.open(path, encoding="utf-8", errors="replace").read()
    missing = []

    # G1 定级（平台体系优先，CVSS 只兜底；推导在 *.gate.md 侧栏，禁入报告正文）
    sidecar = path[:-3] + ".gate.md" if path.endswith(".md") else path + ".gate.md"
    side = io.open(sidecar, encoding="utf-8", errors="replace").read() if os.path.exists(sidecar) else ""
    sev_line = re.search(r"(severity\s*\**\s*[:=]\s*\**\s*(low|medium|high|critical|p[1-5]|info)|严重度\s*[:：].{1,12}|风险程度\s*[:：].{1,12}|漏洞等级\s*[:：].{1,12})", text, re.I)
    if not sev_line:
        missing.append("G1a 报告缺干净的定级行（severity: X 一行结论，不带推导）")
    if SEV_SECTION_RE.search(text):
        missing.append("G1b 报告正文含定级推导节（Severity rationale/定级依据）——推导是内部材料，写进报告=不专业，挪到 .gate.md 侧栏")
    if re.search(r"CVSS\s*3\.1[/ ]|AV:[NALP]", text, re.I) and "cvss" not in (path or "").lower():
        # 平台表单自带 CVSS 字段的除外（文件名含 cvss 的模板）——正文堆 CVSS 推导=内部材料泄漏
        missing.append("G1c 报告正文出现 CVSS 向量/推导——平台有自带 CVSS 字段时填表单，否则留 .gate.md（定级跟平台体系走，不死套 CVSS）")
    if not side:
        missing.append("G1d 缺内部对账侧栏 <报告名>.gate.md（平台体系行/判例带或 CVSS 兜底+终局 L 级——不进报告）")
    else:
        if not (CVSS_RE.search(side) or PRECEDENT_RE.search(side)):
            missing.append("G1d 侧栏缺定级依据：平台体系（平台分级表/VRT/outcomes/判例带）引用，或平台无体系时的 CVSS 兜底向量")
        if not L_RE.search(side):
            missing.append("G1d 侧栏缺终局 L 级标注（L0-L7 实测到第几级）")
        if not re.search(r"预计[^。\n]{0,40}判|prediction", side, re.I):
            missing.append("G1e 侧栏缺定级预测句（'预计该平台判 X，依据=锚点+证据档'——定级=预测 triager，自评≠拍脑袋；预测与实判的差值记回你自己的台账）")

    # G2 受理门（三行全在侧栏；报告只要求干净的 in-scope 声明）
    if not re.search(r"in.?\s?scope|scope\s*[:：]|范围内|资产.*授权", text, re.I):
        missing.append("G2① 报告缺 in-scope 资产声明（正常报告内容）")
    if side:
        if not (SCOPE_RE.search(side) or re.search(r"scope\s*原文", side, re.I)):
            missing.append("G2② 侧栏缺 scope 原文映射（policy in-scope 条款≥30字引文+逐条映射）")
        if not VERDICT90_RE.search(side):
            missing.append("G2③ 侧栏缺近90天同类判例行（收/不收+出处；查不到=明示并降级为评论素材）")
        if not DUP_RE.search(side):
            missing.append("G2④ 侧栏缺 dup 密度行（该程序已披露/判 dup 同族计数，或明示'查无披露库'）")
        # G4 过审先验（侧栏）
        if not PRIOR_RE.search(side):
            missing.append("G4 侧栏缺过审先验（'先验 N%' 或明示查不到判例→不交；没先验数字不许对用户说'可以交'）")

    # G3 L 级标注（侧栏——L级是内部对账口径，不写报告正文）
    if side and not L_RE.search(side):
        missing.append("G3 危害标注: 侧栏无 L0-L7 实测级标注（UNRESOLVED/L4 以下不交）")

    # G5 引文可溯源提醒（软门：只查存在性）
    quotes = QUOTE_RE.findall(text)
    if quotes:
        print(f"[gate] G5 提醒: 报告含 {len(quotes)} 处长引文——交前须逐条 grep 存档验命中（编造引文零容忍）")

    if missing:
        # 豁免阀：--why "G编号或关键词=理由" 只免命中的项，没被 why 覆盖的照拒
        waived, remain = [], []
        for x in missing:
            if any(w and w.split("=", 1)[0].strip().lower() in x.lower() for w in whys):
                w = next(w for w in whys if w.split("=", 1)[0].strip().lower() in x.lower())
                waived.append(f"{x.split(':')[0]} ← 豁免：{w.split('=', 1)[-1].strip()}")
            else:
                remain.append(x)
        for v in waived:
            print("  ~ " + v)
        if remain:
            print(f"[gate] 拒出稿 × {len(remain)}：{os.path.basename(path)}")
            for x in remain:
                print("  ✗ " + x)
            print("[gate] 补齐后重跑，或对不适用项用 --why 'G编号=理由' 显式豁免（留痕）。")
            return 1
        print(f"[gate] 放行（{len(waived)} 项显式豁免，理由已留痕）：{os.path.basename(path)}")
        return 0
    print(f"[gate] 放行 × 全绿：{os.path.basename(path)}（G1定级干净+侧栏推导/G2受理三行/G3 L级(侧栏)/G4先验 全在位）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
