# OpenNeuro ds002691 EEG Observational Pilot Analysis

This note summarizes the first real open-data EEG observational pilot run for `lrdbench`. It is intended as discussion-ready material for the benchmark manuscript and should be interpreted within observational-mode limits: the run has no benchmark ground truth, so it supports workflow, stability, uncertainty-width, disagreement, and sensitivity claims, not estimator-accuracy or confidence-interval coverage claims.

## Dataset and run shape

| Field | Value |
| --- | --- |
| Dataset | OpenNeuro `ds002691`, internal-attention EEG study |
| DOI | `10.18112/openneuro.ds002691.v1.1.0` |
| License | CC0 |
| Manifest | `openneuro_ds002691_pilot_v1` |
| Mode | `observational` |
| Run ID | `3762d43d-5610-4ce2-a931-bf11aac9317a` |
| Subjects | 4 (`sub-001` to `sub-004`) |
| Channels | 4 (`E1`, `E8`, `E16`, `E24`) |
| Records | 16 |
| Sampling rate | 250 Hz |
| Samples per record | 2,500 |
| Window duration | 10 seconds |
| Estimator variants | 12 |
| Fit jobs | 192 |
| Benchmark truth | None |

The full local report is stored at:

```text
reports/openneuro_ds002691_pilot/3762d43d-5610-4ce2-a931-bf11aac9317a
```

Compact manuscript-oriented summaries are stored at:

```text
benchmark_experiment/results/openneuro_ds002691_pilot/
```

## Primary result

The pilot demonstrates that `lrdbench` can ingest a real public EEG corpus, convert selected EEG windows into observational CSV records, preserve subject/channel/source/QC metadata, and produce truth-free estimator summaries across validity, runtime, uncertainty width, instability, estimator disagreement, family disagreement, and scale/window sensitivity.

The strongest safe claim is workflow-oriented:

> On a CC0 OpenNeuro EEG pilot, `lrdbench` observational mode processed 16 real EEG windows from four subjects and four channels, preserved study/source/QC metadata, produced valid estimates for all 192 estimator fits, and exposed substantial estimator-family disagreement despite universal fit validity.

This is useful manuscript evidence because it shows that the benchmark framework extends beyond synthetic ground-truth experiments into real observational neurophysiology while retaining explicit interpretive boundaries.

## Run health and validation

All estimator variants produced valid fits on all records.

- Manifest validation: passed.
- Output contract validation: passed with contract version `1.0.0`.
- Estimator validity rate: 1.0 for every estimator variant.
- Full repository test suite after adding the pilot: 191 passed, 1 pre-existing notebook warning.

The single warning came from a research notebook using a non-interactive Matplotlib backend and is not specific to the EEG pilot.

## Truth-free leaderboard

The observational leaderboard ranks estimator variants by stability/runtime/validity components. Because every estimator achieved validity 1.0, the ranking is driven mainly by instability and runtime. It is not an accuracy ranking.

| Rank | Estimator | Score | Mean instability | Mean runtime (s) | Validity rate |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | `DFA::balanced_scales` | 2.95 | 0.0270 | 0.0064 | 1.0 |
| 2 | `DFA::short_scales` | 4.85 | 0.0334 | 0.0123 | 1.0 |
| 3 | `AbsoluteMoment` | 5.05 | 0.0742 | 0.00036 | 1.0 |
| 4 | `Higuchi` | 5.30 | ~0.0000 | 0.0206 | 1.0 |
| 5 | `RS` | 5.90 | 0.0228 | 0.0191 | 1.0 |

A conservative interpretation is that DFA variants are strong observational choices in this pilot because they combine full validity, low instability, and moderate runtime. This should be phrased as stability under the pilot configuration, not estimator accuracy.

## Uncertainty-width patterns

Mean confidence-interval width varied materially by estimator.

Narrowest mean CI widths:

