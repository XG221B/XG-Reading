# Content JSON contract

Write one UTF-8 JSON file. Image paths may be absolute or relative to the JSON directory. Do not place Markdown syntax inside values.

```json
{
  "document_title": "论文题目与逐图解读",
  "citation": "论文：Author et al., Title, Journal,Year",
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
- For every new evidence block require `label`, `title`, `image`, `paper_claim`, `panel_explanations`, and `logic_role`.
- Set `kind` to `figure`, `table`, `conceptual_figure`, or another precise label.
- `future_outlook`, `support_text`, `support_images`, and `bullet_notes` are optional.
- Use empty arrays when optional evidence is absent. Never invent missing supplements.

## Content rules

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

The builder accepts legacy `figures`, `translated_title`, and string-only `panel_explanations` as fallbacks, but new tasks must use `evidence_blocks`, place the translated caption title directly in `title`, and use panel objects.
