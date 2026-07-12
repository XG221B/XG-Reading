# 本地论文工作区

所有持久化产出必须位于下载或克隆的`XG-Reading`仓库根目录的`outputs/`下，不能写入`.codex/skills`、桌面根目录或系统临时目录。

在任何论文任务开始前运行：

```powershell
& $PYTHON_BIN scripts/reader_workspace.py init --paper <main.pdf> --title <stable-paper-title>
```

可选地追加`--supplement <file>`和`--movie <file>`。脚本输出的JSON是该任务所有路径的唯一来源：

```text
outputs/<paper-title>/
  <paper-title>论文逐图解读.docx
  process/
    source-manifest.json
    content.json
    figures/
    supplementary/
    movie-frames/
    rendered/
    audit-report.json
```

原始主文、补充材料和视频不复制，只在`source-manifest.json`中记录绝对路径、SHA-256和发现状态。图像裁图与对应的`.crop.json`进入`process/figures/`；补图和视频代表帧分别进入`process/supplementary/`和`process/movie-frames/`；渲染PDF和逐页PNG进入`process/rendered/`。

输出根目录解析顺序：本地`xg-reading.local.json`配置、Skill路径上方的XG-Reading仓库根目录、命令行`--repository-root`。若无法解析，停止并要求配置路径，绝不将产物写进安装目录。
