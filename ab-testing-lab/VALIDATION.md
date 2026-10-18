# Validation record

Validated on **16 October 2026**. **78/78 automated checks passed.** These are assertions across selected numerical scenarios, not 78 independent experiments or an exhaustive proof.

## Exact documented baseline

- Application: documented single-file browser release with shared two-sided/one-sided selection, directional bounds, negative-effect planning, half-unit sliders, precise number entry, compact layout and three chart views.
- HTML SHA-256: `4b8e17aa7ce8119526593871f2e949016e223494c9b5e9cc2d181b76a3e4c1a6`
- Statistical-script SHA-256 (the text between its script tags): `09954f33175a2745e1ee85e1087d6c9969e49646d7c0e33250f7f0333519be0d`
- This documentation package contains no replacement app file. The hash identifies the HTML used for validation, not a verified current deployment.
- Full machine-readable output: [validation-results.json](validation-results.json).

## Environment

| Tool | Recorded version |
| --- | --- |
| Python | 3.12.14 |
| Node.js | v24.19.0 |
| NumPy | 2.3.5 |
| SciPy | 1.17.0 |
| statsmodels | 0.15.0 |

Node executes the actual inline `lab-statistics` source extracted from the chosen HTML. Python independently computes references and calls library functions. There is no npm or DOM dependency in the numerical runner, no live API call, and no change to the app file.

## What the checks cover

| Area | Coverage / acceptance criterion |
| --- | --- |
| Normal CDF | 321 z-values from −8 to +8, maximum absolute error < 1e−7 against SciPy |
| Normal inverse CDF | 13 probabilities from .0005 to .9995; maximum absolute error < 1e−4 in z units |
| Planning power | Fourteen scenarios: both directional alternatives and two-sided, positive/negative/zero effects, opposite directions, unequal n, low rates, different α; absolute power difference < 2e−6 against SciPy and statsmodels |
| Standard errors and cutoffs | SE difference < 1e−12; absolute cutoff difference < 1e−7 in proportion units |
| Complements | Calculated power + β = 1; α/confidence algebraic identity |
| Planning | Eight designs meet desired power; immediately smaller candidate control n fails under the same rounded allocation rule |
| Relationships | Higher desired power and smaller effect magnitude increase n; stricter α reduces fixed-n power |
| Observed analysis | Fifteen tables, including directional alternatives, normal and sparse cases, both-zero and both-all-event counts, zero control and tiny n |
| Test references | Selected-direction pooled z versus statsmodels; matching-tail Fisher versus SciPy; absolute p difference < 2e−6 |
| CI reference | Central Newcombe intervals and ordinary one-sided finite bounds versus statsmodels, absolute endpoint difference < 2e−6; unusual confidence ≤50% uses an independently calculated signed-Wilson formula, not a library coverage guarantee |
| Binomial random generator | Empirical means/variances for n=10, 1,000 and 100,000, 20,000 draws each; count validity and p=0/1 boundaries |
| Long-run calibration | 100,000 total: 20,000 each in three two-sided scenarios; 10,000 each in four directional null/alternative scenarios |
| Revenue generator | 200,000 synthetic users: mean agrees within 5 theoretical Monte Carlo SEs and zero mass within .01 |
| Invalid engine inputs | Negative/excess/fractional counts, n<2, invalid planning rates, zero planning effect |

The α/confidence identity is an algebra check, not an automated test of slider layout or accessibility. Integer planning minimality is checked against the app's own power model; the separate reference comparisons validate that power calculation on selected cases.

## Selected repeated-experiment results

All scenarios below use α = 5% and baseline 20%. Simulations use deterministic validation seeds; the interactive app's simulation uses unseeded `Math.random()`.

| Test / scenario | Control / treatment n | Repetitions | Nominal/reference rejection rate | Observed rejection rate |
| --- | --- | --- | --- | --- |
| two-sided / null boundary | 5,000 / 5,000 | 20,000 | 5.0000% | 5.12% |
| two-sided / +5% relative | 25,583 / 25,583 | 20,000 | 80.0013% | 80.03% |
| two-sided / −5% relative | 24,641 / 24,641 | 20,000 | 80.0011% | 79.87% |
| greater / null boundary | 5,000 / 5,000 | 10,000 | 5.0000% | 4.80% |
| less / null boundary | 5,000 / 5,000 | 10,000 | 5.0000% | 5.16% |
| greater / +5% relative | 20,000 / 20,000 | 10,000 | 79.7377% | 79.28% |
| less / −5% relative | 20,000 / 20,000 | 10,000 | 81.0351% | 80.54% |

