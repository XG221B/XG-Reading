# Shared figure-to-evidence method

## 1. Locate the paper

Define the field-level problem, the narrower unresolved question, the study's biological system, and the exact gap addressed. Separate what the field ultimately wants from what this paper actually demonstrates.

## 2. Map the material system

Before reconstructing the argument, establish what the system is made of and why it was designed that way:

- list every material, component, or functional module and the role the paper assigns to it, citing the Figure or panel that demonstrates each role;
- separate the role the authors design a component for from the role they experimentally demonstrate; a designed role needs control or functional evidence before it is stated as achieved;
- identify how the components combine and what final structure or assembly forms;
- select the paper's original structure figure with its complete caption; do not redraw, composite, or substitute a schematic;
- write two or three sentences stating what problem this material system solves and through what design.

Record this as the `materials` block in the content JSON. New tasks centered on an engineered material, device, or micro/nanorobotic system require it; a paper without such a system may omit it.

## 3. Build a claim ledger

Before writing, record for each major claim:

- exact wording of the claim;
- direct observable or measurement;
- intervention or comparison;
- negative, positive, vehicle, mock, wild-type, or reference control;
- experimental unit and biological replicate;
- sample size, normalization, uncertainty, and statistical model;
- orthogonal or independent validation;
- strongest alternative explanation still open;
- evidence level: descriptive, associative, perturbational, causal, mechanistic, translational.

Use this ledger internally. The final reader should communicate its conclusions without dumping a checklist.

Keep the ledger provisional: give every claim a stable ID, source location, evidence strength, and dependencies on other claims. Subagents receive only the claims relevant to their figure and return `supports`/`qualifies`/`challenges`/`insufficient` for those claims plus candidates for new findings (claim, panel, source basis, and any cross-figure relation the main task must check). The main task adjudicates each verdict and then updates the ledger, affected evidence blocks, and logic chain; subagents do not edit the global ledger or other figures. The context-pack and verdict protocol are defined in `references/subagent-figure-template.md`.

## 4. Reconstruct the paper-specific chain

Assign one necessary claim to each main Figure or table. Explain why the next evidence block is still needed. Begin each logic-step body with `对应Fig.x：` or the equivalent Table label, followed immediately by a colon. Do not force a standard sequence. A paper may begin with a phenotype, a cohort, a structure, a screen, a method benchmark, or a clinical observation.

## 5. Analyze each Figure

Extraction completeness is checked separately (see `references/figure-extraction.md`); this section covers scientific interpretation. When a statistic, control, or method is missing, use the evidence-status vocabulary in `references/subagent-figure-template.md` (`not_supplied`, `not_located`, `not_reported`, `reported`, plus `source_unavailable`) and word the final text for the scope actually checked. Review scope, sampling rules, and review states are defined in `SKILL.md` workflow step 9; high model confidence is not review.

### Main-figure heading

Extract the complete title from the main-figure caption and translate it accurately into Chinese. Put it directly in the centered heading before the image as `Figure X：<完整中文图题>`. Do not replace the caption title with a one-sentence interpretation, and do not repeat it after the image.

### Authors' figure-level statement

Use the caption and Results to state the authors' intended claim directly after the figure. Preserve qualifiers such as model, condition, time point, dose, and population. Do not add a visible “论文中的说法：” prompt.

### Panel titles and interpretation

For every panel or tightly linked panel group, first translate the panel-specific caption clause into a concise left-aligned title that retains the panel label. If panels are explained together, place all translated panel titles in one heading separated by a Chinese semicolon; do not split them across separate heading paragraphs.

Separate adjacent panel-title-and-interpretation groups with the retained 0.2-line blank spacer. Do not place this spacer before the first group or after the last group.

For every panel or tightly linked panel group, explain:

1. assay or visualization type;
2. axes, channels, colors, groups, time points, and units;
3. experimental and comparison groups;
4. observed direction, magnitude, variability, and distribution;
5. why that measurement supports the local claim;
6. what the statistic means and does not mean;
7. remaining alternative explanations.

Do not narrate visible pixels. Teach the reader how the data produce the conclusion.

### Fig.x summary

Write this paragraph with the visible label `Fig.x总结：`. State what prior claim it relies on, what later claim it enables, and what the paper would lose without it. Do not use “这张图在论文逻辑中的位置：”.

### Supplementary support

Integrate only material that changes confidence in the main claim: raw gates, uncropped blots, additional replicates, controls, dose/time courses, validation cohorts, sensitivity analyses, full trajectories, or negative results.

## 6. Calibrate evidence language

- Observation does not establish causality.
- Correlation does not establish direction or mechanism.
- Perturbation supports involvement but may not establish a direct target.
- Necessity and sufficiency are different claims.
- Rescue strengthens specificity only when the rescue design is appropriate.
- Colocalization does not prove molecular interaction.
- Binding does not prove downstream function.
- Pathway enrichment is hypothesis-generating unless functionally tested.
- Marker abundance does not automatically establish cell state or function.
- A reporter signal establishes functional delivery only when free reporter and cargo-independent effects are excluded; otherwise it supports presence or association at most.
- A representative image needs independent quantification.
- Endpoint distribution does not reveal a dynamic route.
- Statistical significance does not establish biological importance.
- In vitro, animal, and human evidence support different scopes of inference.

Prefer “supports”, “is consistent with”, and “suggests” unless the design directly excludes major alternatives.

## 7. Preserve evidence boundaries without adding a critique chapter

Use model boundaries, alternative explanations, and missing validation to calibrate the interpretation of the relevant Figure or claim. Do not turn these internal checks into a standalone “文章不足” section.

Apply a distinction only when it is relevant to the paper's actual wording and central evidence. In particular, do not automatically add a disease-directed displacement caveat whenever an MSD, speed, diffusion, or trajectory assay appears. Discuss directionality, net displacement, navigation, or chemotaxis only when the paper claims those properties, when the experiment is designed to test them, or when the distinction materially changes a central conclusion.

For domain-specific checks, state the claim or system the check serves, the evidence it requires, and what the evidence gap limits. Do not require checks the paper's claims do not need; see the selected module (for example `references/micro-nano-robotics.md` for micro/nanorobotic systems) for applicability.

## 8. Extract only author-grounded future outlook

Create a “未来展望” section only when the authors explicitly discuss a limitation, unresolved question, or next direction in the Discussion, Conclusion, or stated future work. State the source location and explain it in Chinese. Do not add the reader's own forecast, criticism, or proposed experiment. Omit the section when no such source exists.

## 9. Source verification

Check every major paragraph against the Figure, complete caption, and Results. Check Methods for sample definition, dose, timing, replicate, model, processing, statistics, exclusions, randomization, and blinding. State “uncertain” when the source does not resolve a point.

When a source element is missing, distinguish `not_supplied` (not provided to the analysis), `not_located` (not found within the material checked), `not_reported` (confirmed absent after checking the main text, Methods, and available supplements), and `source_unavailable` (the supplement itself was not obtained; this does not establish that the method is unreported). Request the specific missing item, record the scope checked, and use the wording that matches that scope: “当前可获取材料未说明……”, “在已核对的 Methods 与补充材料中未找到……”, or “原文未报告” only when the checked scope is sufficient. A missing input is not a paper deficiency.
