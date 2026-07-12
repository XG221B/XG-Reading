# Figure and caption extraction

Use PDF text coordinates to crop every main figure and its complete caption. Never use one fixed bottom coordinate or one fixed page percentage across figures.

## Required workflow

1. Locate the PDF page and exact caption label for each figure.
2. Run `scripts/extract_figure_region.py`. The script detects the caption's two-column text extent, stops before the next text block, and writes a `.crop.json` report next to the image.
3. Read the report. Confirm that `caption_text` begins with the expected figure label, contains the final caption sentence, and does not contain the following Results or Discussion paragraph.
4. Open the cropped image at 100% zoom. Confirm that every panel label, axis, legend, scale bar, complete caption line, and footnote is visible.
5. Use `--top-from-page` when automatic top detection includes the journal header, excludes a panel, or has low confidence. This value is measured in PDF points from the page top.
6. Stop for manual review when the caption spans pages, the figure and caption are on different pages, the PDF text layer is corrupt, or the report is low confidence. Do not widen the bottom crop merely to avoid checking the caption.

## Example

```powershell
& $PYTHON_BIN scripts/extract_figure_region.py `
  --pdf paper.pdf `
  --page 4 `
  --label "Fig. 2" `
  --output images/figure-2-with-caption.png
```

If the automatic top is wrong:

```powershell
& $PYTHON_BIN scripts/extract_figure_region.py `
  --pdf paper.pdf `
  --page 4 `
  --label "Fig. 2" `
  --top-from-page 38 `
  --output images/figure-2-with-caption.png
```

## Acceptance gates

- The crop contains the complete figure and complete caption.
- The crop contains no paragraph after the caption.
- The crop report records the expected label and caption text.
- Low-confidence output is not used in the DOCX without manual visual confirmation.
- A caption image is regenerated after any boundary change; an old crop is never silently reused.
