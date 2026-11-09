# -*- coding: utf-8 -*-
# 以客户定版模板为基座整体重写报告（skill铁律：整体重写，禁补丁）
# 保：封面表(改文字)/目录sdt/正文前空段/附录A等级评定表；删：旧正文；插：新内容
import sys, copy
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

TPL = sys.argv[2] if len(sys.argv) > 2 else r'<客户定版模板.docx>'   # 用法: python build_report.py <内容模块> <模板docx>

# 客户模板标题样式名（按当轮模板探实际值替换；Word 默认为 '标题 2'/'标题 3'，
# 定版模板常用自定义名如拼音/项目前缀系——探法：读模板内 h2/h3 段落的 style.name）
STYLE_H2, STYLE_H3 = '标题 2', '标题 3'


def para_text(p):
    if hasattr(p, 'itertext'):
        return ''.join(p.itertext()).strip()
    return p.text.strip()


def build(mod_name):
    mod = __import__(mod_name)
    doc = Document(TPL)
    body = doc.element.body

    # ---- 先探样式（删除前）----
    cover_tbl = doc.tables[0]
    obj_tbl_style = doc.tables[1].style  # 对象表样式
    # 探模板标题的outlineLvl（老标题是段落直设，样式不带，必须复制给新标题否则目录抓不到）
    lvl_h2, lvl_h3 = '1', '2'
    for p in doc.paragraphs:
        t = p.text.strip()
        if t == '一、漏洞概况':
            ol = p._p.find(qn('w:pPr') + '/' + qn('w:outlineLvl'))
            if ol is not None:
                lvl_h2 = ol.get(qn('w:val'))
        elif t.startswith('1.1.1 '):
            ol = p._p.find(qn('w:pPr') + '/' + qn('w:outlineLvl'))
            if ol is not None:
                lvl_h3 = ol.get(qn('w:val'))
    print('  outlineLvl probes: h2=%s h3=%s' % (lvl_h2, lvl_h3))
    # HTTP块字体：找模板里POST开头的段，取其第一个run的字体设置
    http_font = {}
    for p in doc.paragraphs:
        if p.text.strip().startswith(('POST ', 'GET ')):
            for r in p.runs:
                http_font['name'] = r.font.name
                http_font['size'] = r.font.size
                rf = r.font.element.find(qn('w:rFonts'))
                if rf is not None:
                    http_font['eastAsia'] = rf.get(qn('w:eastAsia'))
                break
            break

    # ---- 封面改文字（保run格式：改首run文本，其余run清空）----
    def set_para_text(p, lines):
        # lines: list of str，用 w:br 连接；保留第一个run的rPr
        runs = p.runs
        if not runs:
            p.add_run('\n'.join(lines))
            return
        first = runs[0]
        for r in runs[1:]:
            r._element.getparent().remove(r._element)
        # 清掉first既有文本节点，重建
        for t in first._element.findall(qn('w:t')):
            first._element.remove(t)
        for br in first._element.findall(qn('w:br')):
            first._element.remove(br)
        for i, line in enumerate(lines):
            if i:
                first._element.append(OxmlElement('w:br'))
            t = OxmlElement('w:t')
            t.set(qn('xml:space'), 'preserve')
            t.text = line
            first._element.append(t)

    cover_paras = cover_tbl.rows[0].cells[0].paragraphs + \
                  [p for row in cover_tbl.rows[1:] for p in row.cells[0].paragraphs]
    # 找含旧标题/旧公司日期的段
    import re as _re
    for p in cover_paras:
        txt = p.text
        if mod.COVER['title_anchor'] in txt:
            set_para_text(p, [mod.COVER['title']])
        elif mod.COVER['org_anchor'] in txt:
            set_para_text(p, [mod.COVER['org']])
        elif _re.search(r'\d{4}年\d{1,2}月\d{1,2}日', txt):
            set_para_text(p, [mod.COVER['date']])

    # ---- 找锚点：附录A标题 ----
    appendixa = None
    for p in doc.paragraphs:
        if para_text(p) == '附录A 安全等级评定':
            appendixa = p
            break
    assert appendixa is not None, '附录A锚点未找到'

    # ---- 删除正文：从"一、漏洞概况"到附录A之前 ----
    started = False
    for el in list(body):
        if el is appendixa._p:
            break
        if el.tag == qn('w:p'):
            if para_text(el) and para_text(el).startswith('一、漏洞概况'):
                started = True
        if started:
            body.remove(el)

    # ---- 插入新内容（insert_paragraph_before按调用序落位）----
    def add_p(text, style='Normal'):
        p = appendixa.insert_paragraph_before(text, style=doc.styles[style])
        if style == STYLE_H2:
            _set_outline(p, lvl_h2)
        elif style == STYLE_H3:
            _set_outline(p, lvl_h3)
        return p

    def _set_outline(p, val):
        ppr = p._p.get_or_add_pPr()
        ol = OxmlElement('w:outlineLvl')
        ol.set(qn('w:val'), val)
        ppr.append(ol)

    def add_http(lines):
        p = appendixa.insert_paragraph_before('', style=doc.styles['Normal'])
        r = p.add_run()
        for i, line in enumerate(lines):
            if i:
                r.add_break()
            r.add_text(line)
        r.font.name = 'Consolas'
        r.font.size = Pt(10.5)
        rf = r.font.element.get_or_add_rPr().get_or_add_rFonts()
        rf.set(qn('w:eastAsia'), '宋体')
        return p

    def add_img(idx, caption):
        import os
        from PIL import Image
        path = mod.META['img_prefix'] % idx
        assert os.path.exists(path), path
        with Image.open(path) as im:
            w_px, h_px = im.size
        disp_w = min(5.5, 4.3 * w_px / max(1, h_px))  # 宽≤5.5in 且 高≤4.3in（客户模板基线）
        p = appendixa.insert_paragraph_before('', style=doc.styles['Normal'])
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.keep_with_next = True  # 图不与图注分页
        p.add_run().add_picture(path, width=Inches(disp_w))
        cap = appendixa.insert_paragraph_before(caption, style=doc.styles['Normal'])
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER

    def add_table(rows):
        t = doc.add_table(rows=len(rows), cols=len(rows[0]))
        t.style = obj_tbl_style
        for ri, row in enumerate(rows):
            for ci, cell in enumerate(row):
                c = t.cell(ri, ci)
                c.text = ''
                first = True
                for line in cell.split('\n'):
                    if first:
                        para = c.paragraphs[0]
                        first = False
                    else:
                        para = c.add_paragraph()
                    para.add_run(line)
        appendixa._p.addprevious(t._tbl)

    for op in mod.CONTENT:
        kind = op[0]
        if kind == 'h2':
            add_p(op[1], STYLE_H2)
        elif kind == 'h3':
            add_p(op[1], STYLE_H3)
        elif kind == 'p':
            add_p(op[1])
        elif kind == 'urls':
            for u in op[1]:
                add_p(u)
        elif kind == 'http':
            add_http(op[1])
        elif kind == 'img':
            add_img(op[1], op[2])
        elif kind == 'table':
            add_table(op[1])
        else:
            raise ValueError(kind)

    # ---- 附录B：插在最后一个空段（sectPr前）之前 ----
    tail_anchor = None
    for el in reversed(list(body)):
        if el.tag == qn('w:p'):
            tail_anchor = el
            break
    # tail_anchor 此时是附录A表格后的空段；找它前面的表格之后的第一个p
    # 简化：直接以最后一个 w:p 为锚（位于附录A表之后）
    for op in mod.APPENDIX_B:
        kind = op[0]
        if kind == 'h2':
            p = _new_p(doc, op[1], STYLE_H2)
            _set_outline(p, lvl_h2)
            tail_anchor.addprevious(p._p)
        elif kind == 'p':
            tail_anchor.addprevious(_new_p(doc, op[1], 'Normal')._p)
        elif kind == 'http':
            p = _new_p(doc, '', 'Normal')
            r = p.add_run()
            for i, line in enumerate(op[1]):
                if i:
                    r.add_break()
                r.add_text(line)
            if http_font.get('name'):
                r.font.name = http_font['name']
            if http_font.get('size'):
                r.font.size = http_font['size']
            tail_anchor.addprevious(p._p)

    # ---- 打开时刷新目录 ----
    settings = doc.settings.element
    upd = OxmlElement('w:updateFields')
    upd.set(qn('w:val'), 'true')
    settings.append(upd)

    # ---- docProps 清理 ----
    cp = doc.core_properties
    cp.author = ''
    cp.last_modified_by = ''
    cp.comments = ''
    cp.category = ''
    cp.subject = ''
    cp.keywords = ''

    # ---- 字体规范落地（客户口径：正文宋体12pt+Times New Roman，标题黑体；HTTP块Consolas）----
    font_sweep(doc, cover_tbl)

    # ---- 附录A等级表括号改冒号（机器审计括号门；语义不变）----
    for t in doc.tables:
        for row in t.rows:
            for c in row.cells:
                for p in c.paragraphs:
                    for r in p.runs:
                        if '（符合任何一个条件）' in r.text or '（符合全部条件）' in r.text:
                            r.text = r.text.replace('（符合任何一个条件）', '：符合任何一个条件').replace('（符合全部条件）', '：符合全部条件')

    doc.save(mod.META['docx_out'])
    strip_orphan_media(mod.META['docx_out'])
    print('BUILT', mod.META['docx_out'])


