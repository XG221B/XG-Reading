# XG-Reading

[中文](README.md) | [English](README_EN.md)

XG-Reading是一个面向生命科学论文的深度精读Skill。它以论文图表、实验设计和证据强度为核心，把分散在主文、图注、Methods和Supplementary Information中的信息重建为一条可以检查的论证链，并生成结构统一的中文Word文档。

它不绑定Codex或任何特定agent客户端：任何具备读取文本与图像、执行本地命令、写入指定目录能力的agent，都可以读取同一份`SKILL.md`并运行同一套脚本。Codex的`$xg-reading`只是可选接入之一。

<p align="center">
  <img src="docs/overview.png" width="48%" alt="XG-Reading evidence-chain overview" />
  <img src="docs/figure-reading.png" width="48%" alt="XG-Reading figure-level reading" />
</p>

> 上图来自虚构研究与合成数据，只用于展示输出结构，不对应任何真实论文。

## 核心思路

读懂论文不只是知道作者得出了什么结论，还要知道：

- 结论由哪一张Figure、哪个panel或哪一张Table支持；
- 实验真正测量了什么，作者又进一步推断了什么；
- 对照、重复、统计和补充材料是否足以支撑该推断；
- 相邻图表如何从现象推进到因果、机制或转化结论；
- 哪些结论证据较强，哪些仍然存在替代解释。

主图从PDF文字坐标中单独提取，保留完整图注，并在下一段正文开始前结束裁剪，避免固定截图范围带入无关正文。

XG-Reading先建立论文专属的claim-to-evidence map，再逐图写作，因此不会把图表解读退化成图注翻译。

## 通用，但不牺牲深度

项目使用一套共享的证据判断骨架，同时针对不同生命科学研究调用不同的专业模块：

- 分子与细胞机制；
- 组学、单细胞与计算生物学；
- 免疫学、微生物学与感染；
- 结构生物学与方法开发；
- 生物材料、药物递送、动物研究与临床转化；
- 微纳机器人与主动递送（驱动、导航、载药释放、靶向与体内验证）。

每次阅读只选择一个主模块，必要时叠加一个次模块。这样既能适应不同论文，又不会用一套浅层问题清单平均化所有研究。

## 输出内容

生成的Word文档通常包括：

1. 材料体系与设计思路：材料/组分及各自作用的两列表格、用文章原图呈现的结合结构，以及2-3句设计思路概括；
2. 领域问题、研究缺口和本文贡献；
3. 整篇论文的图表逻辑链；
4. 每张主图的中文译名、逐panel译名与解读；
5. 补充材料对主结论的支持；
6. 可选的“未来展望”：仅整理作者在Discussion、Conclusion或明确的Future work中讨论过的局限、未解决问题或后续方向；若论文没有这类原文依据，则不生成该栏目。

文档采用固定的中文学术阅读版式，并在生成后执行结构审计和逐页渲染检查。

章节级标题与`Figure X：<中文图题>`居中显示；`Step`与panel译名等段内阅读引子保持左对齐。每张主图或主表的解读均从新页开始，便于逐图审阅和批注。

## 通用使用（不绑定Codex）

不安装到任何agent目录也可以直接使用。最小能力要求是：能读取文本与图像、执行本地命令、写入用户指定的输出目录，并能基于原文推理。纯文本聊天界面或无法访问本地文件的云端agent不能直接运行，需要先获得相应工具或同步工作区。

取用方式有两种：

1. 克隆整个仓库（保留仓库默认输出行为）：

   ```powershell
   git clone https://github.com/XG221B/XG-Reading.git
   cd XG-Reading
   python -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. 只复制`skill/xg-reading/`文件夹到任意位置，不需要原仓库。该文件夹自带完整的依赖声明，安装依赖时使用文件夹内的`requirements.txt`。

依赖为python-docx、Pillow、pypdfium2，需要Python 3.11+。可复用已有虚拟环境（本机验证使用Python 3.13）。下文用`<PYTHON>`指代已装依赖的解释器，`<skill目录>`指包含`SKILL.md`与`run.py`的目录。

安装依赖后先做只读环境诊断：

```powershell
<PYTHON> <skill目录>/run.py doctor
```

`doctor`输出JSON：Python版本、skill目录、解析出的仓库根与输出根、依赖版本、模板SHA-256校验、渲染器、字体以及errors/warnings。它只说明工具可用，不等于整篇论文已通过验收。默认把缺少渲染器记为warning；加`--require-renderer`才记为error。

渲染检查需要可用的DOCX渲染器：优先`XG_READING_SOFFICE`环境变量指定的LibreOffice可执行文件，其次PATH中的`soffice`/`libreoffice`，再查Windows、macOS、Linux常见安装位置，Windows上还可回退到Word COM（需要PowerShell）；都缺失时`render`明确报错。缺少指定的华文中宋、Times New Roman字体时，不得静默替换字体后宣称格式验收通过。

初始化论文工作区有两种输出根模式：

```powershell
# 仓库模式：默认写入<仓库根>\outputs\<年份>-<文章标题>\
<PYTHON> <skill目录>/run.py workspace init --paper <论文.pdf> --title "<年份>-<文章标题>"

