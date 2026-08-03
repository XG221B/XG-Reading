# AGENTS.md

本文件是 XG-Reading 仓库对 AI 助手（opencode / Codex 等）的全局约定。执行本仓库内任何任务前，先完整阅读本文件。

## 硬性规则（除非用户给出明确指令，否则不可违反）

### Word 文档格式保护（最高优先级）

不得修改任何影响 Word 输出外观的设定，包括但不限于：

- 字体：中文「华文中宋」、英文/数字「Times New Roman」及其在样式/run 上的绑定
- 字号、加粗、颜色（正文黑字）
- 行距（1.25 等）、段前段后间距、首行缩进（0.74 cm 等）
- 对齐方式（章节标题与 `Figure X：<中文图题>` 居中、`Step` 与 panel 标题左对齐、正文两端对齐等）
- 页边距与页面尺寸（21.59 × 27.94 cm 等）
- 分页规则（每张主图/主表从新页开始、keep_with_next、widow_control、panel 间 0.2 行空白间隔等）
- 自定义样式定义（FER Title / FER Metadata / FER Section / FER Step / FER Body / FER Figure / FER Figure Translation / FER Supplement / FER Picture / FER Bullet）
- `assets/reference.docx` 模板文件
- `references/style-contract.md`、`references/template-contract.md` 中的排版契约

当格式要求与速度/工具优化冲突时，一律优先保证格式不变。

### 其他硬性规则

- 不得修改 `references/content-schema.md` 定义的 content.json 结构契约（兼容性新增除外）。
- 渲染检查页必须使用 `scripts/render_reader_docx.py`（带 sha256 缓存），禁止手动全量重转 PDF。
- 提取图表默认使用 `scripts/extract_figures_batch.py`（进程级并行，禁止自行用线程并发渲染 PDFium）。
- 论文输出目录命名约定：`outputs/<年份>-<文章标题>`，如 `outputs/2023-Autonomous metal-organic framework nanorobots for active mitochondria-targeted cancer therapy`。
- 所有产出写入仓库 `outputs/`，禁止写入 skill 安装目录或系统临时目录。

## 运行环境

- 脚本运行时：仓库根目录 `.venv\Scripts\python.exe`。若不存在：
  `python -m venv .venv`，然后 `.venv\Scripts\python.exe -m pip install -r requirements.txt`
- 依赖：python-docx、Pillow、pypdfium2（见 `requirements.txt`）。

## 常用命令（均在仓库根目录执行）

```powershell
# 1. 初始化工作区（--title 用「年份-文章标题」格式）
& .venv\Scripts\python.exe skill\xg-reading\scripts\reader_workspace.py init --paper <论文.pdf> --title "<年份>-<文章标题>"

# 2. 批量提取主图（每图一个 --fig，格式 <标签>:<页码>[:<输出文件名>]）
& .venv\Scripts\python.exe skill\xg-reading\scripts\extract_figures_batch.py --pdf <论文.pdf> --outdir <paper>\process\figures --fig "Fig. 1:2:Fig1.png" --fig "Fig. 2:3:Fig2.png" ...

# 3. 构建 DOCX
& .venv\Scripts\python.exe skill\xg-reading\scripts\build_reader_docx.py --content <paper>\process\content.json --output "<paper>\<年份>-<标题>论文逐图解读.docx" --work-dir <paper>\process\supplementary

# 4. 审计
& .venv\Scripts\python.exe skill\xg-reading\scripts\audit_reader_docx.py --docx "<paper>\<年份>-<标题>论文逐图解读.docx" --content <paper>\process\content.json --json-report <paper>\process\audit-report.json

# 5. 渲染检查页（带缓存，未修改的 DOCX 会直接命中缓存）
& .venv\Scripts\python.exe skill\xg-reading\scripts\render_reader_docx.py --docx "<paper>\<年份>-<标题>论文逐图解读.docx" --work-dir <paper>\process\rendered
```

## 已知坑（Windows 环境）

- PowerShell 5.1 向原生程序传中文路径参数会损坏编码；一律在 Python 脚本内部处理中文路径，不要在 PowerShell 命令行直接拼接中文路径。
- PDFium 在本机多线程并发渲染会崩溃（退出码 0xC0000134 / 0x80000003）；不要自己写多线程渲染。
- 同一篇论文二次解读时，先核对 `process/source-manifest.json` 中源文件的 sha256 未变化，再决定是否复用 `process/` 下的中间产物。