def strip_orphan_media(path):
    # 模板旧图已随旧正文删除，但包内media+rels残留 → 重打包剥离
    import re as _re
    import zipfile as _zf
    import shutil as _sh
    import os as _os
    tmp = path + '.stripping'
    with _zf.ZipFile(path) as z:
        names = z.namelist()
        data = {n: z.read(n) for n in names}
    used_rids = set()
    for n in names:
        if _re.match(r'word/(document|header\d*|footer\d*)\.xml$', n):
            used_rids.update(_re.findall(rb'r:(?:embed|id|link)="(rId\d+)"', data[n]))
    drop_media = set()
    for n in names:
        m = _re.match(r'word/_rels/(document|header\d*|footer\d*)\.xml\.rels$', n)
        if not m:
            continue
        part = 'word/%s.xml' % m.group(1)
        part_used = set(_re.findall(rb'r:(?:embed|id|link)="(rId\d+)"', data[part]))
        rels = data[n]
        def _filter(mo):
            tag = mo.group(0)
            rid = _re.search(rb'Id="(rId\d+)"', tag)
            typ = _re.search(rb'Type="([^"]+)"', tag)
            tgt = _re.search(rb'Target="([^"]+)"', tag)
            if typ and tgt and rid and b'/image' in typ.group(1) and rid.group(1) not in part_used:
                t = tgt.group(1).decode().lstrip('/')
                drop_media.add(t if t.startswith('word/') else 'word/' + t)
                return b''
            return tag
        rels = _re.sub(rb'<Relationship\b[^>]*/>', _filter, rels)
        data[n] = rels
    if not drop_media:
        return
    with _zf.ZipFile(tmp, 'w', _zf.ZIP_DEFLATED) as z:
        for n in names:
            if n in drop_media:
                continue
            z.writestr(n, data[n])
    _sh.move(tmp, path)
    print('  stripped %d orphan media' % len(drop_media))