# 独立模式：写入任意普通项目目录，不要求是Git仓库
<PYTHON> <skill目录>/run.py workspace init --paper <论文.pdf> --title "<年份>-<文章标题>" --output-root <输出目录>
```

`--repository-root <仓库根>`与`--output-root <目录>`互斥；给`--repository-root`时产物进入`<仓库根>/outputs/`。未显式指定时，依次读取环境变量`XG_READING_OUTPUT_ROOT`（必须是绝对路径）、skill同目录`xg-reading.local.json`中的`output_root`（相对路径相对该配置文件）、同一配置的`repository_root`，再从skill位置向上发现仓库；全部失败时报错，绝不写入skill安装目录。完整解析顺序与manifest字段见[skill/xg-reading/references/workspace-layout.md](skill/xg-reading/references/workspace-layout.md)。

独立复制的skill如果既不在XG-Reading仓库内、也没有本地配置，`doctor`会因为无法解析输出根而报错；此时给它`--output-root <输出目录>`，或先写好`xg-reading.local.json`。`workspace init`同样处理。

`run.py`命令一览：

| 命令 | 作用 |
|---|---|
| `doctor` | 只读环境诊断，输出JSON |
| `workspace init` | 创建或复用单篇论文工作区，输出manifest JSON |
| `workspace resolve-root` | 只解析输出根，不创建目录 |
| `extract` | 批量提取主图 |
| `preflight` | 构建前预检content.json |
| `build` | 生成DOCX |
| `audit` | 结构审计 |
| `render` | 渲染逐页检查图（带缓存） |

`run.py`只做分发，透传参数与退出码；原有`scripts/*.py`脚本仍可直接运行。脚本只负责确定性处理，阅读、判断和content.json写作仍由agent完成，`run.py`不是自动解读引擎。

已验证范围：当前只在Windows 11 + Python 3.13（本机虚拟环境）上验证过；含材料体系段的合成素材完整链路（preflight→build→audit→render）已跑通，通过Word COM完成DOCX→PDF与逐页PNG，3页逐页检查通过；此前无材料段的2页样例亦通过。LibreOffice路径未实测（本机未安装）。其他操作系统、其他Python版本、其他agent客户端均未验证；Codex之外平台的skill自动发现机制未验证，未验证的客户端应按“显式读取指定路径的`SKILL.md`并运行其脚本”的方式使用。

## 可选安装到Codex

安装到Codex的Skill目录只是可选步骤。下载或克隆仓库后，在仓库根目录执行：

```powershell
.\install.ps1
```

默认安装方式会在个人Codex Skill目录创建一个指向本仓库`skill/xg-reading`的目录链接，默认目标是`$HOME\.codex\skills\xg-reading`，可用`-TargetSkillDir <目录>`指定其他目标。这样Skill的规则、脚本与仓库始终同步，论文产出也会自动回到仓库根目录的`outputs/`。已有同名Skill时，先备份本地修改，再显式运行：

```powershell
.\install.ps1 -ReplaceExisting
```

若不能使用目录链接，可复制安装并写入本地仓库路径配置：

```powershell
.\install.ps1 -Mode Copy -ReplaceExisting
```

复制模式会在目标目录写入`xg-reading.local.json`，其中`repository_root`指向本仓库，因此产物仍写回仓库`outputs/`。安装脚本会打印安装目标与默认outputs位置。该脚本为PowerShell实现，主要在Windows上使用；其他平台的安装方式与skill自动发现均未验证。

`outputs/`是本地工作区，不会被Git提交。每篇论文在其中拥有独立的「年份-文章标题」文件夹（例如`2023-Autonomous metal-organic framework nanorobots for active mitochondria-targeted cancer therapy`），最终Word位于顶层，裁图、内容JSON、图片身份清单、渲染页和审计报告位于`process/`。原始PDF、补充材料和视频不会被复制，来源路径和SHA-256会记录在`source-manifest.json`。独立使用时，产出位于`--output-root`指定的目录，文件夹结构相同。

重新打开Codex后可显式调用：

```text
Use $xg-reading to deeply read this life-science paper and create a Chinese Word reader.
```

也可以直接使用中文：

```text
请结合主文和补充材料逐图精读这篇论文，梳理论证链、证据强度，以及作者明确讨论过的未来方向，并生成Word文档。
```

## 建议输入

- 主文PDF；
- Supplementary Information；
- Supplementary Movies或可访问的视频文件；
- 用户希望重点理解的问题。

缺少关键材料时，Skill应明确标注证据缺口，而不是根据领域常识补写不存在的数据。

## 准确性说明

XG-Reading用于辅助科研阅读，不替代原始论文、同行评议或研究者本人的判断。AI生成内容可能存在遗漏、误读或结论强度不当。涉及实验条件、样本量、统计方法、机制、疗效和安全性的判断，必须回到原文、完整图注、Methods、Supplementary Information及原始数据核查。

## Repository status

当前仓库尚未选择开源许可证。在没有许可证的情况下，默认保留相关权利。后续如需允许他人复制、修改或分发，可再选择合适的软件许可证。

## English README

See [README_EN.md](README_EN.md). The Skill continues to generate Chinese DOCX readers; the English README only documents the project for English-speaking readers.
