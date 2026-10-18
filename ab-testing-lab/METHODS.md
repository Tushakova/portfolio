# Statistical methods and assumptions

This is the specification of the **browser edition** in `index.html`, not a generic description of every A/B testing method. Function names refer to the inline script `lab-statistics` unless otherwise stated. The project overview is in [README.md](README.md); directional hypotheses are covered in [ONE_SIDED_TESTS.md](ONE_SIDED_TESTS.md).

## 1. Data model and notation

For arm j = 0 (control) or 1 (treatment), each user contributes a binary outcome Y: event = 1, no event = 0. The event may be a purchase, error or bad review; the statistical model does not determine whether more is better.

| Symbol | Meaning | Units |
| --- | --- | --- |
| p₀, p₁ | Assumed true event probabilities for planning/simulation | Proportions, 0–1 |
| n₀, n₁ | Numbers of independent users in each arm | Users |
| X₀, X₁ | Observed event counts | Integers |
| p̂₀, p̂₁ | Observed rates, Xⱼ/nⱼ | Proportions |
| δ | Specified true difference, p₁ − p₀ | Proportion units |
| D̂ | Estimated difference, p̂₁ − p̂₀ | Proportion units |
| r | Signed relative change, δ/p₀ | Proportion units; input shown as % |
| α | Significance threshold / nominal Type I error rate | Probability |
| β(δ) | Probability of failing to reject H₀ at the specified true effect | Probability |
| π(δ) | Power = 1 − β(δ) | Probability |
| q | Fraction of traffic assigned to treatment | Probability |
| Φ, φ | Standard normal CDF and density | — |

Under the model, Xⱼ ~ Binomial(nⱼ, pⱼ), independently across arms and repetitions. Then E(D̂) = δ and Var(D̂) = p₀(1−p₀)/n₀ + p₁(1−p₁)/n₁.

### Units and signed effects

The interface accepts a percentage R and sets r = R/100, p₁ = p₀(1+r). An absolute difference becomes percentage points by multiplying δ by 100.

| Baseline | Input | Target | Absolute difference |
| --- | --- | --- | --- |
| 20% | +5% relative | 21% | +1 percentage point |
| 20% | −5% relative | 19% | −1 percentage point |
| 23% | +8% relative | 24.84% | +1.84 percentage points |

Strictly, MDE describes the magnitude of a planning alternative. The signed control combines **magnitude and direction**. A negative value is not a different test. The global test selector separately chooses two-sided, one-sided increase or one-sided decrease. A signed effect alone does not change the test. Non-inferiority, equivalence and a business-success rule remain outside scope.

## 2. Hypotheses and the two curves

In the default two-sided mode, the tested null is H₀: p₁ − p₀ = 0. The two-sided alternative is H₁: p₁ − p₀ ≠ 0. To calculate power we select one specific alternative δ, even though the test can reject in either direction.

Each curve represents possible **estimates D̂ across repeated experiments**, not individual users, treatment-only outcomes, posterior probabilities or uncertainty over which hypothesis is true.

- The H₀ curve is centred on zero.
- The chosen H₁ curve is centred on δ.
- The x-axis is D̂ in percentage points.
- The y-axis is probability density per percentage point; height is not probability. Probability is area.

For a normal curve with mean μ and standard deviation s, the density is f(x) = exp(−(x−μ)²/(2s²))/(s√(2π)). Each full curve has area 1. Narrower distributions have higher peaks to preserve area. The plotted range truncates far tails; its numerical shaded areas are visual approximations. Calculated probabilities use the CDF, not the drawn pixels. Plotting percentage points rather than proportions also requires dividing the original density by 100, which the chart does, so areas remain probabilities.

## 3. Planning approximation: `model`

The equations and α/2 areas below describe the default **two-sided** mode. [ONE_SIDED_TESTS.md](ONE_SIDED_TESTS.md) extends them to the two directional modes: one threshold, z(1−α), one selected rejection tail and a half-line non-rejection region. Its null curve is the boundary of a composite null, not the entire null.

Under a specified alternative, the allocation-weighted pooled rate is

$$p_* = \frac{n_0p_0+n_1p_1}{n_0+n_1}.$$

The implementation uses