def font_sweep(doc, cover_tbl):
    for name, east, asc, size, bold in [
            ('Normal', '宋体', 'Times New Roman', Pt(12), None),
            (STYLE_H2, '黑体', 'Times New Roman', Pt(14), True),
            (STYLE_H3, '黑体', 'Times New Roman', Pt(12), True)]:
        try:
            st = doc.styles[name]
        except KeyError:
            continue
        f = st.font
        f.name = asc
        f.size = size
        if bold is not None:
            f.bold = bold
        rf = st.element.get_or_add_rPr().get_or_add_rFonts()
        rf.set(qn('w:ascii'), asc)
        rf.set(qn('w:hAnsi'), asc)
        rf.set(qn('w:eastAsia'), east)

    def sweep_runs(runs):
        for r in runs:
            rf = r.font.element.get_or_add_rPr().get_or_add_rFonts()
            if rf.get(qn('w:ascii')) == 'Consolas':
                rf.set(qn('w:eastAsia'), '宋体')
                continue
            rf.set(qn('w:ascii'), 'Times New Roman')
            rf.set(qn('w:hAnsi'), 'Times New Roman')
            rf.set(qn('w:eastAsia'), '宋体')

    for p in doc.paragraphs:
        sweep_runs(p.runs)
    for t in doc.tables:
        if t._tbl is cover_tbl._tbl:
            continue
        for row in t.rows:
            for c in row.cells:
                for p in c.paragraphs:
                    sweep_runs(p.runs)


def _new_p(doc, text, style):
    from docx.text.paragraph import Paragraph
    p = Paragraph(OxmlElement('w:p'), doc)
    p.style = doc.styles[style]
    if text:
        p.add_run(text)
    return p


if __name__ == '__main__':
    build(sys.argv[1])
