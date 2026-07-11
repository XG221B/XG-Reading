# Omics and computational biology

## Identify the experimental unit

Determine whether `n` means patients, animals, biological samples, pooled cells, libraries, batches, fields, or individual cells. Cells from one sample are not independent biological replicates.

## Quality and preprocessing

- Check sample inclusion, sequencing depth, mapping or identification quality, missingness, doublets, ambient RNA, normalization, filtering, and batch correction.
- Determine whether preprocessing choices were fixed before outcome analysis.
- Inspect whether batch, treatment, tissue, subject, and platform are confounded.

## Statistical inference

- Check multiple-testing correction and effect size, not only nominal `P` values.
- For differential analysis, verify the model respects pairing, repeated measures, donor structure, and covariates.
- For clustering, assess parameter sensitivity, stability, and whether labels were circularly assigned from selected markers.
- For trajectory or pseudotime, treat ordering as model-based inference unless independently validated over real time.
- For cell-cell communication, regulons, pathways, and enrichment, treat results as hypotheses until supported by perturbation or orthogonal evidence.

## Prediction and machine learning

- Separate training, validation, and external test sets.
- Check leakage, class imbalance, calibration, uncertainty, baseline fairness, hyperparameter tuning, and repeated splits.
- Distinguish internal cross-validation from external generalization.
- Check whether interpretability plots establish biological mechanism or only model dependence.

## Validation hierarchy

Prefer independent cohorts, alternative platforms, targeted assays, spatial validation, perturbation, functional experiments, and prospective testing. Reanalysis of the same samples is not independent validation.

## Common overclaims

- biological mechanism inferred solely from enrichment;
- new cell type inferred from unstable clustering;
- temporal development inferred solely from pseudotime;
- clinical utility inferred from internal accuracy;
- causal biomarker inferred from predictive importance.