$$SE_0=\sqrt{p_*(1-p_*)\left(\frac1{n_0}+\frac1{n_1}\right)},\qquad SE_1=\sqrt{\frac{p_0(1-p_0)}{n_0}+\frac{p_1(1-p_1)}{n_1}}.$$

The visual/planning model is D̂ | H₀ ≈ Normal(0, SE₀²) and D̂ | specified H₁ ≈ Normal(δ, SE₁²). H₀ has an unknown common rate; p* is a plug-in planning value implied by the alternative, not a claim that we know the null rate from data.

With z = Φ⁻¹(1−α/2), let c = z SE₀. The rejection region is **D̂ < −c or D̂ > c**. Thus

$$\pi(\delta)\approx\Phi\left(\frac{-c-\delta}{SE_1}\right)+1-\Phi\left(\frac{c-\delta}{SE_1}\right),\qquad \beta(\delta)=1-\pi(\delta).$$

In code the right-tail term is evaluated as Φ((δ−c)/SE₁), using normal symmetry. The central probability is β = P(−c ≤ D̂ ≤ c | specified H₁).

### α and β belong to different distributions

| Area | Distribution used | Region |
| --- | --- | --- |
| α/2, left | H₀ | D̂ < −c |
| α/2, right | H₀ | D̂ > c |
| β | Specified H₁ | −c ≤ D̂ ≤ c |
| Power | Specified H₁ | Both tails beyond the thresholds |

β is the **whole H₁ central region**, including either side of zero. It is not the overlap of the two curves and not necessarily half of any area. With positive δ it often lies mostly left of the H₁ peak; with negative δ, mostly right. Power includes statistically significant estimates in the opposite direction too. Such an estimate does not establish the intended improvement; “reject H₀” and “ship the change” are different decisions.

### What is exact and what is approximate?

Power + β = 1 and α + nominal confidence = 1 are mathematical complements. The claimed nominal α and the power calculation depend on the model. In an actual pooled z-test, the standard error is estimated from each experiment, so the threshold in raw D̂ units is random. The planning chart substitutes the fixed planned SE₀. Its boundaries are an educational approximation, not an exact rejection boundary for all possible binomial tables.

This pooled-null/unpooled-alternative approach is also documented by [statsmodels power_proportions_2indep](https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.power_proportions_2indep.html). The validation script maps treatment to its “sample 1” and control to its “sample 2”; reversing that ratio would give incorrect unequal-allocation comparisons.

## 4. Planning versus fixed sample: `plan`

**Planning mode:** test direction, p₀, signed r, α, desired power and q are inputs; n₀ and n₁ are outputs. The power/β bar specifies desired power. Calculated achieved power is displayed separately and may be slightly higher after rounding.

The treatment/control ratio is k = q/(1−q). For a candidate integer n₀, the code sets n₁ = max(2, ceil(k n₀)). Starting at n₀ = 2, it doubles the upper bound until achieved power meets the target, then binary-searches for the smallest integer control n that meets it under this allocation rule. This is not a closed-form sample-size formula and not an optimisation over all possible allocations. The doubling search stops with an error once its upper bound exceeds 100 million; this is a practical computational guard and can reject cases near that limit.

**Fixed-sample mode:** test direction, p₀, signed r, α, n₀ and q are inputs; n₁ follows the allocation, and power and β are outputs. The β bar is disabled. This avoids a circular dependency in which both sample size and desired power independently control the same model.

At fixed rates and allocation, more users reduce SE and generally raise power for a non-zero effect in the selected alternative. A fixed effect in the opposite direction of a one-sided test makes rejection less likely as n grows; it lies within that test's null. Planning restricts the MDE slider to positive values for an increase test and negative values for a decrease test; exact zero is skipped. Incompatible or zero typed values are rejected with an explicit warning before updating the model. Precise compatible typed values remain supported. Choosing a directional test or re-entering Planning aligns the planning-effect sign and announces the adjustment. At fixed sample sizes and rates, reducing α moves thresholds outwards and reduces power. In planning mode stricter α instead increases n to preserve target power. A smaller **effect magnitude**, closer to zero, needs more users for the same target power. Do not interpret “smaller effect” as “more negative effect”.

