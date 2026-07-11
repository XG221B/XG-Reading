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
6. Treat `assets/reference.docx` and `references/template-contract.md` as the visual authority.

## Workflow

1. Collect the main paper, Supplementary Information, source data, and supplementary movies supplied by the user. Identify missing material instead of guessing it.
2. Determine the paper type, central claims, biological scale, model system, and decisive experiments before drafting. Do not infer the paper's chain from section headings alone.
3. Build a private claim ledger for every major conclusion: exact claim, direct measurement, intervention, controls, biological replicate, sample size, statistical test, orthogonal validation, alternative explanation, and evidence strength.
4. Extract every complete main figure and caption. Extract only supplementary figures, tables, or movie frames that directly support a main claim.
5. Reconstruct the paper-specific argument chain. Preserve the paper's actual logic even when it does not follow construction, mechanism, animal, or translation stages.
6. Analyze every main figure and every panel against the figure, caption, Results, Methods, statistics, and relevant supplement. Explain how to read the axes, groups, channels, controls, effect direction, uncertainty, and biological meaning.
7. Apply the selected domain module. Do not replace domain reasoning with generic questions merely to increase coverage.
8. Write one UTF-8 JSON file following `references/content-schema.md`. Mark uncertainty and inference explicitly. Use Chinese where accurate; retain necessary acronyms and proper nouns.
9. Generate and audit the DOCX with the bundled workspace Python runtime:

   ```powershell
   & $PYTHON_BIN scripts/build_reader_docx.py --content <content.json> --output <final.docx>
   & $PYTHON_BIN scripts/audit_reader_docx.py --docx <final.docx> --content <content.json>
   ```

10. Render the final DOCX to page PNGs with the Documents skill. Inspect every page at 100% zoom and fix incomplete captions, unreadable figures, isolated headings, clipping, overlap, excessive blank space, and awkward page breaks.
11. Return only the final DOCX unless the user requests additional files.

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
- Use 华文中宋 for Chinese and Times New Roman for English and numbers.
- Keep body text justified with the spacing and hierarchy in `references/style-contract.md`.
- Keep complete figure captions with their figures and integrate supporting material under the relevant main figure.
- Do not insert spaces at Chinese-Latin or Chinese-number boundaries.

## Failure conditions

Stop and report the limitation when the source is unreadable, a required supplement is missing, or a central figure cannot be recovered clearly enough to interpret. Do not compensate with plausible-sounding biology.
