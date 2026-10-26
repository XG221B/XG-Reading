---
name: xg-reading
description: Read life-science papers deeply from figures, tables, methods, statistics, supplementary materials, and exact claim-to-evidence links, then create a consistent Chinese DOCX reader. Use for 生物论文精读、逐图解读、文献阅读、证据链梳理、机制论文分析、组学论文分析、免疫或微生物论文分析、结构生物学、方法学、生物材料、药物递送、微纳机器人、纳米机器人、微纳马达、主动递送、动物或临床研究, or when the user explicitly invokes $xg-reading.
---

# XG-Reading

Create one source-grounded Chinese DOCX that reconstructs how a life-science paper argues from data. Preserve depth by routing each paper to domain-specific rules instead of forcing every paper into one generic chain.

## Boundaries

- 除用户单独明确要求外，任何改动都绝对不允许修改任何与内容有关的东西：解读质量标准、文档格式（字体、字号、颜色、行距、缩进、对齐、分页、样式定义）、排版契约、模板资产、图题与段落措辞规范一律冻结。
- 纯技术维护（脚本、缓存、测试、工作区文档）同样受此约束：不得以任何方式改变 DOCX 输出外观或 content.json 的解释规则。
- 工具层面的效率/质量优化永远不得以格式或内容规则的任何让步为代价；冲突时一律优先保证格式与内容规则不变。

## Runtime

Use any Python 3.11+ interpreter with the dependencies from `requirements.txt` installed (`python-docx`, `Pillow`, `pypdfium2`); `$PYTHON` below stands for that interpreter. Run the skill through `run.py` (`<PYTHON> <skill-dir>/run.py <command> [args]`): it dispatches to the existing scripts and forwards arguments and exit codes, and the individual scripts remain directly runnable. Any agent that can read text and images, execute local commands, and write to a user-specified output directory can run this skill; a plain chat interface or a cloud agent without local file access needs those tools first. Durable artifacts go to the resolved output root: the `outputs/` directory of a cloned XG-Reading repository by default, or a project directory given explicitly for a standalone skill copy. Rendering (`render`) needs LibreOffice, or Word with PowerShell on Windows; set `XG_READING_SOFFICE` to the LibreOffice executable when it is not on `PATH`.

## Load resources

1. Read `references/reading-method.md` for the shared evidence workflow.
2. Read `references/biology-routing.md`, classify the paper, and choose one primary domain module. Add at most one secondary module when the paper is genuinely hybrid.
3. Read the selected module completely:
   - `references/molecular-cellular.md`
   - `references/omics-computational.md`
   - `references/immunology-microbiology.md`
   - `references/structural-methods.md`
   - `references/translational-engineering.md`
   - `references/micro-nano-robotics.md`
4. Read `references/content-schema.md` before creating task-local JSON.
5. Read `references/style-contract.md` before generation and audit.
6. Read `references/figure-extraction.md` before extracting figures from a PDF.
7. Read `references/workspace-layout.md` before creating any task files.
8. Read `references/subagent-figure-template.md` before dispatching figure-analysis subagents.
9. Treat `assets/reference.docx` and `references/template-contract.md` as the visual authority.

## Workflow

