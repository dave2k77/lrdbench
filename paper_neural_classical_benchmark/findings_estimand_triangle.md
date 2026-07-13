# Findings: the H / β / τ estimand triangle

**Suite:** `neural_timescale_triangle_ground_truth`  ·  **run_id:** `795db58e-83e5-4c74-a25f-0fe999428325`
**Config:** 50 records (fGn H∈{0.6,0.7,0.8,0.9} + fOU H∈{0.5,0.7,0.9} × θ∈{0.05,0.20}), n=2048,
5 replicates, block-bootstrap 95% CIs (200 resamples), `global_seed=20260713`.

## Why

The neural-timescales / long-range-dependence literature treats the Hurst exponent (H), the
spectral slope (β, `S(f)~f^(-β)`) and the autocorrelation-decay timescale (τ) as three views of the
same temporal-correlation structure, and warns that **true long-range dependence can masquerade as a
long characteristic timescale**. This is the first `lrdbench` run in which those three estimands are
first-class, individually ground-truthed, and scored on the *same* realisations — so we can measure
that confound instead of asserting it.

## Result 1 — Hurst estimators trade clean-signal accuracy for robustness

Mean absolute error against the H truth, split by generating process:

| Estimator | fGn (stationary) | fOU (mean-reverting) |
|---|---|---|
| WhittleMLE | **0.024** | 0.279 |
| DFA | 0.034 | 0.233 |
| GPH | 0.130 | **0.103** |

WhittleMLE and DFA are near-exact on clean fGn but collapse under mean reversion (fOU suppresses
large-scale scaling); GPH is the most robust to fOU but the weakest on fGn. Estimator choice is a
signal-dependent trade-off, not a global ranking.

## Result 2 — the timescale estimator inflates under true LRD (the confound, quantified)

Median ACF-decay `τ̂` vs the fOU mean-reversion truth `τ* = 1/(θ·dt)`:

| H | θ | τ\* | median τ̂ | MAE |
|---|---|---|---|---|
| 0.5 | 0.05 | 20.0 | **19.7** | 4.2 |
| 0.5 | 0.20 | 5.0 | **4.7** | 0.4 |
| 0.7 | 0.05 | 20.0 | 34.4 | 32.0 |
| 0.7 | 0.20 | 5.0 | 12.4 | 9.1 |
| 0.9 | 0.05 | 20.0 | 69.6 | 108.0 |
| 0.9 | 0.20 | 5.0 | 55.3 | 82.0 |

At H=0.5 (plain OU) the estimator recovers τ\* almost exactly. As the driving process gains long-range
dependence the fitted timescale inflates monotonically — at **H=0.9 it reports a timescale ≈3.5× too
long** (69.6 vs 20). This is the literature's central methodological warning reproduced as a number:
an intrinsic-timescale estimate applied to a persistent signal overstates the timescale in proportion
to the underlying LRD.

## Caveat surfaced by the run

95% CI coverage is poor across all estimators (~0.35–0.53 vs nominal 0.95): the point estimators are
biased on these processes and the block-bootstrap intervals are too narrow to cover. This is a real,
reportable calibration finding, not an implementation artefact — and motivates bias-corrected or
wider-interval uncertainty for downstream neural applications.

## Reproduce

```bash
lrdbench run configs/suites/neural_timescale_triangle_ground_truth.yaml
```

Per-estimand truths (H, β=2H−1, τ=1/(θ·dt)) are recorded in `raw/truths.csv`; each estimator is
scored only against the truth for its own `target_estimand`. Convention and recovery are covered by
`tests/unit/test_estimand_triangle.py`.

---

# Findings: true-vs-apparent LRD discrimination

**Suite:** `neural_lrd_discrimination_ground_truth`  ·  **run_id:** `4498cb3a-265d-4e41-8f15-b6c9e53f82e1`
**Config:** multi_timescale nulls (τ_max∈{4,8,16}) + fGn H=0.5 null + fGn H∈{0.7,0.8} true-LRD
positives, n=2048, 8 replicates, block-bootstrap 95% CIs (200 resamples), `global_seed=20260713`.

## Why

Result 2 above showed a *timescale* estimator inflating under true LRD. The dual question is whether
*Hurst* estimators are fooled the other way — reporting long-range dependence for signals that have
none. The `multi_timescale` generator is a finite superposition of AR(1) components: provably
short-memory (summable ACF, truth H=0.5) but engineered to mimic power-law scaling over finite
samples, with severity graded by `tau_max`. `false_positive_lrd_rate` scores how often each estimator
calls H ≥ 0.6 on these H=0.5 nulls.

## Result 3 — most estimators cannot tell apparent LRD from real LRD

False-positive rate (fraction calling H ≥ 0.6 on a true-H=0.5 null):

