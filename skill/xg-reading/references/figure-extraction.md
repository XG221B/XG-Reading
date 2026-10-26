# Figure and caption extraction

Use PDF text coordinates to crop every main figure and its complete caption. Never use one fixed bottom coordinate or one fixed page percentage across figures.

This file is the authoritative definition of the extraction workflow, cache behaviour, single-figure fallback, and acceptance gates; `SKILL.md` workflow step 6 points here. The batch path is the main workflow; the single-figure script is a debugging and boundary tool.

## Required workflow

1. Locate the PDF page and exact caption label for each figure.
2. Run the batch extractor through the unified entrypoint:

   ```powershell
   <PYTHON> <skill-dir>/run.py extract --pdf <paper.pdf> --outdir <process/figures> --fig "Fig. 1:2:Fig1.png" --fig "Fig. 2:3:Fig2.png:120"
   ```

   Each `--fig` entry is `<label>:<page>[:<output.png>][:<top_from_page>]`. Pages are processed in parallel, each page is rendered only once, and captions are detected before rendering. The batch command writes a `.crop.json` report next to each image. Each report is schema version 2 and records `caption_label_matched` (the caption marker actually matched) and `output_sha256` (the output PNG hash). A crop is reused only when the report schema, source fingerprint (PDF SHA-256 plus page and options), and output PNG hash all match; a corrupt, non-object, or older-schema report is recomputed, and `--no-cache` forces re-extraction.
3. Keep object identity in caption search: `Fig.1` is not `Fig.10`, `Table 1` is not `Fig 1`, and `Fig.S1` is not `Fig.1`. When a page has no text layer, extraction stops with `unsupported_text_layer` and needs a manual crop region or a text-based PDF; this is a failure, not a successful low-confidence crop.
4. Read each figure's `.crop.json` report next to the image. The batch prints one result entry per requested figure; read the full `crop.json` of the figures you are working on (the file keeps the complete caption) instead of copying every report into shared context. Confirm that `caption_label_matched` corresponds to the expected object, `caption_text` begins with the expected figure label, contains the final caption sentence, and does not contain the following Results or Discussion paragraph.
5. Open each cropped image at 100% zoom. Confirm that every panel label, axis, legend, scale bar, complete caption line, and footnote is visible. This is crop completeness only; it does not establish that the scientific interpretation of the panels is correct (see `SKILL.md` workflow step 9).
6. Stop for manual review when the caption spans pages, the figure and caption are on different pages, the PDF text layer is corrupt, or the report is low confidence. Do not widen the bottom crop merely to avoid checking the caption.

## Single-figure fallback (debugging or boundary cases)

`scripts/extract_figure_region.py` remains available for one-off diagnosis or boundary cases: refining `--top-from-page`, re-extracting a single figure after a boundary change, or handling a page that the batch path reports as low confidence. It is not the main workflow. When it is used, read its `.crop.json` report and inspect the image exactly as above.

```powershell
& $PYTHON scripts/extract_figure_region.py `
  --pdf paper.pdf `
  --page 4 `
  --label "Fig. 2" `
  --output images/figure-2-with-caption.png
```

If the automatic top is wrong:

```powershell
& $PYTHON scripts/extract_figure_region.py `
  --pdf paper.pdf `
  --page 4 `
  --label "Fig. 2" `
  --top-from-page 38 `
  --output images/figure-2-with-caption.png
```

`--top-from-page` is measured in PDF points from the page top.

## Acceptance gates

- The batch run reports one entry per requested figure; failed figures are reported on stderr with a non-zero exit code, and only failed figures need retrying.
- The `.crop.json` report is schema version 2, its `caption_label_matched` matches the expected object, and its `output_sha256` matches the current PNG; an older-schema or hash-mismatched report is not accepted as a cache hit.
- The crop contains the complete figure and complete caption.
- The crop contains no paragraph after the caption.
- The crop report records the expected label and caption text.
- Low-confidence output is not used in the DOCX without manual visual confirmation.
- A caption image is regenerated after any boundary change; an old crop is never silently reused.