1. Initialize the per-paper workspace with `<PYTHON> <skill-dir>/run.py workspace init` before collecting or creating task files. Use the returned paths for every durable artifact. Pass `--title "<年份>-<文章标题>"` (for example `--title "2023-Autonomous metal-organic framework nanorobots for active mitochondria-targeted cancer therapy"`); in a cloned repository the output folder is then named `outputs/<年份>-<文章标题>`, while a standalone skill copy can write to any project directory with `--output-root <directory>` or to `<repository>/outputs` with `--repository-root <repository>`. The manifest is schema version 2: a repeated `init` without `--supplement`/`--movie` keeps registered sources, while added, removed, or changed sources set `stale=true` with a stderr warning; the old DOCX is not deleted but is not a current success artifact. Never write task artifacts into the skill installation directory, desktop root, or system temporary folders.
2. Collect the main paper, Supplementary Information, source data, and supplementary movies supplied by the user. Record supplied and missing material in the workspace manifest instead of copying original files or guessing missing evidence.
3. Determine the paper type, central claims, biological scale, model system, and decisive experiments before drafting. Do not infer the paper's chain from section headings alone.
4. Establish the material system before drafting: list every material, component, or functional module and the role the paper assigns to it, citing the Figure or panel that demonstrates each role; identify how the components combine and what final structure or assembly forms; extract the paper's original structure figure with its complete caption; write a two- or three-sentence design rationale stating what problem this material system solves and through what design. Record this in `process/content.json` as the `materials` block defined by `references/content-schema.md`; it is required for new tasks centered on an engineered material, device, or micro/nanorobotic system and may be omitted only when the paper has no such system.
5. Build a provisional private claim ledger for every major conclusion with stable IDs: exact claim, source location, direct measurement, intervention, controls, biological replicate, sample size, statistical test, orthogonal validation, alternative explanation, evidence strength, and dependencies on other claims. Mark the ledger provisional and revise it when subagent findings or adjudication change a claim.
6. Extract every complete main figure and caption into `process/figures/` with `<PYTHON> <skill-dir>/run.py extract`, passing one `--fig "<label>:<page>[:<output.png>][:<top_from_page>]"` entry per figure; the batch command, single-figure fallback, and acceptance gates are defined in `references/figure-extraction.md`. Each `.crop.json` report is schema version 2 and records `caption_label_matched` and `output_sha256`; a crop is reused only when the report schema, source fingerprint, and output PNG hash all match, and corrupt or older-schema reports are recomputed. Captions are matched by object type and number (`Fig.1` is not `Fig.10`, `Table 1` is not `Fig 1`, `Fig.S1` is not `Fig.1`); when a page has no text layer the extractor reports `unsupported_text_layer` and the region needs manual handling. This is the crop-completeness check only: confirm every main figure and its complete caption were recovered; it does not verify the scientific interpretation. Never crop all figures with one fixed bottom coordinate or page percentage. Extract only supplementary figures, tables, or movie frames that directly support a main claim.
7. Reconstruct the paper-specific argument chain. Preserve the paper's actual logic even when it does not follow construction, mechanism, animal, or translation stages. Begin each logic-step body with `对应Fig.x：` or the equivalent Table label, using a colon immediately after the evidence label.
8. Analyze every main figure in parallel: dispatch one subagent per main figure using the task template in `references/subagent-figure-template.md`, which defines the required context pack, evidence-status vocabulary, and verdict protocol. Do not send the complete ledger, the whole paper, or unrelated figures. In brief, give each subagent the paper's one-sentence thesis and condensed logic chain, the provisional claims relevant to this figure (stable IDs, evidence strength, necessary dependencies), the figure PNG, its `crop.json` (complete caption, warnings, boundary reason), the exact Results/Methods/statistics paragraphs, and the applicable domain-module checks; complete captions, n definitions, controls, and source method passages must be sent verbatim, not summarized. Subagents return `supports`/`qualifies`/`challenges`/`insufficient` for existing claims and candidates for new findings; the main task adjudicates, then updates the ledger, affected evidence blocks, and logic chain. If the environment cannot dispatch subagents, run the same template serially. Optional model layering: when the environment supports per-subagent models, a faster model may analyze the figures, but the main model must keep the review gate in step 9 and must not skip it.
9. Merge and spot-check, then run the scientific review: merge returned blocks in figure order; verify each block against `crop.json` (panel labels, n values, statistical tests, control groups, effect direction); verify every panel text contains both the reading explanation and the supported sub-claim with its reasoning; adjudicate each claim as `supports`/`qualifies`/`challenges`/`insufficient`; then update the provisional ledger, affected blocks, and logic chain. This scientific review is distinct from the crop-completeness check in step 6 and the final DOCX page inspection in step 12; none of the three substitutes for another. At minimum review the panels supporting central conclusions, key quantitative comparisons, causal or mechanistic inferences, negative or conflicting results, and any text-caption mismatch. Record for each reviewed panel: axes and units, linear/log scale, error bars, groups, controls, effect direction, and statistical markers; check n and tests against the caption and Methods, never infer them from the image. Other panels use a recorded sampling rule; when a substantive reading error appears, expand to all panels of that figure and to figures of the same type, and expand to all figures when an error crosses figures. Do not default to re-sending every full-resolution image; local zooms keep their figure, panel, and coordinate context. Track review state per figure as `unreviewed`, `reviewed`, `needs_source`, or `needs_revision` with the source version; high model confidence is not evidence of review. Apply the selected domain module here; do not replace domain reasoning with generic questions merely to increase coverage.
10. Write `process/content.json` following `references/content-schema.md`, including the `materials` block when the paper studies an engineered material, device, or micro/nanorobotic system. Mark uncertainty and inference explicitly. Use Chinese where accurate; retain necessary acronyms and proper nouns. When a statistic or method is missing, use the scoped evidence-status wording defined in `references/subagent-figure-template.md`; never turn missing input into a paper deficiency. Put author-grounded limitations or future directions in `future_outlook` with their source locations; legacy `limitations`/`trends` still build but preflight and audit warn that they were not verified against the authors' Discussion/Conclusion. Before running the builder, machine-check the file with `<PYTHON> <skill-dir>/run.py preflight --content <process/content.json>` and self-check the remaining audit contract items (figure heading count, panel spacer count, complete captions) so the first build and audit pass succeeds. Preflight checks evidence-label/title consistency and panel ownership/coverage; it does not build a source inventory, so a passing preflight is not proof that every expected source panel was covered.
11. Generate and audit the DOCX with the same dependency-installed Python 3.11+ interpreter. Write the final DOCX to the paper directory and all audit/support artifacts to `process/`:

   ```powershell
   & $PYTHON <skill-dir>/run.py preflight --content <process/content.json>
   & $PYTHON <skill-dir>/run.py build --content <process/content.json> --output <paper/<title>论文逐图解读.docx> --work-dir <process/supplementary>
   & $PYTHON <skill-dir>/run.py audit --docx <paper/<title>论文逐图解读.docx> --content <process/content.json> --json-report <process/audit-report.json>
   ```

   The build writes `process/image-manifest.json` (schema version 1) with the ordered image occurrences, source hashes, support-sheet members, embedded byte hashes, and dimensions; audit verifies embedded bytes, source-image hashes, and member order against it. A missing manifest is a warning only (legacy or externally built DOCX); an unreadable manifest, unsupported schema, or mismatched image identity is an error, and a DOCX hash mismatch is a warning that the DOCX changed after build.

