# XG-Reading

[中文](README.md) | [English](README_EN.md)

XG-Reading is a portable Skill for deep reading of life-science papers. It treats figures, experimental design, and evidence strength as the backbone of reading, reconstructing the claim-to-evidence chain across the main text, captions, Methods, and Supplementary Information into a consistent Chinese Word document.

It is not tied to Codex or any specific agent client: any agent that can read text and images, execute local commands, and write to a specified directory can read the same `SKILL.md` and run the same scripts. Codex's `$xg-reading` is only one optional integration.

<p align="center">
  <img src="docs/overview.png" width="48%" alt="XG-Reading evidence-chain overview" />
  <img src="docs/figure-reading.png" width="48%" alt="XG-Reading figure-level reading" />
</p>

> The images above use fictional studies and synthetic data. They demonstrate the output structure only and do not represent a real publication.

## Core Approach

Reading a paper means more than knowing its conclusion. XG-Reading asks:

- Which Figure, panel, or Table supports each conclusion?
- What did the experiment measure, and what did the authors infer from it?
- Do controls, replicates, statistics, and supplementary materials support that inference?
- How do adjacent figures move the story from observation to mechanism or translation?
- Which conclusions have strong evidence, and where do alternative explanations remain?

Main figures are extracted from PDF text coordinates one by one. Each crop preserves the complete figure caption and stops before the following Results or Discussion paragraph. The Skill builds a paper-specific claim-to-evidence map before drafting, so figure reading does not collapse into caption translation.

## Broad, Without Becoming Generic

XG-Reading uses a shared evidence framework while routing each paper to an appropriate life-science module:

- molecular and cellular mechanisms;
- omics, single-cell, and computational biology;
- immunology, microbiology, and infection;
- structural biology and methods;
- biomaterials, drug delivery, animal studies, and clinical translation;
- micro/nano robotics and active delivery (actuation, navigation, cargo release, targeting, and in vivo validation).

Each paper uses one primary module and, only where truly needed, one secondary module. This preserves domain depth instead of applying a shallow universal checklist to every study.

## Output

The generated Chinese Word document usually includes:

1. the material system and design rationale: a two-column table of materials/components and their roles, the assembled structure shown with the paper's original figure, and a two- to three-sentence design summary;
2. field positioning, the research gap, and the paper's contribution;
3. the full figure/table logic chain;
4. translated main-figure and panel titles followed by panel-level interpretation;
5. supplementary evidence placed beside the main claim it supports;
6. an optional **Future Outlook** section, limited to limitations, open questions, or next directions explicitly discussed by the authors in the Discussion, Conclusion, or stated future work. When the paper provides no such source-grounded discussion, this section is omitted.

The Word output follows a fixed Chinese academic layout and is structurally audited and rendered page by page after generation. Chapter-level headings are centered; in-paragraph reading prompts remain left aligned. Every main Figure or Table starts on a new page for review and annotation.

## General Use (Not Tied to Codex)

No installation into an agent's skill directory is required. The minimum capabilities are: reading text and images, executing local commands, writing to a user-specified output directory, and reasoning from the source paper. A text-only chat interface or a cloud agent without local file access cannot run this skill until it gains those tools or a synced workspace.

There are two ways to use it:

1. Clone the whole repository (preserves the default repository output behavior):

   ```powershell
   git clone https://github.com/XG221B/XG-Reading.git
   cd XG-Reading
   python -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. Copy only `skill/xg-reading/` to any location; the original repository is not required. The folder carries its own complete dependency declaration, so install dependencies from its `requirements.txt`.

Dependencies are python-docx, Pillow, and pypdfium2; Python 3.11+ is required. An existing virtual environment can be reused (verified here with Python 3.13). Below, `<PYTHON>` means the dependency-installed interpreter and `<skill-dir>` the folder containing `SKILL.md` and `run.py`.

Run the read-only environment diagnosis first:

```powershell
<PYTHON> <skill-dir>/run.py doctor
```

`doctor` prints JSON: Python version, skill directory, resolved repository and output roots, dependency versions, template SHA-256 check, renderer, fonts, and errors/warnings. It only shows that the tools are available; it does not mean a paper has passed acceptance. A missing renderer is a warning by default and an error with `--require-renderer`.

Rendering needs a working DOCX renderer: first the LibreOffice executable named by `XG_READING_SOFFICE`, then `soffice`/`libreoffice` on `PATH`, then common Windows/macOS/Linux install locations, with Word COM on Windows (requires PowerShell) as a fallback; when none is available, `render` reports a clear error. If the required 华文中宋 or Times New Roman font is missing, never silently substitute fonts and then claim the format passed acceptance.

`workspace init` supports two output-root modes:

```powershell
# Repository mode: defaults to <repository-root>\outputs\<year>-<title>\
<PYTHON> <skill-dir>/run.py workspace init --paper <paper.pdf> --title "<year>-<title>"

