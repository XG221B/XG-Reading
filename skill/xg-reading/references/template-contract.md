# Retained template contract

- Reference: `assets/reference.docx`
- SHA-256: `A1EE0C4F7B46F20A8CA3EBFFE2224157E09FA0929A1F1DC02EC822CF6E2F8BB8`
- Content: generic XG-Reading placeholders and no source-specific material
- Sections: 1
- Embedded images: 0
- Page: Letter portrait
- Margins: 2.00 cm top/bottom, 2.30 cm left/right
- Body system: black, 华文中宋/Times New Roman, 11 pt, 1.25 spacing, justified, 0.74 cm first-line indent

## Visual pattern

1. Begin with the paper title and citation.
2. Establish the field-level direction, the problem already addressed by the field, the remaining problem, and the problem addressed by this paper.
3. Present the paper-specific figure/table logic chain before detailed figure reading.
4. Add an optional “未来展望” only when it is grounded in the authors' Discussion, Conclusion, or stated future work; otherwise omit it.
5. Center each chapter-level heading, while keeping paragraph-level reading prompts left aligned.
6. Start every evidence block on a new page with a one-sentence conclusion and a complete figure or table with caption.
7. Follow the image with the authors' figure-level claim as direct prose, without a visible prompt label.
8. Center the translated main-figure caption title, then use left-aligned translated panel titles followed by panel-level interpretation. Keep combined panel titles in one heading when the panels are explained together.
9. End each main-figure block with `Fig.x总结：`, followed by relevant supplementary support.
10. Keep supplementary evidence next to the main claim it changes.

## Editable and preserved elements

- Replace all placeholder text with source-grounded paper content.
- Preserve page geometry, font system, hierarchy, black visual treatment, paragraph rhythm, section order, and figure-centered flow.
- Allow any number of evidence blocks. Never add, remove, or reorder evidence merely to imitate the template length.
- Keep the retained reference unchanged; build outputs from a working document.

## Fidelity gates

- Verify the reference hash before generation.
- Pass `audit_reader_docx.py`.
- Render every output page and inspect it at 100% zoom.
- Permit page-count changes caused by real content while preserving the visual system.
