# Directional one-sided tests

This release adds a shared **Hypothesis test** selector above the learning-path tabs. It applies to Design, Simulate and Analyse. Metrics is a distribution demonstration rather than a hypothesis test.

## The three options

Let δ = treatment event rate − control event rate. “Increase” and “decrease” describe the measured event, not whether the change is good for the business.

| Selection | Null hypothesis | Alternative | Normal rejection rule | α area |
| --- | --- | --- | --- | --- |
| Two-sided | δ = 0 | δ ≠ 0 | D̂ < −c or D̂ > c, c = z(1−α/2) SE₀ | α/2 in each null tail |
| One-sided increase | δ ≤ 0 | δ > 0 | D̂ > c, c = z(1−α) SE₀ | Entire α in right null tail |
| One-sided decrease | δ ≥ 0 | δ < 0 | D̂ < −c, c = z(1−α) SE₀ | Entire α in left null tail |

The displayed null curve for a one-sided test is the **boundary δ=0** of its composite null. The approximation uses the same pooled-null and unpooled-alternative SE as before. At α=.05 the critical z is approximately 1.645 one-sided versus 1.960 two-sided. One-sided testing can therefore require fewer users for the same specified effect in the chosen direction; it gives up rejection in the other direction.

## Power and non-rejection regions

For true δ and alternative SE₁:

- Increase: power/rejection probability = Φ((δ−c)/SE₁); non-rejection region (−∞,c].
- Decrease: power/rejection probability = Φ((−c−δ)/SE₁); non-rejection region [−c,+∞).
- Two-sided: power = Φ((−c−δ)/SE₁)+Φ((δ−c)/SE₁); non-rejection region [−c,+c].

When the specified truth belongs to the selected alternative, non-rejection is a Type II error β and power = 1−β. At zero, or at a truth in the opposite direction, it satisfies the directional null instead: rejection is a false positive, and non-rejection is not a Type II error. The engine retains the numeric field `beta = 1 − rejection probability` for compatibility; its error-type interpretation must be conditioned on the selected truth.

The chart uses one threshold and one α region in one-sided mode, and fills the full appropriate non-rejection region under the specified-truth curve. Changing the sign of MDE alone in a two-sided test does **not** turn it into a one-sided test.

## Planning and simulation behaviour

Selecting a directional test while in Planning adjusts the planning effect sign to match and announces this next to the selector; it preserves the effect magnitude. Switching from Fixed sample to Planning also aligns the sign. The Planning slider cannot select an effect in the contradictory direction or exact zero. Manual values must be strictly positive for increase and strictly negative for decrease; incompatible entries are highlighted and produce a warning while the previous valid calculation is retained. Precise compatible values are preserved, including magnitudes smaller than the slider step. A fixed-n model accepts opposite-direction effects to illustrate the consequences.

More users increase power for a fixed non-zero effect **in the selected alternative**. When a fixed effect is opposite to that alternative, more users generally reduce the probability of rejection in the selected direction. Do not apply the ordinary “n up, power up” statement without its directional condition.

The global selector never changes the observed counts in Analyse, or silently changes the truth inputs in Simulate. It clears old simulated results; in-progress results from the previous setting are discarded. For an effect in the composite null, the simulator labels rejections as false positives and uses model rejection probability as its comparison rate. Only at the boundary is that reference nominal α; under a strict opposite effect it is generally smaller.

The static dependency map and some generic “power/β” labels describe the usual alternative-effect setting. The dynamic warning and cards qualify opposite-effect/zero settings. The court analogy remains a general explanation of conditional errors, not a directional test model of courts.

## Observed p-values

Using the pooled observed Z statistic:

- Two-sided: p = 2Φ(−|Z|).
- Increase: p = Φ(−Z).
- Decrease: p = Φ(Z).

You cannot universally divide a two-sided p-value by two: for a result opposite to the specified direction, the one-sided normal p-value is near one rather than near zero. For sparse counts, the matching directional Fisher tail is used instead. The reference test table places **treatment first, control second**, which is essential for matching SciPy's greater/less convention. Fisher's discrete p-values do not obey a universal doubling/halving identity.

## One-sided confidence bounds

Analyse displays a confidence **set** with one data-dependent finite bound and one physical parameter limit, since δ ∈ [−1,+1]:

- Increase: [L, +1], a lower confidence bound.
- Decrease: [−1, U], an upper confidence bound.

At confidence 1−α, the finite bound uses the Wilson-based Newcombe-style construction with **z(1−α)**, not z(1−α/2). For ordinary α<.5, the finite endpoint equals the corresponding endpoint of a central Newcombe interval at confidence 1−2α. Thus a 95% one-sided bound shares its finite endpoint with the appropriate endpoint of a 90% central interval; it is **not** a 90% one-sided statement.

For the ordinary range, take the Newcombe formulas in METHODS with the Wilson z replaced by z(1−α). The plotted arrow shows continuation toward ±100 pp without stretching the view to that limit. The estimate marker, zero reference and numeric confidence set remain visible. Near a boundary, the p-value and bound can disagree because pooled-z/Fisher and Newcombe are different constructions.

For the intentionally broad α controls, α≥.5 yields confidence ≤50%. The engine uses directed Wilson roots and the sign of z in the Newcombe distance construction: L = D̂ − sign(z)√[(p̂₁−L₁)²+(U₀−p̂₀)²], U = D̂ + sign(z)√[(U₁−p̂₁)²+(p̂₀−L₀)²], bounded physically. A warning explains that the bound can lie beyond the point estimate. This unusual extension is numerically tested, not coverage-certified; it is an educational exploration setting, not a recommended interval for decisions.

## Choose before seeing the outcome

Use a pre-specified directional test when the question, decision rule and risk of ignoring the opposite direction justify it. The app cannot enforce a pre-registration: changing the selector after inspecting results is possible mechanically but does not preserve the claimed false-positive control for a data-dependent choice.

One-sided testing is not a free gain in power. If harmful movement matters, monitor it with an appropriate pre-specified safety/guardrail procedure. Non-significance in an increase test does not establish no harm. A decrease test against zero is not a non-inferiority test: non-inferiority and equivalence require non-zero margins and distinct hypotheses, which remain outside this MVP.

## API and validation

Engine `model`, `plan` and `analyse` accept an optional final `alternative`, default `'two-sided'`. `simulate` preserves its existing seed/RNG argument, with `alternative` appended after it. Valid values: `'two-sided'`, `'greater'`, `'less'`. Existing calls that omit the parameter keep their two-sided meaning.

The reference runner covers all three choices against SciPy/statsmodels, one-sided null and alternative simulations, sparse Fisher tails, directional confidence bounds and wrong-direction effects. It also retains two-sided regression cases. A separate DOM interaction check exercises shared settings, plot areas/thresholds, comparison mode, unchanged observed counts and cancellation of stale simulations, using a Plotly stub; it is not a real-browser visual check.

Primary references: [statsmodels proportion power](https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.power_proportions_2indep.html), [SciPy Fisher exact tails](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.fisher_exact.html), [statsmodels Newcombe intervals](https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.confint_proportions_2indep.html). The browser implementation is local; these libraries are reference tools, not runtime APIs.