At δ = 0 the probability of rejection is approximately α, not useful ability to detect a real effect. The planning UI requires a non-zero effect; zero can be explored at fixed n or in Simulate. If desired power ≤ α, the minimum n may already exceed the target. Extreme α/β settings are educational settings, not recommended experiment designs. The normal approximation may be poor there.

### Traffic and duration

The displayed traffic minimum is ceil((n₀+n₁)/daily eligible users), assuming stable incoming traffic and the planned allocation. It is a throughput estimate, not a recommended stopping date. Allow for full weekly cycles, ramp-up, late conversions, retention windows, exclusions and analysis readiness. Very small samples and integer allocation can make per-arm arrival requirements differ from that rounded total-based estimate.

## 5. Simulated experiments: `simulate`, `binomial`

Each repetition independently draws X₀ and X₁ from their binomial distributions, then calls the same `analyse` function used by Analyse. It does **not** draw a p-value or assign a predetermined number of coloured tiles.

For small n (<64), the random generator sums Bernoulli draws. For larger n it uses recursive beta splitting: a beta draw is constructed as Gₐ/(Gₐ+Gᵦ) from independent gamma draws; conditional splitting reduces the binomial problem recursively. This is distributional binomial generation, not a normal approximation to counts. Gamma generation uses a rejection sampler; normal draws use Box–Muller. These are custom browser routines and are validated empirically, not formally proven by this repository's tests.

The interactive simulator uses `Math.random()`; repeated clicks are not seeded or replayable. Validation uses the built-in seeded PRNG. No cryptographic randomness is needed or claimed. The metrics demo uses fixed seeds and caches results.

For R independent repetitions with rejection probability θ, K ~ Binomial(R, θ) and SD(K/R) = sqrt(θ(1−θ)/R). At R = 100, the expected rate's Monte Carlo SE is about 2.18 percentage points for θ=.05 and 4 percentage points for θ=.8. A batch need not contain exactly five false positives or exactly eighty detections. The simulator's displayed Monte Carlo SE uses the nominal/planning rate, not an estimated CI for the observed rate.

Under the selected H₀ a rejection is a false positive. At the null boundary its reference rate is α; a specified truth strictly within a one-sided null has its own, generally smaller, model rejection rate. Under a specified truth in H₁ a rejection is a detection; non-rejection is a missed effect. Two-sided detection includes either tail, while one-sided detection only uses the pre-specified direction. Finite-sample discreteness, the estimated pooled variance and the exact-test fallback cause departures from the planning approximation.

## 6. Analysis: `analyse`

Inputs must be integer counts, nⱼ ≥ 2 and 0 ≤ Xⱼ ≤ nⱼ. Compute p̂ⱼ = Xⱼ/nⱼ, D̂ = p̂₁−p̂₀ and relative estimate D̂/p̂₀. If control has zero events, relative change is undefined; the absolute difference remains defined.

The pooled observed rate is p̂ = (X₀+X₁)/(n₀+n₁). The pooled test SE is sqrt(p̂(1−p̂)(1/n₀+1/n₁)). When expected cells are adequate, Z = D̂/SE. The two-sided p-value is 2Φ(−|Z|), the increase p-value is Φ(−Z), and the decrease p-value is Φ(Z). There is no continuity correction.

Expected cells are n₀p̂, n₁p̂, n₀(1−p̂), n₁(1−p̂). If **any is below 5**, the implementation uses Fisher's exact test with the selected two-sided or one-sided alternative. For a two-sided test with fixed row/column margins it sums hypergeometric probabilities of tables with probability no greater than the observed table. A one-sided test instead sums treatment-event-count probabilities at least as large (increase) or at most as large (decrease) as observed. Log probabilities are used for numerical stability; code includes a 1e−7 tolerance on the log-probability comparison for nearly equal tables. This follows the probability-ordering two-sided convention, which is not generally twice a one-sided Fisher p-value. See [SciPy fisher_exact](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.fisher_exact.html).

The strict decision is **p < α**. p = α is not labelled significant. Both-zero or both-all-event cases enter the exact-test branch, avoiding a zero-SE division. Fisher calculation enumerates feasible tables: very large pathological inputs can be slow. The sparse-cell threshold is a practical rule, not a guarantee that every z-test above it is accurate.

### Meaning of a p-value

