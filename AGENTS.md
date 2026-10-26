# AGENTS.md

本文件是 XG-Reading 仓库对 AI 助手（opencode / Codex / Claude Code 等任意具备读取文件与图像、执行本地命令、写入指定目录能力的 agent）的全局约定。执行本仓库内任何任务前，先完整阅读本文件。

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

### 内容与格式冻结

- 除用户单独明确要求外，任何改动都绝对不允许修改任何与内容有关的东西：解读质量标准、文档格式（字体、字号、颜色、行距、缩进、对齐、分页、样式定义）、排版契约、模板资产、图题与段落措辞规范一律冻结。
- 纯技术维护（脚本、缓存、测试、工作区文档）同样受此约束：不得以任何方式改变 DOCX 输出外观或 content.json 的解释规则。

### 其他硬性规则

- 不得修改 `references/content-schema.md` 定义的 content.json 结构契约（兼容性新增除外）。
- 渲染检查页必须使用 `run.py render`（分发到 `scripts/render_reader_docx.py`，带 sha256 缓存），禁止手动全量重转 PDF。
- 提取图表默认使用 `run.py extract`（分发到 `scripts/extract_figures_batch.py`，进程级并行，禁止自行用线程并发渲染 PDFium）；原脚本仍可直接运行。
- 构建前用 `run.py preflight --content <process/content.json>` 预检 content.json；预检覆盖证据标签/panel 一致性与覆盖信号，但不建立来源 inventory，不能据此宣称所有来源 panel 已核对。
- 工作区 manifest 当前为 `schema_version: 2`：重复 `init` 未传 `--supplement`/`--movie` 时保留已登记来源；来源新增、删除或内容变化会置 `stale=true` 并打印 stderr 警告。旧裁图、DOCX 与渲染页不删除，但不得当作当前成功产物。
- 构建在 `process/image-manifest.json` 记录图片出现顺序、源图哈希、补图成员与嵌入字节哈希；`audit` 据此核对图片身份，缺失该文件仅 warning（旧文档或外部构建）。
- `limitations`/`trends` 仍可构建，但 preflight/audit 会 warning（未核对作者 Discussion/Conclusion）；新任务使用 `future_outlook` 并给出来源位置。
- 论文输出目录命名约定：`outputs/<年份>-<文章标题>`，如 `outputs/2023-Autonomous metal-organic framework nanorobots for active mitochondria-targeted cancer therapy`。
- 默认所有产出写入仓库 `outputs/`；单独复制 skill 使用时，用 `--output-root <目录>` 或 `XG_READING_OUTPUT_ROOT`（绝对路径）显式指定输出根。禁止写入 skill 安装目录或系统临时目录。

## 运行环境

- Python 3.11+。依赖 python-docx、Pillow、pypdfium2：skill 自带完整声明 `skill/xg-reading/requirements.txt`，根 `requirements.txt` 以 `-r skill/xg-reading/requirements.txt` 引用。
- 可使用任意已装依赖的 Python 3.11+ 解释器（本机验证使用 Python 3.13 虚拟环境）。也可在仓库根目录新建 `.venv`：
  `python -m venv .venv`，然后 `.venv\Scripts\python.exe -m pip install -r requirements.txt`
- 统一入口：`<PYTHON> skill\xg-reading\run.py <command> [args]`，command ∈ doctor、workspace、extract、preflight、build、audit、render。`run.py` 只负责分发并透传参数与退出码；原有 `scripts\*.py` 仍可直接运行。下文 `$PYTHON` 指选定的解释器。
- 渲染检查需要可用的 DOCX 渲染器：按 `XG_READING_SOFFICE` 环境变量 → PATH 中的 `soffice`/`libreoffice` → Windows/macOS/Linux 常见安装位置 → Windows 上 Word COM（需要 PowerShell）的顺序查找；都缺失时明确报错。缺少指定的华文中宋、Times New Roman 字体时，不得静默替换字体后宣称格式验收通过。本机实测 Word COM 渲染通过：含材料体系段的合成素材 3 页检查通过，此前无材料段 2 页样例亦通过；LibreOffice 未实测（本机未安装）。

## 常用命令

以下命令在仓库根目录执行；`run.py` 按 skill 目录解析资源，不依赖当前工作目录。

```powershell
# 0. 环境诊断（只读，输出 JSON；默认把缺少渲染器记为 warning，加 --require-renderer 才记为 error）
& $PYTHON skill\xg-reading\run.py doctor

# 1. 初始化工作区（--title 用「年份-文章标题」格式；默认写入仓库 outputs/；单独复制 skill 时用 --output-root <目录>；重复 init 未传补充/视频时保留已登记来源，源变化会置 stale 并告警，旧产物保留）
& $PYTHON skill\xg-reading\run.py workspace init --paper <论文.pdf> --title "<年份>-<文章标题>"

# 2. 批量提取主图（每图一个 --fig，格式 <标签>:<页码>[:<输出文件名>][:<顶边界pt>]；crop 缓存校验 schema 与输出 PNG 哈希，--no-cache 强制重提）
& $PYTHON skill\xg-reading\run.py extract --pdf <论文.pdf> --outdir <paper>\process\figures --fig "Fig. 1:2:Fig1.png" --fig "Fig. 2:3:Fig2.png:120" ...

# 3. 预检 content.json（构建前先跑，尽早暴露契约错误）
& $PYTHON skill\xg-reading\run.py preflight --content <paper>\process\content.json

# 4. 构建 DOCX
& $PYTHON skill\xg-reading\run.py build --content <paper>\process\content.json --output "<paper>\<年份>-<标题>论文逐图解读.docx" --work-dir <paper>\process\supplementary

# 5. 审计
& $PYTHON skill\xg-reading\run.py audit --docx "<paper>\<年份>-<标题>论文逐图解读.docx" --content <paper>\process\content.json --json-report <paper>\process\audit-report.json

# 6. 渲染检查页（带缓存；命中前校验 PDF/页哈希与引擎签名，重渲染打印 changed/unchanged/added/removed）
& $PYTHON skill\xg-reading\run.py render --docx "<paper>\<年份>-<标题>论文逐图解读.docx" --work-dir <paper>\process\rendered

# 7. 运行脚本测试（requirements-dev.txt 提供 pytest）
& $PYTHON -m pytest tests -q
```

## 已知坑（Windows 环境）

- PowerShell 5.1 向原生程序传中文路径参数会损坏编码；一律在 Python 脚本内部处理中文路径，不要在 PowerShell 命令行直接拼接中文路径。
- PDFium 在本机多线程并发渲染会崩溃（退出码 0xC0000134 / 0x80000003）；不要自己写多线程渲染。
- 同一篇论文二次解读时，重复 `init` 会自动对比 `process/source-manifest.json` 中已登记来源的 sha256；新增、删除或内容变化会把工作区置为 `stale=true` 并在 stderr 警告。确认无变化后再复用 `process/` 下的中间产物；过期工作区不删除旧 DOCX，但旧 DOCX 不得当作当前成功产物。
