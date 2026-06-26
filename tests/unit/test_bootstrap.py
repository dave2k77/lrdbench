from __future__ import annotations

import numpy as np

from lrdbench.bootstrap import symmetric_percentile_cis


def test_symmetric_percentile_cis_uses_nominal_confidence_level() -> None:
    samples = np.arange(101, dtype=float)

    cis = symmetric_percentile_cis(samples, (0.95,))

    np.testing.assert_allclose(np.asarray(cis), np.asarray(((0.95, 2.5, 97.5),)))


def test_symmetric_percentile_cis_sorts_deduplicates_and_skips_invalid_levels() -> None:
    samples = np.arange(11, dtype=float)

    cis = symmetric_percentile_cis(samples, (0.80, 1.0, 0.50, 0.80, -0.1))

    np.testing.assert_allclose(
        np.asarray(cis),
        np.asarray(
            (
                (0.50, 2.5, 7.5),
                (0.80, 1.0, 9.0),
            )
        ),
    )