It measures how unusual a result at least as extreme would be under H₀ and the specified sampling procedure. It is not P(H₀ true | data), P(result due to chance), an effect size or the chance that a rollout will succeed. Under an exactly calibrated continuous null test, p-values are uniform; for discrete tests they are typically conservative rather than exactly uniform. The finite-sample z-test is approximate.

## 7. Confidence interval: Wilson + Newcombe

The central interval below is the **two-sided** result. A one-sided selection instead returns a Wilson-based Newcombe-style lower or upper bound at z(1−α), with the other endpoint at the physical difference limit ±1. See [ONE_SIDED_TESTS.md](ONE_SIDED_TESTS.md) for formulas, arrow display and unusual-confidence settings.

For one observed proportion p̂ = X/n, put z = Φ⁻¹(1−α/2), A = 1+z²/n,

$$m=\frac{\hat p+z^2/(2n)}A,\qquad h=\frac{z\sqrt{\hat p(1-\hat p)/n+z^2/(4n^2)}}A.$$

Wilson bounds are L = max(0,m−h), U = min(1,m+h). Let [L₀,U₀] and [L₁,U₁] be the two arm intervals. For D̂ = p̂₁−p̂₀ the implemented Newcombe bounds are

$$L_D=\hat D-\sqrt{(\hat p_1-L_1)^2+(U_0-\hat p_0)^2},\qquad U_D=\hat D+\sqrt{(U_1-\hat p_1)^2+(\hat p_0-L_0)^2}.$$

This is the uncorrected Wilson-based Newcombe difference interval, often called method 10. It is **not** obtained by simply subtracting the endpoints of the two arm intervals; it is not the plain Wald interval D̂ ± z SE. See [statsmodels confint_proportions_2indep](https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.confint_proportions_2indep.html), explicitly selecting `method='newcomb'`, `compare='diff'`.

Nominal 95% confidence describes intended repeated-sampling coverage of the interval procedure. Once observed, the fixed true difference is not assigned a 95% probability by this frequentist interval. Actual coverage varies with finite samples and event rates.

**CI and p-value are not exact inverses in this app.** The p-value comes from pooled z or Fisher, whereas the CI comes from Newcombe. Near α they can disagree about whether zero is excluded. The significance label follows the p-value. Neither discrepancy nor rounding should be hidden by claiming they must always agree. A paired test/CI inversion would be a future methodological change.

## 8. Revenue and the central limit theorem

`revenue()` generates Y from this known population (natural-log parameters):

| Probability | Revenue |
| --- | --- |
| 0.80 | 0 |
| 0.19 | exp(3.4 + 0.65 Z), Z ~ Normal(0,1) |
| 0.01 | exp(6 + 0.65 Z), Z ~ Normal(0,1) |

Its mean is μ = .19 exp(3.4+.65²/2) + .01 exp(6+.65²/2). For k=1 or 2, E(Yᵏ) = .19 exp(3.4k+.65²k²/2) + .01 exp(6k+.65²k²/2), so Var(Y) = E(Y²)−μ² is finite.

Chart A contains 20,000 synthetic individual draws (seed 2026). Chart B contains 1,000 independently generated sample means at selected n ∈ {10,50,100,500,1000,10000} (seed 2027, restarted per n). They are draws from the generator, **not bootstrap resamples of Chart A**. Results are cached; different n panels are not independent Monte Carlo runs because they reuse the seed. Histogram binning is automatic and density/axis scales may change, so inspect axis values as well as shapes.

For independent identically distributed observations with finite variance, sqrt(n)(Ȳ−μ)/σ converges in distribution to Normal(0,1), and SE(Ȳ)=σ/sqrt(n). The CLT applies to the mean's sampling distribution, not to individual revenues becoming normal. Skewness and rare large values can slow convergence. Infinite-variance populations need not follow this classical result; this particular synthetic mixture has finite variance.

The Metrics section explains Welch's t-test but **does not run a revenue A/B test**. For two independent sample means Welch uses t = (Ȳ₁−Ȳ₀)/sqrt(s₁²/n₁+s₀²/n₀). Write vⱼ = sⱼ²/nⱼ. Its Welch–Satterthwaite degrees of freedom are ν = (v₀+v₁)² / [v₀²/(n₀−1)+v₁²/(n₁−1)]. It does not assume equal variances. Welch's t reference is itself an approximation, even for unequal-variance normal populations; the ordinary equal-variance Student t construction has an exact t distribution under its normal model. With skewed revenue, large-sample approximations and robustness need assessment. The t distribution has heavier tails than the normal for finite degrees of freedom, approaching normal as degrees of freedom grow. Bernoulli variance p(1−p) is why the conversion example uses a proportion model rather than switching automatically to t for small n. See [SciPy ttest_ind](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_ind.html), `equal_var=False`.