| Estimator | Mean CI width |
| --- | ---: |
| `Higuchi` | 0.0000 |
| `RS` | 0.0805 |
| `DFA::balanced_scales` | 0.0884 |
| `GHE` | 0.1024 |
| `VarianceResidual` | 0.1046 |
| `DFA::short_scales` | 0.1193 |

Widest mean CI widths:

| Estimator | Mean CI width |
| --- | ---: |
| `DMA::balanced_windows` | 0.2669 |
| `Variance` | 0.2784 |
| `AbsoluteMoment` | 0.2816 |

These values support an uncertainty-width comparison only. Without known benchmark truth, they do not support empirical CI coverage claims. Higuchi's zero-width uncertainty should be treated cautiously because very narrow or degenerate uncertainty can reflect estimator/reporting behavior rather than meaningful calibration.

## Instability patterns

Lowest mean instability:

| Estimator | Mean instability |
| --- | ---: |
| `Higuchi` | 0.0000 |
| `RS` | 0.0228 |
| `DFA::balanced_scales` | 0.0270 |
| `VarianceResidual` | 0.0285 |
| `GHE` | 0.0285 |
| `DFA::short_scales` | 0.0334 |

Highest mean instability:

| Estimator | Mean instability |
| --- | ---: |
| `WaveletOLS::broad_band` | 0.0593 |
| `DMA::balanced_windows` | 0.0687 |
| `Variance` | 0.0724 |
| `AbsoluteMoment` | 0.0742 |

Temporal estimators were generally stable in this pilot. However, extremely low instability should not be over-interpreted as accuracy. In particular, flat or saturating behavior can look stable while still being scientifically misleading.

## Runtime patterns

All estimators were fast on 10-second windows. Runtime was therefore not a limiting factor for this pilot.

Fastest mean runtimes:

| Estimator | Mean runtime (s) |
| --- | ---: |
| `Variance` | 0.000307 |
| `AbsoluteMoment` | 0.000356 |
| `WaveletOLS::conservative_band` | 0.000901 |
| `WaveletOLS::broad_band` | 0.001068 |
| `DFA::balanced_scales` | 0.006412 |

Slowest mean runtimes:

| Estimator | Mean runtime (s) |
| --- | ---: |
| `RS` | 0.0191 |
| `Higuchi` | 0.0206 |
| `DMA::balanced_windows` | 0.0207 |
| `DMA::short_windows` | 0.0212 |
| `GHE` | 0.0494 |

Scaling to more subjects, channels, or windows should be feasible, although full-corpus analyses should still be staged and cached.

## Estimator disagreement

Estimator disagreement was one of the clearest scientific observations from the pilot.

Overall cross-estimator dispersion:

- Mean: 0.2714.
- Median: 0.2564.

Within-family disagreement:

| Family | Mean disagreement |
| --- | ---: |
| Temporal | 0.0782 |
| Wavelet | 0.1126 |
| Geometric | 0.7880 |

Between-family disagreement:

| Comparison | Mean disagreement |
| --- | ---: |
| Geometric vs temporal | 0.3940 |
| Geometric vs wavelet | 0.4493 |
| Temporal vs wavelet | 0.4820 |

This supports a useful discussion point: real EEG observational LRD summaries depend strongly on estimator family and scale assumptions. A single unqualified Hurst/fractal estimate would hide this disagreement. Reporting disagreement and sensitivity alongside point estimates is therefore a core methodological contribution of the benchmark workflow.

## Parameter and scale/window sensitivity

Mean maximum variant drift:

| Estimator family | Mean max variant drift |
| --- | ---: |
| DFA | 0.0506 |
| DMA | 0.0590 |
| WaveletOLS | 0.1126 |

Mean parameter-variant sensitivity:

| Estimator family | Mean sensitivity |
| --- | ---: |
| DFA | 0.0253 |
| DMA | 0.0295 |
| WaveletOLS | 0.0563 |

WaveletOLS showed larger band-choice sensitivity than DFA or DMA showed scale/window sensitivity in this pilot. This supports including scale-band sensitivity as a standard observational diagnostic.

