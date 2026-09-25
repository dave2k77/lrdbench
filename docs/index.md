<div class="lrd-home">
  <section class="lrd-hero" aria-labelledby="lrd-title">
    <div class="lrd-hero-copy">
      <p class="lrd-eyebrow">Open source · Python 3.11+ · Reproducible research</p>
      <h1 id="lrd-title">Benchmark long-range dependence with the assumptions in view.</h1>
      <p class="lrd-lede">Compare estimators on known synthetic processes, controlled contamination, and observational signals. <strong>lrdbench</strong> keeps the target estimand, uncertainty, failures, and provenance visible from run to report.</p>
      <div class="lrd-actions">
        <a class="md-button md-button--primary" href="tutorials/quickstart/">Run a first benchmark</a>
        <a class="md-button" href="benchmark_protocol/">Explore the protocol</a>
      </div>
      <p class="lrd-hero-meta">Version 2.0.0 · <a href="https://github.com/dave2k77/lrdbench">View source on GitHub</a></p>
    </div>
    <div class="lrd-hero-visual" aria-label="Benchmark workflow: source series, estimator, and mode-specific evaluation">
      <div class="lrd-visual-head"><span class="lrd-status-dot"></span> A benchmark run, made inspectable</div>
      <svg class="lrd-trace" viewBox="0 0 520 148" role="img" aria-label="Illustrative time-series trace">
        <defs><linearGradient id="trace-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#53d3bc" stop-opacity=".24"/><stop offset="1" stop-color="#53d3bc" stop-opacity="0"/></linearGradient></defs>
        <path class="lrd-grid-line" d="M0 31H520M0 74H520M0 117H520"/>
        <path fill="url(#trace-fill)" d="M0 91L13 84 25 99 39 78 52 87 66 69 78 82 91 64 104 76 117 56 130 68 143 51 156 73 169 59 182 84 195 68 208 75 221 49 234 65 247 42 260 58 273 36 286 56 299 73 312 64 325 87 338 66 351 79 364 58 377 68 390 45 403 63 416 55 429 76 442 66 455 87 468 70 481 83 494 63 507 74 520 54V148H0Z"/>
        <path class="lrd-trace-line" d="M0 91L13 84 25 99 39 78 52 87 66 69 78 82 91 64 104 76 117 56 130 68 143 51 156 73 169 59 182 84 195 68 208 75 221 49 234 65 247 42 260 58 273 36 286 56 299 73 312 64 325 87 338 66 351 79 364 58 377 68 390 45 403 63 416 55 429 76 442 66 455 87 468 70 481 83 494 63 507 74 520 54"/>
      </svg>
      <div class="lrd-flow">
        <div><span>01</span><strong>Declare the source</strong><small>Generator or observed series</small></div>
        <div><span>02</span><strong>Fit estimators</strong><small>Explicit target estimands</small></div>
        <div><span>03</span><strong>Evaluate by mode</strong><small>Metrics, failures, provenance</small></div>
      </div>
    </div>
  </section>

  <section class="lrd-section" aria-labelledby="modes">
    <div class="lrd-section-heading">
      <p class="lrd-eyebrow">One framework · Three modes</p>
      <h2 id="modes">Choose the question your data can answer</h2>
      <p>Each mode has its own evaluator. Truth-based metrics belong only where a target value is declared.</p>
    </div>
    <div class="lrd-mode-grid">
      <article class="lrd-mode-card">
        <div class="lrd-mode-number">01 / KNOWN TRUTH</div>
        <h3>Ground truth</h3>
        <p>Benchmark on canonical synthetic series with a declared target estimand.</p>
        <div class="lrd-mode-detail">Bias · MAE · RMSE · coverage</div>
        <a href="tutorials/ground_truth_benchmark/">Explore ground truth <span aria-hidden="true">→</span></a>
      </article>
      <article class="lrd-mode-card">
        <div class="lrd-mode-number">02 / CONTROLLED CHANGE</div>
        <h3>Stress test</h3>
        <p>Measure what happens when contamination challenges an estimator's assumptions.</p>
        <div class="lrd-mode-detail">Drift · degradation · validity</div>
        <a href="tutorials/stress_testing/">Explore stress tests <span aria-hidden="true">→</span></a>
      </article>
      <article class="lrd-mode-card">
        <div class="lrd-mode-number">03 / NO BENCHMARK TRUTH</div>
        <h3>Observational</h3>
        <p>Inspect stability on biomedical or user-provided signals without claiming a true Hurst value.</p>
        <div class="lrd-mode-detail">Window · preprocessing · resampling</div>
        <a href="tutorials/observational_data/">Explore observational data <span aria-hidden="true">→</span></a>
      </article>
    </div>
  </section>

  <section class="lrd-start" aria-labelledby="start">
    <div>
      <p class="lrd-eyebrow">First run</p>
      <h2 id="start">From install to a validated report</h2>
      <p>Start with the packaged smoke suite. Preview its record-by-estimator grid before running it, then validate the output directory printed by the CLI.</p>
      <p><a href="tutorials/quickstart/">Follow the full quickstart →</a></p>
    </div>
    <div class="lrd-command" aria-label="Quickstart terminal commands">
      <div class="lrd-command-top"><span></span><span></span><span></span><small>terminal</small></div>
      <pre><code>python -m pip install "lrdbench[reports]"
lrdbench run smoke_ground_truth --dry-run
lrdbench run smoke_ground_truth
lrdbench validate-output reports/&lt;run_id&gt;</code></pre>
    </div>
  </section>

  <section class="lrd-section lrd-paths" aria-labelledby="paths">
    <div class="lrd-section-heading">
      <p class="lrd-eyebrow">Find your route</p>
      <h2 id="paths">Go deeper</h2>
    </div>
    <div class="lrd-path-grid">
      <a href="interpretation_semantics/"><strong>Interpret a result</strong><span>Estimands, metric meanings, and what a leaderboard can support.</span></a>
      <a href="bundled_estimators/"><strong>Compare methods</strong><span>Browse estimator families, targets, and implementation status.</span></a>
      <a href="confirmation_benchmark/"><strong>Reproduce the research</strong><span>Follow the audited confirmation benchmark and its evidence trail.</span></a>
      <a href="adding_estimators/"><strong>Extend lrdbench</strong><span>Implement an estimator using the public contract.</span></a>
    </div>
  </section>

  <aside class="lrd-scope">
    <strong>Research scope.</strong> lrdbench is a framework for comparing estimators, not a clinical or diagnostic tool. For empirical signals, report assumptions and stability rather than treating an estimate as proof of true long-range dependence. <a href="research_usage/">Read the research usage policy →</a>
  </aside>
  <p class="lrd-footer-note">Using lrdbench in research? <a href="citation/">Cite the software</a> and review the <a href="migration/">version 2.0 migration notes</a> before comparing older results.</p>
</div>