12. Render the final DOCX to `process/rendered/` with `<PYTHON> <skill-dir>/run.py render --docx <final.docx> --work-dir <process/rendered>` and inspect every page at 100% zoom. The render cache (schema version 3) records the DOCX hash, PNG scale, conversion engine and engine signature, the PDF hash, and every page hash; a cache hit requires all recorded outputs to verify, so rerun it before each inspection. On a miss LibreOffice conversions run in an isolated staging directory and publish only a validated PDF; every engine's PDF must be non-empty, readable, and have at least one page, and a failed conversion does not update the cache. A full render prints `changed`/`unchanged`/`added`/`removed` per page, and a workspace lock plus a converter lock (workspace first, then converter) prevents concurrent renders from corrupting the cache. On the first pass inspect every page. After a fix cycle, re-inspect only the pages marked `changed` or `added`, plus `removed` page shifts; when the total page count changed, also inspect the pages adjacent to the break shift. Fix incomplete captions, unreadable figures, isolated headings, clipping, overlap, excessive blank space, and awkward page breaks. This page inspection verifies DOCX readability and layout; it does not replace the scientific review in step 9 or the crop-completeness check in step 6.
13. Return only the final DOCX unless the user requests additional files.

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
- Tie every component role in the material-system table to a characterization, measurement, or experiment in the paper; do not assert a component or function that the figures do not support.
- Ground the structure claim in the paper's original figure and text; never redraw, composite, or infer a material structure the paper does not show.
- Apply domain checks by applicability: state which claim or system a check serves, which evidence it needs, and what the evidence gap limits; never require every check from every paper.
- Distinguish a component's designed role from a validated function; a validated function needs control or functional evidence, not only design intent.

## Formatting

- Preserve the retained black academic layout and non-collapsible custom styles.
- When the paper studies an engineered material, device, or micro/nanorobotic system, open with the material system: a centered `材料体系与设计思路` section, the two-column `材料/组分` / `作用` table, the paper's original structure figure under the left-aligned `Fig.1A：<title>` heading with its explanation beneath, and a bold-labeled `设计思路：` summary of two to three sentences. Use `references/style-contract.md` for the table width, borders, and image limits.
- Preserve the retained section order: the material system (`材料体系与设计思路`) first, then field positioning and the paper's problem, then the full-paper figure/table logic chain, then an optional source-grounded future outlook, and only then the detailed figure/table evidence blocks. Do not reorder these sections for convenience or add a new opening background section.
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