## Preprocessing sensitivity

The configured preprocessing-sensitivity diagnostic was 0.0 for all estimator variants in this compact pilot. That is consistent with the simple current preprocessing setup, which uses demeaned 10-second windows and does not yet compare substantive EEG preprocessing choices.

This should be interpreted narrowly. It does not show that EEG LRD estimates are insensitive to preprocessing in general. A future expanded pilot should explicitly compare filtering, referencing, artifact rejection, channel selection, and window duration.

## Channel-level patterns

Across the four selected channels, temporal/moment/DFA/DMA estimates were generally high, often around 0.8 to 1.0, while GHE and WaveletOLS estimates were much lower.

Examples:

- `E1`: DFA variants, Higuchi, and VarianceResidual were near 0.9999; RS mean was 0.9394; GHE mean was 0.3301; WaveletOLS broad-band mean was 0.1962.
- `E16`: AbsoluteMoment mean was 0.9260; RS mean was 0.8859; DFA balanced mean was 0.8502; GHE mean was 0.1711; WaveletOLS broad-band mean was 0.4963.
- `E24`: RS mean was 0.9312; Variance mean was 0.9300; DFA balanced mean was 0.9575; GHE mean was 0.1943; WaveletOLS broad-band mean was 0.4074.
- `E8`: DMA short-window mean was 0.9587; Variance mean was 0.9502; RS mean was 0.8860; GHE mean was 0.1519; WaveletOLS broad-band mean was 0.5370.

The channel summaries reinforce the family-disagreement result. Apparent LRD strength in real EEG depends heavily on the estimator definition and selected scale range.

## Discussion-ready interpretation

This pilot is best framed as a real-data workflow and diagnostic demonstration rather than a truth-based estimator benchmark. It shows that the same infrastructure used for synthetic ground-truth and stress-test experiments can handle open observational EEG while preserving metadata and reporting the diagnostics needed to avoid overclaiming.

Suggested manuscript language:

> In a CC0 OpenNeuro EEG pilot, observational mode processed 16 real EEG windows from four subjects and four channels, preserving source, subject, channel, sampling-rate, preprocessing, and QC metadata. All 192 estimator fits were valid, but estimator-family disagreement was substantial, with temporal, wavelet, and geometric estimators producing materially different summaries. These results demonstrate the need for observational LRD reports to include validity, uncertainty width, runtime, estimator disagreement, and scale/window sensitivity rather than reporting a single unqualified Hurst estimate.

## Claims supported by this pilot

The pilot supports the following claims:

- `lrdbench` can ingest and evaluate real open EEG data in observational mode.
- Subject, channel, source, sampling-rate, preprocessing, and QC metadata are preserved into output artifacts.
- All estimator variants completed successfully on the pilot subset.
- Truth-free diagnostics expose meaningful differences among estimators even when validity is uniformly high.
- Estimator-family disagreement is substantial on real EEG windows.
- Wavelet band choice was more sensitive than the tested DFA/DMA scale/window variants in this pilot.
- The observational workflow is suitable for manuscript discussion as a real-data complement to synthetic truth-based benchmark results.

## Claims not supported by this pilot

The pilot does not support the following claims:

- Any estimator is most accurate on these EEG records.
- The EEG records have a known true LRD/Hurst value.
- Confidence intervals have valid empirical coverage.
- Higuchi's zero instability or zero CI width implies superior scientific reliability.
- The observed values generalize to all EEG preprocessing choices, tasks, channels, or clinical populations.

## Recommended next steps

1. Use this pilot as the manuscript's real-data observational demonstration.
2. Keep synthetic ground-truth claims separate from observational EEG claims.
3. If more empirical depth is needed, expand the pilot by adding longer windows, more channels, and explicit preprocessing comparisons.
4. For any expanded run, continue reporting estimator disagreement and scale/window sensitivity as first-class outcomes.
5. Publish compact summaries in git and archive full row-level reports separately if externally cited.