## 9. Assumptions and practical checks

| Assumption | Why it matters | Before applying this to an actual experiment |
| --- | --- | --- |
| Random assignment and stable user identity | Supports causal interpretation and arm comparability | Confirm assignment/exposure logging; investigate sample-ratio mismatch |
| Independent observations | Binomial SE treats users as independent | Aggregate per user; assess household, store or cluster randomisation |
| One binary outcome per user/window | Defines the denominator and Bernoulli variable | Do not substitute orders/sessions as independent users |
| Consistent eligibility and outcome window | Avoids selection and maturity bias | Define inclusion before exposure; let late outcomes mature |
| No cross-arm interference | One user's assignment should not change another's outcome | Assess shared inventory, networks, marketplace effects |
| Stable arm probabilities in this model | Enables a single binomial rate per arm | Account for calendar cycles, traffic mix and time-varying effects |
| Fixed analysis horizon | Preserves the intended testing procedure | Do not repeatedly peek and stop at the first p < α |
| One pre-specified comparison | α is per test, not automatically family-wide | Handle multiple variants, metrics and exploratory segments separately |
| Adequate expected counts for normal planning | Tail probabilities can be inaccurate near boundaries | Treat warning settings as demonstrations; use suitable specialised planning |
| Complete, comparable measurement | Missingness can bias estimated rates | Check instrumentation, duplicates, exclusions and differential attrition |

Full-population coverage is not an input. The model is a repeated-user-arrival/superpopulation approximation. A finite-population sampling-without-replacement problem can need a finite population correction; a randomised experiment on all available users can still have assignment uncertainty and uncertainty about future users. Do not set SE to zero merely because all current eligible users were exposed.

The app does not implement sequential tests, multiplicity control, CUPED, covariate adjustment, clustered SE, Bayesian inference, bootstrap CIs, equivalence tests or non-inferiority tests. Non-significance does not establish equivalence. No business-loss function or automated rollout recommendation is calculated.

## 10. Numerical and interface boundaries

The browser uses a polynomial normal-CDF approximation and a binary-search inverse within [−9,9], rather than SciPy in production. Therefore results are approximate and can differ in the last displayed digits or by an integer user near a planning boundary. Fisher uses log-gamma arithmetic. [VALIDATION.md](VALIDATION.md) records tolerances and observed checks; it is not a proof of correctness for every extreme input.

Design inputs currently support baseline .01–90%, signed effect −30–+30% relative and treatment allocation 1–99%, with p₁ required strictly between 0 and 1. Sliders snap to 0.5-unit values; precise typed values are preserved. In one-sided Planning the effect range is restricted to the selected sign, with strict non-zero validation; two-sided Planning and fixed-sample true effects retain the full signed range. Baseline values below the slider's first positive half-unit remain accessible by typing. α/β controls are clamped to .1–99.9%. The normal approximation warning uses an expected success/failure count below 10, whereas the observed test switches to Fisher below 5; these are deliberately different decisions. Numeric display rounding does not define the test.

Planning skips exact zero while dragging through it; typing zero prompts a non-zero planning-effect message. Fixed-sample zero is accepted, but the generic “power/detect/miss” wording remains: at zero, interpret these values as rejection/non-rejection probabilities under H₀. This is a documented educational copy limitation.

Input errors show an alert and can leave the previous valid design visible; do not read old values as a result for invalid inputs. Analyse dims stale output. Sessions reset on reload; settings are not saved to local storage or a server. Future releases should improve these edge-state explanations and should be revalidated after statistical changes.

## References

The primary documentation linked in sections 3, 6, 7 and 8 describes the reference methods. This application contains its own browser implementation; it does not call those libraries at runtime. References were checked on 16 October 2026. For executable comparison and exact software versions, see [VALIDATION.md](VALIDATION.md).