At H₀ the reference is nominal α. At H₁ it is the SciPy normal-model power approximation. The tolerance is five Monte Carlo SEs plus .003 absolute probability to allow for a modest planning-versus-observed-test discrepancy. This is a sanity check, not proof that rejection is exact at every event rate or tiny sample. No sparse tables occurred in these seven large-sample scenarios; exact-test correctness is checked separately on selected sparse tables.

The recorded CDF error is about 7.41e−8. The recorded inverse-CDF error is about 3.32e−5 in z units. These explain why browser outputs need not match a reference calculator in every last digit. Floating-point tolerances are explicit; tests should not be loosened silently after a failure.

## Reproduce

Place these files beside the **actual** project `index.html` and install Python 3.12 plus Node.js 18+:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-validation.txt
python validate_statistics.py --html index.html --report validation-results.json
```

The runner prints PASS/FAIL lines and returns a non-zero exit code for failed checks. Missing files/dependencies or a JavaScript runtime error also fail the run. It can take tens of seconds depending on the computer. Running it again overwrites the report only when `--report` is supplied; it does not update this Markdown record automatically. After a code change, review any new failures and update the report, hashes and narrative together.

## Not established by these checks

- Real-browser rendering, screenshot appearance, pointer events, mobile layout, chart overlap, keyboard accessibility, contrast or screen-reader usability. Manual browser checks should cover all four tabs, positive/negative effects, all test directions, comparison mode, keyboard and number inputs, chart labels, simulation reruns and invalid-input messages.
- Whether the newest HTML is currently published, DNS/hosting health or external Plotly CDN availability.
- Exact binomial power, correct calibration at all sparse/extreme settings, exhaustive Fisher enumeration or CI coverage over all parameters.
- Valid randomisation, outcome measurement, no interference, appropriate stopping rules or business value for a real experiment.
- A formal proof of the custom random generator or a cryptographic randomness assessment.
- A test of a separate Python/Streamlit application; this runner tests the browser statistical engine.

## Known limitations to keep visible

1. Planning uses fixed normal-model variances; observed z/Fisher procedures differ in finite samples.
2. Newcombe CI and z/Fisher p-values are not method inverses; their decisions can differ near a boundary.
3. Dynamic cards qualify zero/opposite-direction effects, but some generic power/β controls and the static dependency map remain framed for a true alternative. Read the warning and ONE_SIDED_TESTS.md.
4. Invalid Design input may leave previous valid outputs visible beneath an alert.
5. Fisher enumeration and large synthetic samples can be slow on extreme inputs or less powerful devices.
6. Comparison curves and shaded areas are educational model scenarios, not empirical evidence or posterior probabilities.

The result supports the documented MVP within these limits. It does not convert an educational tool into a production experimentation platform.

## Directional release notes

The shared selector, one/two rejection lines, shaded-area integrals, exact input precision, fixed-n opposite effects, directional p-values and confidence-bound labels, unchanged Analyse counts, pending-simulation cancellation and all three chart views also passed DOM interaction checks with Plotly rendering stubbed. These do not certify real-browser visual layout.

After the numerical run, simulator-preset highlighting, CSV test/alpha metadata and conditional graph wording were refined. The statistical script hash was verified unchanged; DOM checks were rerun, and the HTML hash above records the validated release file. See the machine report for this provenance.

## Planning-input update — 18 October 2026

The effect slider now enforces the chosen one-sided direction in Planning. DOM interaction checks passed for both sign restrictions, zero exclusion, wrong-sign/zero manual input, clear warnings, unchanged last-valid outputs, exact manual precision, half-unit slider/keyboard steps, test/mode changes, all chart views, Analyse and 100 simulated experiments. Fixed-sample true-effect exploration still permits either sign.

The inline statistical engine was compared by SHA-256 and is byte-identical to the preceding numerically validated release. The 78 numerical checks above were not rerun for this interface-only change. The HTML hash records the updated interface; the numerical run timestamp and engine hash retain their original provenance. Plotly was stubbed in DOM checks; these are not real-browser visual checks.
