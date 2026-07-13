# XG-Reading

[中文](README.md) | [English](README_EN.md)

XG-Reading is a Codex Skill for deep reading of life-science papers. It treats figures, experimental design, and evidence strength as the backbone of reading, reconstructing the claim-to-evidence chain across the main text, captions, Methods, and Supplementary Information into a consistent Chinese Word document.

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
- biomaterials, drug delivery, animal studies, and clinical translation.

Each paper uses one primary module and, only where truly needed, one secondary module. This preserves domain depth instead of applying a shallow universal checklist to every study.

## Output

The generated Chinese Word document usually includes:

1. field positioning, the research gap, and the paper's contribution;
2. the full figure/table logic chain;
3. translated main-figure and panel titles followed by panel-level interpretation;
4. supplementary evidence placed beside the main claim it supports;
5. an optional **Future Outlook** section, limited to limitations, open questions, or next directions explicitly discussed by the authors in the Discussion, Conclusion, or stated future work. When the paper provides no such source-grounded discussion, this section is omitted.

The Word output follows a fixed Chinese academic layout and is structurally audited and rendered page by page after generation. Chapter-level headings are centered; in-paragraph reading prompts remain left aligned. Every main Figure or Table starts on a new page for review and annotation.

## Install

After downloading or cloning the repository, run this from the repository root:

```powershell
.\install.ps1
```

The default installation creates a personal Codex Skill directory junction pointing to `skill/xg-reading`. This keeps the rules and scripts synchronized with the repository. Paper outputs are written back to `outputs/` at the repository root.

If a skill with the same name already exists, back up local changes and run:

```powershell
.\install.ps1 -ReplaceExisting
```

If a directory junction is unavailable, use copy mode with a repository-path configuration:

```powershell
.\install.ps1 -Mode Copy -ReplaceExisting
```

`outputs/` is a local workspace ignored by Git. Each paper receives its own folder: the final Word document is placed at the top level, while crops, content JSON, rendered pages, and audit reports are stored under `process/`. Source PDFs, supplementary files, and movies are not copied; their paths and SHA-256 values are recorded in `source-manifest.json`.

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
