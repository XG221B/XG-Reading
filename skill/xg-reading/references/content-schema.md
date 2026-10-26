# Content JSON contract

Write one UTF-8 JSON file. Image paths may be absolute or relative to the JSON directory. Do not place Markdown syntax inside values.

```json
{
  "document_title": "论文题目与逐图解读",
  "citation": "论文：Author et al., Title, Journal,Year",
  "materials": {
    "heading": "材料体系与设计思路",
    "items": [
      {"name": "材料/组分名称", "role": "作用（建议注明Fig.x依据）"},
      {"name": "材料/组分名称", "role": "作用（建议注明Fig.x依据）"}
    ],
    "structure": {
      "label": "Fig.1A",
      "title": "材料结合后的结构示意",
      "image": "images/structure_with_caption.png",
      "explanation": "各组分如何结合、形成何种结构，以及该结构对功能的意义。"
    },
    "summary": "两三句话概括：本文用这种材料体系以什么方式解决了什么问题。"
  },
  "field_positioning": {
    "heading": "领域定位与本文解决的问题",
    "paragraphs": ["领域问题", "具体缺口", "本文贡献与边界"]
  },
  "bullet_notes": [],
  "logic_chain": [
    {"title": "Step1：为什么需要这一步", "text": "对应Fig.1：实验、结果及其支持的结论。"}
  ],
  "future_outlook": [
    {"title": "第一，作者明确提出的未解决问题。", "text": "注明Discussion、Conclusion或Future work中的原文依据，并用中文说明其含义。"}
  ],
  "evidence_blocks": [
    {
      "kind": "figure",
      "label": "Fig.1",
      "title": "Figure 1：主图英文标题的准确中文翻译",
      "image": "images/figure1_with_caption.png",
      "paper_claim": "作者对该证据块的主要表述。",
      "panel_explanations": [
        {"title": "Fig.1A：该panel图注内容的中文译名；Fig.1B：与其合并解读的panel译名", "text": "Fig.1A-B的实验设计、读图方法、结果，以及该panel支撑的小结论、对应逻辑链第几步、为什么能支撑（先读图、后说支撑）。"},
        {"title": "Fig.1C：该panel图注内容的中文译名", "text": "Fig.1C的实验设计、读图方法、结果，以及所支撑的小结论及其依据。"}
      ],
      "logic_role": "该证据块在全文论证中的作用。",
      "support_text": "补充材料如何改变对主结论的信心。",
      "support_images": [
        {"label": "Fig.S1", "path": "images/fig_s1_with_caption.png"}
      ]
    }
  ]
}
```

## Required fields

- Require `document_title`, `citation`, `field_positioning.paragraphs`, `logic_chain`, and `evidence_blocks`.
- For new tasks whose subject is an engineered material, device, or micro/nanorobotic system, require `materials`. Legacy content JSON without `materials` still builds and audits; preflight and audit report it as a warning.
- When `materials` is present, require a non-empty `materials.items` (each item with `name` and `role`) and `materials.summary`. `materials.heading` is optional and defaults to `材料体系与设计思路`; `materials.structure` is optional. When `structure` is present, require `structure.title`, `structure.image`, and `structure.explanation`; `structure.label` is optional.
- For every new evidence block require `label`, `title`, `image`, `paper_claim`, `panel_explanations`, and `logic_role`.
- Set `kind` to `figure`, `table`, `conceptual_figure`, or another precise label.
- `future_outlook`, `support_text`, `support_images`, and `bullet_notes` are optional.
- Use empty arrays when optional evidence is absent. Never invent missing supplements.

## Content rules

