---
name: xg-reading
description: Read life-science papers deeply from figures, tables, methods, statistics, supplementary materials, and exact claim-to-evidence links, then create a consistent Chinese DOCX reader. Use for 生物论文精读、逐图解读、文献阅读、证据链梳理、机制论文分析、组学论文分析、免疫或微生物论文分析、结构生物学、方法学、生物材料、药物递送、动物或临床研究, or when the user explicitly invokes $xg-reading.
---

# XG-Reading

Create one source-grounded Chinese DOCX that reconstructs how a life-science paper argues from data. Preserve depth by routing each paper to domain-specific rules instead of forcing every paper into one generic chain.

## Load resources

1. Read `references/reading-method.md` for the shared evidence workflow.
2. Read `references/biology-routing.md`, classify the paper, and choose one primary domain module. Add at most one secondary module when the paper is genuinely hybrid.
3. Read the selected module completely:
   - `references/molecular-cellular.md`
   - `references/omics-computational.md`
   - `references/immunology-microbiology.md`
   - `references/structural-methods.md`
   - `references/translational-engineering.md`
4. Read `references/content-schema.md` before creating task-local JSON.
5. Read `references/style-contract.md` before generation and audit.
6. Read `references/figure-extraction.md` before extracting figures from a PDF.
7. Read `references/workspace-layout.md` before creating any task files.
8. Treat `assets/reference.docx` and `references/template-contract.md` as the visual authority.

## Workflow

1. Initialize the per-paper workspace with `scripts/reader_workspace.py init` before collecting or creating task files. Use the returned paths for every durable artifact. Never write task artifacts into the installed Codex Skill directory, desktop root, or system temporary folders.
2. Collect the main paper, Supplementary Information, source data, and supplementary movies supplied by the user. Record supplied and missing material in the workspace manifest instead of copying original files or guessing missing evidence.
3. Determine the paper type, central claims, biological scale, model system, and decisive experiments before drafting. Do not infer the paper's chain from section headings alone.
4. Build a private claim ledger for every major conclusion: exact claim, direct measurement, intervention, controls, biological replicate, sample size, statistical test, orthogonal validation, alternative explanation, and evidence strength.
5. Extract every complete main figure and caption into `process/figures/` with `scripts/extract_figure_region.py`. Inspect its crop report and the image at 100% zoom. Never crop all figures with one fixed bottom coordinate or page percentage. Extract only supplementary figures, tables, or movie frames that directly support a main claim.
6. Reconstruct the paper-specific argument chain. Preserve the paper's actual logic even when it does not follow construction, mechanism, animal, or translation stages.
7. Analyze every main figure and every panel against the figure, caption, Results, Methods, statistics, and relevant supplement. Explain how to read the axes, groups, channels, controls, effect direction, uncertainty, and biological meaning.
8. Apply the selected domain module. Do not replace domain reasoning with generic questions merely to increase coverage.
9. Write `process/content.json` following `references/content-schema.md`. Mark uncertainty and inference explicitly. Use Chinese where accurate; retain necessary acronyms and proper nouns.
10. Generate and audit the DOCX with the bundled workspace Python runtime. Write the final DOCX to the paper directory and all audit/support artifacts to `process/`:

   ```powershell
   & $PYTHON_BIN scripts/build_reader_docx.py --content <process/content.json> --output <paper/<title>论文逐图解读.docx> --work-dir <process/supplementary>
   & $PYTHON_BIN scripts/audit_reader_docx.py --docx <paper/<title>论文逐图解读.docx> --content <process/content.json> --json-report <process/audit-report.json>
   ```

11. Render the final DOCX to `process/rendered/` and inspect every page at 100% zoom. Fix incomplete captions, unreadable figures, isolated headings, clipping, overlap, excessive blank space, and awkward page breaks.
12. Return only the final DOCX unless the user requests additional files.

## Depth gates

- Tie each important conclusion to an exact Figure, panel, table, or supplementary item.
- Distinguish what was measured from what was inferred.
- Distinguish association, intervention, necessity, sufficiency, rescue, and direct mechanism.
- Verify biological replicates, experimental units, sample size, normalization, statistical model, and multiple-testing correction where relevant.
- Check whether representative images have independent quantification.
- Check whether conclusions survive orthogonal assays, independent models, batches, cohorts, or perturbations.
- Treat enrichment, colocalization, binding, marker change, endpoint distribution, and prediction as evidence of different strengths; never collapse them into mechanism.
- Treat cell, organoid, animal, and human evidence as distinct levels of generalization.
- Explain negative results, conflicting panels, and missing controls when they affect the argument.

## Formatting

- Preserve the retained black academic layout and non-collapsible custom styles.
- Preserve the retained section order: field positioning and the paper's problem first, then the full-paper figure/table logic chain, then an optional source-grounded future outlook, and only then the detailed figure/table evidence blocks. Do not reorder these sections for convenience or add a new opening background section.
- Include “未来展望” only when the authors explicitly discuss a limitation, unresolved question, or next direction in the Discussion, Conclusion, or stated future work. Do not create a standalone limitations or trend-judgment section from the reader's own critique, and omit the section entirely when the source contains no such discussion.
- Use 华文中宋 for Chinese and Times New Roman for English and numbers.
- Keep body text justified with the spacing and hierarchy in `references/style-contract.md`.
- Center only chapter-level section headings. Keep `Step` headings and paragraph-level prompts such as “图上如何体现：” left aligned.
- Start every main Figure/Table evidence block on a new page, regardless of the unused space on the preceding page. Do not create a separate blank page before it.
- Keep complete figure captions with their figures and integrate supporting material under the relevant main figure.
- Reject a crop that contains text from the Results or Discussion paragraph following the caption, even when the caption itself is complete.
- Do not insert spaces at Chinese-Latin or Chinese-number boundaries.

## Failure conditions

Stop and report the limitation when the source is unreadable, a required supplement is missing, or a central figure cannot be recovered clearly enough to interpret. Do not compensate with plausible-sounding biology.