# Standalone mode: any ordinary project directory; no Git repository required
<PYTHON> <skill-dir>/run.py workspace init --paper <paper.pdf> --title "<year>-<title>" --output-root <output-dir>
```

`--repository-root <repository>` and `--output-root <directory>` are mutually exclusive; with `--repository-root`, artifacts go to `<repository>/outputs/`. Without either option, resolution reads the `XG_READING_OUTPUT_ROOT` environment variable (must be absolute), then `output_root` in `xg-reading.local.json` beside `SKILL.md` (relative paths are anchored to that config file), then `repository_root` in the same config, then walks upward from the skill location to discover the repository; if all fail it reports an error and never falls back to the skill installation directory. See [skill/xg-reading/references/workspace-layout.md](skill/xg-reading/references/workspace-layout.md) for the full order and manifest fields.

A standalone skill copy that is neither inside an XG-Reading repository nor configured locally cannot resolve an output root, so `doctor` reports that error; pass `--output-root <output-dir>` or create `xg-reading.local.json` first. `workspace init` follows the same resolution.

`run.py` commands:

| Command | Purpose |
|---|---|
| `doctor` | Read-only environment diagnosis as JSON |
| `workspace init` | Create or reuse a per-paper workspace; prints the manifest JSON |
| `workspace resolve-root` | Resolve the output root without creating directories |
| `extract` | Batch main-figure extraction |
| `preflight` | Pre-build check of content.json |
| `build` | Generate the DOCX |
| `audit` | Structural audit |
| `render` | Cached page-by-page inspection images |

`run.py` only dispatches and forwards arguments and exit codes; the original `scripts/*.py` entry points remain directly runnable. The scripts handle deterministic work; reading, judgment, and content.json authoring stay with the agent, and `run.py` is not an automatic interpretation engine.

Verified scope: Windows 11 + Python 3.13 (the local virtual environment) only. The complete synthetic-test-sample chain including the material system section (preflight→build→audit→render) has passed: Word COM produced the DOCX→PDF conversion and page-by-page PNGs, and all 3 pages passed page-by-page inspection; the earlier 2-page sample without a materials section also passed. The LibreOffice path is untested because LibreOffice is not installed here. Other operating systems, Python versions, and agent clients are unverified; skill auto-discovery outside Codex is unverified, so an untested client should explicitly read the `SKILL.md` at a given path and run its scripts.

## Optional: Install into Codex

Installing into a Codex skill directory is optional. After downloading or cloning the repository, run this from the repository root:

```powershell
.\install.ps1
```

The default installation creates a personal Codex Skill directory junction pointing to `skill/xg-reading` (default target `$HOME\.codex\skills\xg-reading`; pass `-TargetSkillDir <directory>` to choose another target). This keeps the rules and scripts synchronized with the repository, and paper outputs are written back to `outputs/` at the repository root.

If a skill with the same name already exists, back up local changes and run:

```powershell
.\install.ps1 -ReplaceExisting
```

If a directory junction is unavailable, use copy mode with a repository-path configuration:

```powershell
.\install.ps1 -Mode Copy -ReplaceExisting
```

Copy mode writes `xg-reading.local.json` into the target directory with `repository_root` pointing at this repository, so artifacts still return to the repository `outputs/`. The installer prints the installation target and the default outputs location. The installer is PowerShell-based and mainly intended for Windows; installation and skill auto-discovery on other platforms are unverified.

`outputs/` is a local workspace ignored by Git. Each paper receives its own folder: the final Word document is placed at the top level, while crops, content JSON, the image-identity manifest, rendered pages, and audit reports are stored under `process/`. Source PDFs, supplementary files, and movies are not copied; their paths and SHA-256 values are recorded in `source-manifest.json`. In standalone mode, artifacts are written under the directory given by `--output-root` with the same folder structure.

Restart Codex, then invoke the Skill explicitly:

```text
Use $xg-reading to deeply read this life-science paper and create a Chinese Word reader.
```

The generated reader remains Chinese. This English README documents the project only; it does not add English output mode.

## Recommended Inputs

- Main paper PDF;
- Supplementary Information;
- Supplementary Movies or accessible video files;
- Any question the reader should prioritize.

When key material is missing, the Skill marks the evidence gap rather than inventing data from domain knowledge.

## Accuracy Notice

XG-Reading assists scientific reading. It does not replace the original paper, peer review, or the researcher's own judgment. AI-generated content may omit, misread, or overstate evidence. Check experimental conditions, sample size, statistical methods, mechanism, efficacy, and safety claims against the original text, complete captions, Methods, Supplementary Information, and source data.

## Repository Status

This repository has not selected an open-source license. In the absence of a license, all rights are reserved. A license can be added later if copying, modification, or redistribution is intended.