| Null source (truth H=0.5) | GPH | DFA | RS | WaveletOLS | WhittleMLE |
|---|---|---|---|---|---|
| fGn (honest short-memory) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| multi-timescale, τ_max=4 | **0.00** | 0.88 | 1.00 | 1.00 | 1.00 |
| multi-timescale, τ_max=8 | **0.00** | 1.00 | 1.00 | 1.00 | 1.00 |
| multi-timescale, τ_max=16 | 0.62 | 1.00 | 1.00 | 1.00 | 1.00 |

Median Hurst estimate per group (nulls should read 0.5; fGn 0.7/0.8 is genuine LRD):

| Group | GPH | DFA | RS | WaveletOLS | WhittleMLE |
|---|---|---|---|---|---|
| fGn H=0.5 (null) | 0.52 | 0.47 | 0.54 | 0.49 | 0.49 |
| multi-τ τ_max=4 | 0.51 | 0.64 | 0.69 | 0.78 | 0.76 |
| multi-τ τ_max=8 | 0.56 | 0.76 | 0.73 | 0.90 | 0.93 |
| multi-τ τ_max=16 | 0.63 | 0.89 | 0.79 | **1.00** | **0.99** |
| fGn H=0.7 (real LRD) | 0.63 | 0.67 | 0.69 | 0.70 | 0.69 |
| fGn H=0.8 (real LRD) | 0.66 | 0.83 | 0.80 | 0.77 | 0.82 |

Four points:

1. **The nulls are honest.** Every estimator scores 0.00 false positives on clean fGn H=0.5 — the
   failures below are specific to the multi-timescale illusion, not general trigger-happiness.
2. **Four of five estimators are fully fooled.** RS, WaveletOLS and WhittleMLE fire false positives at
   100% across every severity; DFA at 88–100%. Genuinely short-memory data is read as LRD almost
   always.
3. **GPH is the standout discriminator** (0% false positives until the most severe setting, then
   62%): the low-frequency log-periodogram slope resists the confound far better than DFA / RS /
   wavelet / Whittle.
4. **Apparent LRD can look stronger than real LRD.** WaveletOLS and WhittleMLE report median H ≈
   0.99–1.00 on the short-memory nulls at τ_max=16 — *higher* than on genuine fGn LRD (H ≈ 0.7–0.8).
   By point estimate alone, a superposition of short timescales is not merely indistinguishable from
   long-range dependence; it can masquerade as more persistent than the real thing.

## Takeaway for neural applications

A single scaling estimate is not evidence of long-range dependence. Reporting 1/f-type "scale-free"
neural dynamics from DFA / wavelet / Whittle alone cannot rule out a short-memory multi-timescale
generator — which is a physiologically plausible alternative (a hierarchy of exponential neural
timescales). GPH is comparatively robust, but the safe practice is an explicit short-memory null model
and a discrimination test, not a point Hurst estimate.

## Reproduce

```bash
lrdbench run configs/suites/neural_lrd_discrimination_ground_truth.yaml
```

The `multi_timescale` generator declares the H=0.5 null truth (annotations record `tau_max` /
`beta_target`); `false_positive_lrd_rate` counts only null records. Generator properties and
apparent-LRD tunability are covered by `tests/unit/test_multitimescale.py`.

---

# Findings: per-series LRD model selection (Phase 3a baseline)

**Suite:** `neural_lrd_model_selection_ground_truth`  ·  **run_id:** `3fc3bf64-c325-4470-b009-abb1d4ca5a06`
**Config:** true-LRD positives (fGn H∈{0.6,0.7,0.8,0.9}, ARFIMA d∈{0.2,0.4}) vs short-memory nulls
(fGn H=0.5, ARFIMA d=0, and multi_timescale τ_max∈{4,8,16}), n=2048, 8 replicates,
`global_seed=20260713`. 88 series, 48 positive.

## Why

Result 3 measured a population *false-positive rate*. The operational question for a practitioner is
per-series: given *this* recording, is it long-range dependent or short-memory? A discriminator emits
a score in [0,1] for a new `lrd_class` estimand; ROC-AUC scores how well that score separates the two
classes. Phase 3a builds the machinery and the naive baseline — a Hurst estimate squashed through a
logistic (`ThresholdHurstDiscriminator`, DFA base) — to set the floor.

## Result 4 — a single scaling estimate has no power against the real adversary

Population metrics for the baseline discriminator:

| ROC-AUC | balanced acc. | TPR | FPR |
|---|---|---|---|
| 0.72 | 0.68 | 0.96 | 0.60 |

Mean score and "called LRD" rate by class (threshold 0.5):

| Class | mean score | called LRD |
|---|---|---|
| fGn H=0.5 (honest null) | 0.19 | 0% |
| ARFIMA d=0 (honest null) | 0.23 | 0% |
| multi-τ τ_max=4 (apparent-LRD null) | 0.87 | 100% |
| multi-τ τ_max=8 (null) | 0.97 | 100% |
| multi-τ τ_max=16 (null) | 0.997 | 100% |
| fGn H=0.6–0.9 (real LRD) | 0.59–0.999 | 75–100% |
| ARFIMA d=0.2–0.4 (real LRD) | 0.93–0.999 | 100% |

The overall AUC of 0.72 is a mirage. Split by adversary:

