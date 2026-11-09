# report_skeleton — 模板重写型报告骨架

政企复测双报告战役沉淀。适用场景：客户给了定版 docx 模板（封面表+自动目录+逐洞七段式+附录A评级表），要按模板整体重写生成同族报告。

## 用法

```
python build_report.py <内容模块名>     # 内容模块参照 content_TEMPLATE.py
```

基座模板路径由 argv[2] 传入（内容模块参照 content_TEMPLATE.py 的 COVER 锚点说明）；锚点（"一、漏洞概况"起始、"附录A 安全等级评定"终止）按模板文字适配。

## 骨架已内置（别再踩）

1. **封面三段式改写**：标题/公司/日期是三个独立段落，逐段匹配改写（日期段单独匹配 `\d{4}年\d+月\d+日`）。
2. **outlineLvl 探针注入**：模板老标题是 pPr 直设 outlineLvl，新标题必须复制同 val，否则 TOC 重建抓不到。
3. **孤儿媒体剥离**：删旧正文后模板旧图仍留在包里，strip_orphan_media 重打包剥掉。
4. **updateFields**：settings.xml 设 true。
5. **docProps 清空**：author/lastModifiedBy 等。
6. **图片定标**：宽≤5.5in 且高≤4.3in（探模板基线），图段落 keep_with_next；渲染前 raw 截断（请求≤24行/响应≤20行/单行≤180字符+截断标记）。
7. **字体清扫 font_sweep**：正文宋体12pt+TNR、标题黑体、HTTP 块 Consolas 10.5pt（客户点名口径；模板自带字体客户未提异议时以模板为准）。
8. **分页**：h2 与 h3 全部 pageBreakBefore（**schema 顺序 insert_element_before，放 outlineLvl 后=Word 不稳定**），但紧跟 h2 的首个 h3 不换页（比较用样式全名）。
9. **页脚 PAGE 域页码**：sections[0].footer，宋体9pt居中。
10. **目录 sdt 后模板空段全删**：概况顶格起。
11. **概况布局**：段落→漏洞清单表→"测试对象为…"描述段→对象表（两表不贴脸）。

## 交付后用户改了文件（立法）

用户在 Word 里编辑过交付 docx 后，**只做手术不做重建**：python-docx 打开其文件做 run/段落级增删替换（标签加粗=剥前段字符+插 bold run 至 pPr 后；跨 run 替换整段重写兜底），改完 Word COM 更新 TOC 再清 docProps。手术前先 diff 段落+表格两层；手术后查概况计数/交叉引用/图号/章节号一致性。

## build 之后必跑（skill 铁律，不在骨架内自动跑）

- Word COM 一进程一文档：`TablesOfContents.Update()+Fields.Update()` 重存 docx（缓存目录写进包），再清一次 docProps（COM 回写 lastModifiedBy）。
- 渲染目检：COM 存 PDF → PyMuPDF 逐页 PNG → 目检目录页/封面/报文截图页。
- ai_taste_check.py 全绿。

## 配套截图工具

- 白底 PoC 报文图（客户交付默认）：`tools/white_shot/render.py`
- 档案证据白底展示（pretty JSON 节选+高亮/表格化）：参照 `当轮 workspace 的 make_art_shots 系脚本`、`同系脚本`
