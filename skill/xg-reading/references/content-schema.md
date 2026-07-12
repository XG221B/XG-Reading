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
    {"title": "Step1：为什么需要这一步", "text": "对应Fig.1或Table 1。实验与结果。"}
  ],
  "future_outlook": [
    {"title": "第一，作者明确提出的未解决问题。", "text": "注明Discussion、Conclusion或Future work中的原文依据，并用中文说明其含义。"}
  ],
  "evidence_blocks": [
    {
      "kind": "figure",
      "title": "Figure 1：一句话核心结论",
      "image": "images/figure1_with_caption.png",
      "paper_claim": "作者对该证据块的主要表述。",
      "panel_explanations": [
        "Fig.1A-B……",
        "Fig.1C……"
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
- For every evidence block require `title`, `image`, `paper_claim`, `panel_explanations`, and `logic_role`.
- Set `kind` to `figure`, `table`, `conceptual_figure`, or another precise label.
- `future_outlook`, `support_text`, `support_images`, and `bullet_notes` are optional.
- Use empty arrays when optional evidence is absent. Never invent missing supplements.

## Content rules

- Use `field_positioning` for the field problem, narrower gap, study system, actual contribution, and unresolved boundary.
- Make each logic step explain why the next evidence is needed, what was done, what was observed, and what claim is supported.
- Preserve every main panel. Merge panels only when they form one indivisible experiment.
- Use complete figure or table images with their complete captions or notes. State uncertainty if the source cannot be recovered clearly.
- Create `future_outlook` only from a limitation, unresolved question, or next direction explicitly discussed by the authors in the Discussion, Conclusion, or stated future work. Cite the relevant source location in the text. Do not add the reader's own criticism, forecast, or proposed experiment to this section.
- Introduce necessary terms briefly in Chinese. Retain acronyms and proper nouns when they are more precise.
- Do not add spaces at Chinese-English or Chinese-number boundaries.
- Do not add personal questions, interview prompts, or proposed experiments unless requested.

The builder accepts legacy `figures` as a fallback key, but new tasks must use `evidence_blocks`.