```
ROC-AUC vs honest nulls only (fGn 0.5, ARFIMA d=0):   1.00   -- solved
ROC-AUC vs multi-timescale adversary only:            0.54   -- ~chance
```

The baseline perfectly separates true LRD from *honest* short-memory but is **at chance** against the
multi-timescale confound — its scores on apparent-LRD nulls (0.87–0.997) equal or exceed those on
genuine LRD. A point scaling estimate, however it is thresholded, carries essentially zero
discriminating power against the one alternative that matters.

## Takeaway and the Phase 3b target

Model selection cannot be reduced to a Hurst threshold. The **AUC ≈ 0.54 on the true-LRD-vs-
multi-timescale subset is the floor** that principled discriminators must beat: (i) information-
criterion / likelihood-ratio comparison of an LRD model against a short-memory AR(p); (ii) scale-
dependence (crossover) of the local scaling exponent; (iii) low-frequency spectral behaviour
(motivated by GPH's robustness in Result 3). These are Phase 3b.

## Reproduce

```bash
lrdbench run configs/suites/neural_lrd_model_selection_ground_truth.yaml
```

Discriminators emit a [0,1] score for the `lrd_class` estimand; generators attach binary `is_lrd`
labels via companion truths (`raw/truths.csv`). Classification metrics (`roc_auc`,
`balanced_accuracy`, `true_positive_rate`, `false_positive_rate`) are routed by estimand kind so
regression error metrics never apply to a decision estimand. Covered by
`tests/unit/test_lrd_model_selection.py`.

---

# Findings: principled LRD discriminators (Phase 3b)

**Suite:** `neural_lrd_model_selection_ground_truth`  ·  **run_id:** `51394031-5d50-417b-8a06-1141eba1eac2`
**Config:** as Phase 3a, adding three principled discriminators alongside the baseline; 88 series,
n=2048, 8 replicates, 100-resample bootstrap, `global_seed=20260713`.

## Why

Result 4 set the floor: a point Hurst estimate scores AUC ~0.54 (chance) against the multi-timescale
confound. Phase 3b asks whether discriminators that inspect the *right* feature can do better. Three
strategies, each emitting a score for the `lrd_class` estimand:

- **ICModelSelect** — summed-Whittle BIC of ARFIMA(0,d,0) versus short-memory AR(1)/AR(2); score
  favours LRD when the fractional model wins.
- **LowFreqSpectral** — local-Whittle memory parameter at a shrinking low-frequency band; true LRD
  keeps `d>0` as f→0 whereas a bounded (short-memory) spectrum collapses to `d≈0`.
- **ScaleCrossover** — slope of the DFA fluctuation curve restricted to large scales; LRD stays above
  0.5 at all scales, a multi-timescale process crosses over to 0.5 beyond its largest timescale.

## Result 5 — inspecting the right feature solves what a Hurst threshold cannot

ROC-AUC, overall and decomposed by adversary:

| Discriminator | AUC (all) | AUC vs honest nulls | AUC vs multi-timescale |
|---|---|---|---|
| ThresholdHurst (baseline) | 0.72 | 1.00 | **0.54** |
| ScaleCrossover | 0.83 | 0.97 | **0.73** |
| LowFreqSpectral | 0.87 | 0.89 | **0.87** |
| ICModelSelect | 0.98 | 0.95 | **1.00** |

1. **All three principled discriminators beat the baseline floor on the adversary**, ranked
   IC > LowFreq > Crossover. The problem that a point scaling estimate could not touch (0.54) is
   solved.
2. **IC model comparison separates the classes perfectly** (AUC 1.00 vs multi-timescale): the
   Whittle-BIC correctly recognises that a multi-timescale superposition is better explained by a
   short-memory AR(p) than by a fractionally-integrated model.
3. **LowFreqSpectral is the most uniform** (0.89 honest vs 0.87 adversary) — it barely depends on
   which null it faces because it measures the one thing that genuinely differs: whether the memory
   parameter survives as f→0. This vindicates GPH's robustness in Result 3.
4. **The crossover geometry is a real but weaker signal** (0.73) — the DFA slope does drop at large
   scales for short-memory data, but more noisily than the spectral / likelihood approaches detect it.

## Takeaway

The through-line of the project: a single Hurst number cannot distinguish long-range dependence from a
hierarchy of short timescales, but a model-selection test can — and the framework now measures exactly
that, per series, end to end. For neural applications this argues for reporting a discrimination score
(ideally an explicit LRD-vs-short-memory model comparison) rather than a point scaling exponent when
claiming scale-free dynamics.

## Reproduce

```bash
lrdbench run configs/suites/neural_lrd_model_selection_ground_truth.yaml
```

The four discriminators are registered estimators (`ThresholdHurstDiscriminator`,
`LowFreqSpectralDiscriminator`, `ScaleCrossoverDiscriminator`, `ICModelSelectDiscriminator`); each
beats the ~0.54 floor on the hard subset in `tests/unit/test_lrd_model_selection.py`.