- Start with the material system: list every functional component and the role the paper assigns to it, citing the Figure or panel that demonstrates that role. `materials.items` must cover all functional components; do not add components or functions the paper does not support.
- Use the paper's own original figure for `structure.image` and keep its complete caption. Do not redraw, composite, or infer a material structure the source does not show; when the structure figure cannot be recovered, omit `structure` and state the limitation.
- Render the structure heading from `structure.label` and `structure.title`: `structure.label` (for example `Fig.1A`) becomes the left-aligned heading prefix and renders as `Fig.1A：<title>`; when `label` is omitted, render `title` alone.
- Keep `materials.summary` to two or three sentences that state which problem the material system solves and through what design, without adding functions or mechanisms the authors do not claim.
- Use `field_positioning` for the field problem, narrower gap, study system, actual contribution, and unresolved boundary.
- Make each logic step explain why the next evidence is needed, what was done, what was observed, and what claim is supported. Start its body with `对应Fig.x：` or the equivalent Table label; put a colon immediately after the label, not a full stop.
- Use `paper_claim` as direct prose after the main image. Do not prepend “论文中的说法：”.
- Translate the full main-figure caption title accurately into `title`, prefixed by its evidence label, for example `Figure 1：OMV-siR机器人的制备与表征`. This is the single centered heading before the image; do not add another main-figure title after the image.
- Preserve every main panel. Write each `panel_explanations` item as an object with `title` and `text`. Translate the panel-specific caption clause into `title`, including its `Fig.xA` label. When panels are interpreted together, combine their translated titles in the same `title` string, separated by a Chinese semicolon, without inserting another paragraph. Write each `text` in two parts: first how to read the panel and what it shows, then which sub-claim it supports, which logic-chain step it serves, and why the reading supports it (state the reasoning plainly when it is obvious, and expand the reasoning chain when it involves controls, statistics, orthogonal validation, or indirect inference).
- Use `logic_role` for the concluding `Fig.x总结：` paragraph.
- Use complete figure or table images with their complete captions or notes. State uncertainty if the source cannot be recovered clearly.
- Create `future_outlook` only from a limitation, unresolved question, or next direction explicitly discussed by the authors in the Discussion, Conclusion, or stated future work. Cite the relevant source location in the text. Do not add the reader's own criticism, forecast, or proposed experiment to this section.
- Introduce necessary terms briefly in Chinese. Retain acronyms and proper nouns when they are more precise.
- Do not add spaces at Chinese-English or Chinese-number boundaries.
- Do not add personal questions, interview prompts, or proposed experiments unless requested.

## Evidence labels and panel coverage

- `label` and `title` must identify the same object. `Fig.1` and `Fig.10`, `Table 1` and `Fig 1`, `Fig.S1` and `Fig.1` are different objects; never infer the object from the first digits in a string.
- Every `panel_explanations[].title` must carry panel letters that belong to the block object. Ranges such as `A–C` are expanded to A, B, C. A repeated panel letter is an error; missing letters between A and the highest covered letter are a warning to verify against the source caption.
- Figures and tables without panels are not forced to invent A/B labels, but `panel_explanations` still needs at least one non-empty entry.
- Preflight checks label/title consistency and panel ownership/coverage. It does not build a source inventory by checking every expected panel against the original article: a passing preflight is a label/format check, not proof that all source panels are covered.

## Image manifest

The builder writes `image-manifest.json` next to `content.json` in `process/`. Its `schema_version` is `1`, `docx_sha256` records the DOCX it describes, and `images` is an ordered array in document appearance order. Each entry has `kind` (`materials_structure`, `evidence_main`, or `support_sheet`), `object`, `source`/`source_sha256` when the image comes from a file, `members` for support sheets (member paths, hashes, and order), plus `embedded_sha256` and `width_emu`/`height_emu`.

Audit checks embedded bytes, source-image hashes, and support-member order against this manifest. A missing manifest is a warning only (legacy or externally built DOCX); an unreadable manifest, an unsupported schema, or mismatched image identity is an error. A DOCX hash that differs from `docx_sha256` is a warning that the DOCX was modified after the build. The same image may appear twice legitimately, for example as the materials structure figure and as a main evidence figure; identity is checked per occurrence, not by unique media count.

## Legacy verdict fields

`limitations` and `trends` still build, but preflight and audit warn that they were not verified against the authors' Discussion/Conclusion. New tasks must put author-grounded items in `future_outlook` and cite the source location for each item.

The builder accepts legacy `figures`, `translated_title`, and string-only `panel_explanations` as fallbacks, but new tasks must use `evidence_blocks`, place the translated caption title directly in `title`, and use panel objects. Legacy content without `materials` remains buildable and auditable; preflight and audit report it as a warning, while new tasks centered on an engineered material, device, or micro/nanorobotic system must include it.
