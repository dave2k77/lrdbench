# Independent confirmation audit

This package is separate from the frozen producer sources. It reads the completed
confirmation archive without modifying its inputs, estimates, draws or summaries.
It does not import the producer's reader, estimator, interval or summary functions.

Audit specification (recorded before the full results inspection):

* Verify run/design identities, every chunk file checksum, the full declared
  parent/condition/method grid, signal hashes, exact integer seed derivations,
  parent links, analyzed-input hashes, settings and targets.
* Replay every contamination from its stored clean parent using the declared
  equations. Parent simulation and estimator equations were tested in the
  earlier implementation/rehearsal packages; this audit does not refit all points.
* Inspect every aligned within-record statistic value and its failure accounting;
  reconstruct every interval endpoint from those values, including GPH's normal
  interval and the fitted-H center for the model bootstrap.
* Recompute every cell's observed metric, support, paired contrast and applicable
  Monte Carlo standard error directly from the raw records. Use the explicit
  Wilson formula for cell proportions.
* Recreate parent selections for all 1,999 summary resamples, then independently
  reconstruct draws at 31 fixed, evenly spaced indices (including both ends),
  using literal row gathering rather than the producer's count-matrix method.
  Check all columns at these positions. This is a deterministic sample of draw
  reconstruction, not a claim to rerun every summary resample from raw records.
* Inspect every saved summary draw for availability and recompute every saved
  percentile interval and bootstrap standard error. Independently reconstruct
  every domain aggregate and all 1,999 of its draw positions from the cell
  results, including ratios of weighted MAEs and square roots of weighted MSEs.
* Verify canonical export against every component row. Report all declared cells
  and contrasts; do not select a new method, scenario or stopping rule from the
  confirmation outcomes.

Numerical comparisons allow floating-point summation differences (relative
`2e-10`, absolute `2e-12`); identifiers, counts, finite masks, seeds and hashes
must agree exactly. Contamination replay tolerance is `2e-14`. Tests exercise
unavailable intervals, pairing, ratio aggregation and corruption detection.

The authoritative scientific design remains `protocol-v1/scientific_design_lock.json`.
This audit does not amend it. Summary uncertainty is Monte Carlo uncertainty of
the simulation study, distinct from the within-record intervals being evaluated.
