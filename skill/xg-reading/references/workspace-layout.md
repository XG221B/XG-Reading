# 本地论文工作区

所有持久化产出必须位于解析出的输出根下的`<年份>-<文章标题>/`，不能写入 skill 安装目录、桌面根目录或系统临时目录。输出根不要求是 Git 仓库，普通项目目录即可。以下命令中的`$PYTHON`指已安装依赖的 Python 3.11+ 解释器，`<skill-dir>`指包含`SKILL.md`与`run.py`的 skill 目录。

## 初始化工作区

在任何论文任务开始前运行：

```powershell
& $PYTHON <skill-dir>/run.py workspace init --paper <main.pdf> --title "<年份>-<文章标题>" [--supplement <file> ...] [--movie <file> ...] [--repository-root <仓库根> | --output-root <输出目录>]
```

`--title`省略时取 PDF 文件名，建议始终传入`<年份>-<文章标题>`。`--repository-root`与`--output-root`互斥，同时给出会报错。脚本成功后输出的 JSON manifest 是该任务所有路径的唯一来源；失败时 stdout 输出`{"ok": false, "error": "..."}`并以非零退出码结束。

```text
<outputs-root>/<paper-title>/
  <paper-title>论文逐图解读.docx
  process/
    source-manifest.json
    content.json
    image-manifest.json
    figures/
    supplementary/
    movie-frames/
    rendered/
    audit-report.json
```

原始主文、补充材料和视频不复制，只在`source-manifest.json`中记录绝对路径、SHA-256和发现状态。图像裁图与对应的`.crop.json`进入`process/figures/`；补图和视频代表帧分别进入`process/supplementary/`和`process/movie-frames/`；渲染PDF和逐页PNG进入`process/rendered/`。构建还会在`process/image-manifest.json`记录正文图片出现顺序、源图哈希、补图成员与嵌入字节哈希，审计据此核对图片身份；缺失该文件只给 warning（旧文档或外部构建）。

## 输出根解析

`run.py workspace init`与`run.py workspace resolve-root`按以下优先级解析输出根（实现见`scripts/reader_workspace.py`）：

1. 显式`--output-root <普通项目目录>`：产物写入`<项目目录>/<年份>-<文章标题>/`，目标目录不需要`.git`或特定仓库树形。或显式`--repository-root <XG-Reading 仓库根>`：产物写入`<仓库根>/outputs/<年份>-<文章标题>/`；该目录必须能被识别为 XG-Reading 仓库根（含`skill/xg-reading/SKILL.md`，且有`.git`或`README.md`），否则报错。两者互斥，同时给出直接报错。
2. 环境变量`XG_READING_OUTPUT_ROOT`：必须是绝对路径，相对路径会报错，避免随当前工作目录漂移。
3. skill 同目录`xg-reading.local.json`中的`output_root`：相对路径相对该配置文件所在目录解析，不随命令的当前工作目录变化。
4. 同一配置文件的`repository_root`：产物写入`<仓库根>/outputs/<年份>-<文章标题>/`。
5. 从 skill 所在位置向上自动发现带`skill/xg-reading/SKILL.md`与`.git`或`README.md`的 XG-Reading 仓库根。
6. 以上都不满足时报告错误，绝不回退到 skill 安装目录。

显式选项与环境变量优先于本地配置，可以覆盖已失效的旧配置；没有显式覆盖时，指向不存在目录的配置会明确报错，而不是悄悄把产物写到其他位置。输出根本身必须位于 skill 目录之外。配置文件接受 UTF-8 与 UTF-8 BOM，内容必须是 JSON 对象。

解析结果与命令的当前工作目录无关；脚本只以 skill 目录、配置文件位置和显式路径为依据，产物不会随 cwd 漂移。

只查路径、不创建任何目录：

```powershell
& $PYTHON <skill-dir>/run.py workspace resolve-root [--repository-root <仓库根> | --output-root <输出目录>]
```

`resolve-root`输出`repository_root`（独立输出根模式下为`null`）与`outputs_root`，不创建目录。`init`才会创建目录并输出完整 manifest。

## manifest 字段与工作区身份

`process/source-manifest.json`当前为`schema_version: 2`；旧 v1 manifest 仍可读取，重复`init`后升级为 v2：

- `schema_version`：当前为`2`，只允许兼容性新增字段。
- `paper_identity`：首次`init`时主文的 SHA-256，作为工作区稳定身份；之后的`init`保留该值。
- `source_revision`：当前主文的 SHA-256。
- `source_changes`：`{added, removed, relocated, changed}` 四个数组，记录相对上次`init`的来源变化；每条含`role`与`path`，`relocated`额外记录`from`/`to`。
- `stale`：布尔值；`added`、`removed`、`changed`任一非空时为`true`。
- `stale_reasons`：字符串数组，逐条说明过期原因。
- `repository_root`、`outputs_root`、`paper_title`、`created_at`、`updated_at`、`workspace`、`sources`：路径与来源记录，含义同前。

重复`init`时若未传`--supplement`/`--movie`，保留上次已登记的补充材料与视频；显式传入某角色的文件时替换该角色的登记。路径移动但内容 SHA-256 不变记为`relocated`，不置`stale`；内容变化、已登记来源消失或新增来源会置`stale=true`，并在 stderr 列出原因。过期工作区不会删除旧裁图、content、DOCX 或渲染页，但这些产物不得当作当前成功结果。

`init`读取旧 manifest 时兼容 v1；标题冲突（已有 manifest 的`paper_title`与本次`--title`大小写不敏感不一致）或目标目录非空但没有`process/source-manifest.json`时，明确报错，不覆盖未受管文件。manifest 通过临时文件原子写入，并在`<paper-dir>/.workspace.lock`上加锁；锁在正常结束后释放，记录的所有者已退出时可回收。

## 配置示例

独立使用、把产物写入普通项目目录时，在 skill 目录的`xg-reading.local.json`中写：

```json
{
  "output_root": "D:/ResearchNotes/paper-readers"
}
```

仓库模式保持：

```json
{
  "repository_root": "C:/path/to/XG-Reading"
}
```

参考`xg-reading.local.example.json`。该本地配置文件被 Git 忽略，不随仓库分发。
