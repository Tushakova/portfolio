# The A/B Testing Lab

**See what actually happens inside an experiment.**

An interactive educational application connecting experiment design, sampling variability, statistical power, error rates and uncertainty. Built as an analytics portfolio project by Maria Tushakova, with AI-assisted development.

[Open the lab](https://tushakova.github.io/portfolio/ab-testing-lab/) · [Portfolio](https://tushakova.co.uk/) · [Application source](https://github.com/Tushakova/portfolio/blob/main/ab-testing-lab/index.html)

## What you can explore

| Section | Question | Working features |
| --- | --- | --- |
| Design | How much evidence do we need? | Two-proportion sample-size planning; fixed-sample power; complementary α/confidence and β/power controls; positive and negative effects; allocation and duration |
| Simulate | What happens if we repeat the experiment? | Independent binomial experiments; false positives and missed effects; individual estimates, p-values and CSV export |
| Analyse | What does one experiment tell us? | Conversion rates, absolute and relative changes, two-sided p-value, Newcombe confidence interval, interpretation |
| Metrics | Why do metrics behave differently? | Binary versus skewed revenue; synthetic revenue and repeated sample means; central limit theorem demonstration |

Design includes **Separate areas**, **Overlay curves** and **Compare changes**. The comparison view holds the axes fixed during an edit, retains the previous distributions as dotted references and fits both states when the edit ends. It compares model scenarios, not observed experiments.

## Documentation

| File | Purpose |
| --- | --- |
| [METHODS.md](METHODS.md) | Full statistical specification: formulas, distributions, assumptions, approximations, algorithms and boundaries |
| [QUESTIONS_AND_ANSWERS.md](QUESTIONS_AND_ANSWERS.md) | Explain and defend the project: conceptual questions, worked examples and practical experiment decisions |
| [EDITING_AND_DEPLOYMENT.md](EDITING_AND_DEPLOYMENT.md) | How the single HTML file works; safe edits; local preview; GitHub upload; publishing and rollback |
| [START_HERE_RU.md](START_HERE_RU.md) | Russian guide for Maria: upload instructions, reading order and key distinctions |
| [VALIDATION.md](VALIDATION.md) | Recorded checks, numerical tolerances, results and remaining coverage gaps |
| [validate_statistics.py](validate_statistics.py) | Reproducible independent checks of the actual JavaScript statistical engine against SciPy and statsmodels |
| [requirements-validation.txt](requirements-validation.txt) | Python dependencies for those checks only |

## Technical implementation

The documented edition is a **static HTML/CSS/JavaScript application**. Its statistical functions and interface are inside `index.html`. Charts use Plotly.js 4.1.1, loaded from `https://cdn.plot.ly/plotly-4.1.1.min.js`.

The browser performs all calculations and simulations. There is no application database, backend or paid API. Loading the chart library requires internet access and makes a normal request to its CDN. Hosting and CDN providers can process normal request metadata; this statement is not a privacy audit of the hosting infrastructure.

Python is used here for independent statistical validation. A separately developed Python/Streamlit edition is not the code executed by this static webpage. Do not describe the live GitHub Pages application as running Streamlit or importing SciPy in the browser.

## Run locally

Download the existing `index.html`. Open it in a browser with internet access, or serve the folder:

```bash
python3 -m http.server 8000
```

Open `http://localhost:8000/`. If serving the whole portfolio repository, open `http://localhost:8000/ab-testing-lab/`.

To run the numerical checks, use Python 3.12 (the tested version family) and Node.js 18+ (Node executes the JavaScript engine without a browser):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-validation.txt
python validate_statistics.py --html index.html
```

See [EDITING_AND_DEPLOYMENT.md](EDITING_AND_DEPLOYMENT.md) for exact upload steps and a manual interface checklist. The validation dependencies are not required to use or host the app.

## Statistical methods at a glance

| Component | Implemented method |
| --- | --- |
| Planning and fixed-sample power | Normal approximation to the difference of independent proportions: pooled null variance and unpooled alternative variance; two-sided rejection region |
| Sample-size search | Integer binary search over control n; treatment n rounded up for the selected allocation |
| Simulated data | Binomial conversion counts generated independently for each arm |
| Result p-value | Pooled two-proportion z-test; two-sided Fisher exact fallback if any pooled expected cell is below 5 |
| Difference CI | Newcombe interval constructed from two Wilson score intervals; no continuity correction |
| Revenue demo | Known mixture: 80% zero, 19% moderate lognormal, 1% high-spender lognormal |

The p-value test and CI are different constructions. They can disagree near a decision boundary. The app's significance label follows **p < α**, not whether its displayed Newcombe interval contains zero.

## Assumptions and scope

The main experiment model assumes independent users, one assignment per user, one binary outcome in a consistent observation window, stable arm-specific event probabilities and fixed sample sizes. It does not diagnose randomisation problems, repeated peeking, interference, missing outcomes, multiple testing or selection bias.

MDE is a planning effect, not a minimum observed effect required for significance. Power is conditional on a specified true effect. Statistical significance does not establish business value. Full details and a practical assumption checklist are in [METHODS.md](METHODS.md).

## Documentation baseline

Prepared on **16 October 2026** for the latest delivered browser edition, including negative-effect planning, compact layout, half-unit sliders, precise manual inputs and comparison mode. [VALIDATION.md](VALIDATION.md) records its SHA-256. A delivered file may differ from the currently deployed website until it is uploaded. This documentation does not certify a deployment.

These documentation files belong **inside `portfolio/ab-testing-lab/`**, beside that project's `index.html`. They do not replace the repository's root portfolio homepage or root README. No licence is granted by the mere presence of public source; add a licence separately if reuse rights are intended.
