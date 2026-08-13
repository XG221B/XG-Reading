---
name: xg-reading
description: Read life-science papers deeply from figures, tables, methods, statistics, supplementary materials, and exact claim-to-evidence links, then create a consistent Chinese DOCX reader. Use for 生物论文精读、逐图解读、文献阅读、证据链梳理、机制论文分析、组学论文分析、免疫或微生物论文分析、结构生物学、方法学、生物材料、药物递送、动物或临床研究, or when the user explicitly invokes $xg-reading.
---

# XG-Reading

Create one source-grounded Chinese DOCX that reconstructs how a life-science paper argues from data. Preserve depth by routing each paper to domain-specific rules instead of forcing every paper into one generic chain.

## Boundaries

- 除用户单独明确要求外，任何改动都绝对不允许修改任何与内容有关的东西：解读质量标准、文档格式（字体、字号、颜色、行距、缩进、对齐、分页、样式定义）、排版契约、模板资产、图题与段落措辞规范一律冻结。
- 纯技术维护（脚本、缓存、测试、工作区文档）同样受此约束：不得以任何方式改变 DOCX 输出外观或 content.json 的解释规则。
- 工具层面的效率/质量优化永远不得以格式或内容规则的任何让步为代价；冲突时一律优先保证格式与内容规则不变。

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
8. Read `references/subagent-figure-template.md` before dispatching figure-analysis subagents.
9. Treat `assets/reference.docx` and `references/template-contract.md` as the visual authority.

## Workflow

1. Initialize the per-paper workspace with `scripts/reader_workspace.py init` before collecting or creating task files. Use the returned paths for every durable artifact. Pass `--title "<年份>-<文章标题>"` (for example `--title "2023-Autonomous metal-organic framework nanorobots for active mitochondria-targeted cancer therapy"`); the output folder is then named `outputs/<年份>-<文章标题>`. Never write task artifacts into the installed Codex Skill directory, desktop root, or system temporary folders.
2. Collect the main paper, Supplementary Information, source data, and supplementary movies supplied by the user. Record supplied and missing material in the workspace manifest instead of copying original files or guessing missing evidence.
3. Determine the paper type, central claims, biological scale, model system, and decisive experiments before drafting. Do not infer the paper's chain from section headings alone.
4. Build a private claim ledger for every major conclusion: exact claim, direct measurement, intervention, controls, biological replicate, sample size, statistical test, orthogonal validation, alternative explanation, and evidence strength.
5. Extract every complete main figure and caption into `process/figures/` with `scripts/extract_figures_batch.py`, passing one `--fig "<label>:<page>[:<output.png>][:<top_from_page>]"` entry per figure; pages are processed in parallel and each page is rendered only once, and captions are detected before rendering. Crops whose source fingerprint (PDF SHA-256 plus page and options) is unchanged hit the cache on reruns; use `--no-cache` to force re-extraction. Inspect each crop report and the image at 100% zoom. Never crop all figures with one fixed bottom coordinate or page percentage. Extract only supplementary figures, tables, or movie frames that directly support a main claim.
6. Reconstruct the paper-specific argument chain. Preserve the paper's actual logic even when it does not follow construction, mechanism, animal, or translation stages. Begin each logic-step body with `对应Fig.x：` or the equivalent Table label, using a colon immediately after the evidence label.
7. Analyze every main figure in parallel: dispatch one subagent per main figure using the task template in `references/subagent-figure-template.md`. Give each subagent only its own context pack: the claim ledger from step 4, the figure PNG, its `crop.json` (full caption text, warnings, boundary reason), the supporting Results/Methods/statistics paragraphs, the selected domain module's key checks, and the mapping of this figure's panels to the claim-ledger entries and the logic-chain step from step 6. Do not send the whole paper to every subagent. If the environment cannot dispatch subagents, run the same template serially. Optional model layering: when the environment supports per-subagent models, a faster model may analyze the figures, but the main model must keep the review gate in step 8 and must not skip it.
8. Merge and spot-check: merge the returned evidence blocks in figure order. For every block, verify text consistency against the caption in `crop.json` (panel labels, n values, statistical tests, control groups, effect direction). Verify every panel text contains both the reading explanation and the supported sub-claim with its reasoning; a claim that is not in the claim ledger or a panel without a claim link goes back to the subagent. Re-read the figure image only for mismatched or low-confidence items, never re-read every figure. Confirm the merged blocks stay consistent with the claim ledger and the logic chain from step 6. Apply the selected domain module here; do not replace domain reasoning with generic questions merely to increase coverage.
9. Write `process/content.json` following `references/content-schema.md`. Mark uncertainty and inference explicitly. Use Chinese where accurate; retain necessary acronyms and proper nouns. Before running the builder, machine-check the file with `scripts/preflight_content.py --content <process/content.json>` and self-check the remaining audit contract items (figure heading count, panel spacer count, complete captions) so the first build and audit pass succeeds.
10. Generate and audit the DOCX with the bundled workspace Python runtime. Write the final DOCX to the paper directory and all audit/support artifacts to `process/`:

   ```powershell
   & $PYTHON_BIN scripts/preflight_content.py --content <process/content.json>
   & $PYTHON_BIN scripts/build_reader_docx.py --content <process/content.json> --output <paper/<title>论文逐图解读.docx> --work-dir <process/supplementary>
   & $PYTHON_BIN scripts/audit_reader_docx.py --docx <paper/<title>论文逐图解读.docx> --content <process/content.json> --json-report <process/audit-report.json>
   ```

11. Render the final DOCX to `process/rendered/` with `scripts/render_reader_docx.py --docx <final.docx> --work-dir <process/rendered>` and inspect every page at 100% zoom. The render is cached by the DOCX SHA-256 plus the PNG scale and conversion engine: after a fix cycle, a rerun skips both the Word/LibreOffice conversion and PNG rasterization when nothing changed, so rerun it before each inspection and it will only reconvert when needed. On a cache hit the script prints each page prefixed with `changed` or `unchanged` (page PNG hashes are compared with the previous render). On the first pass inspect every page. After a fix cycle, re-inspect only the pages marked `changed`, and when the total page count changed, also the pages adjacent to the break shift. Fix incomplete captions, unreadable figures, isolated headings, clipping, overlap, excessive blank space, and awkward page breaks.
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
- Within each main-figure block, use the translated full caption title as the centered `Figure X：<中文图题>` heading before the image. Write the authors' figure-level claim directly after the image without a “论文中的说法：” label, then place each translated panel title or combined panel-group title left aligned and follow it with the panel interpretation. Do not repeat the main-figure title after the image. End with `Fig.x总结：` instead of “这张图在论文逻辑中的位置：”.
- Center chapter-level section headings and `Figure X：<中文图题>` headings. Keep `Step` headings and panel titles left aligned. Insert the retained 0.2-line blank spacer between adjacent panel interpretation groups only.
- Start every main Figure/Table evidence block on a new page, regardless of the unused space on the preceding page. Do not create a separate blank page before it.
- Keep complete figure captions with their figures and integrate supporting material under the relevant main figure.
- Reject a crop that contains text from the Results or Discussion paragraph following the caption, even when the caption itself is complete.
- Do not insert spaces at Chinese-Latin or Chinese-number boundaries.

## Failure conditions

Stop and report the limitation when the source is unreadable, a required supplement is missing, or a central figure cannot be recovered clearly enough to interpret. Do not compensate with plausible-sounding biology.
