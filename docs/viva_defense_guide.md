# Viva Defense Guide — Spatial-Financial Café Feasibility DSS

## Project position and scope

This project is an explainable decision-support tool for testing a café's
financial assumptions, viewing mapped points of interest (POIs) around a
proposed site, and ranking supplied alternatives. It is not a business-success
predictor, investment recommendation, or substitute for local market research.
All case-study numbers below are transparent illustrative inputs chosen to
exercise the implemented calculations; they are not audited café accounts or
verified market observations.

The full HTTP pipeline is covered by `tests/test_e2e_scenarios.py`. Its spatial
service is mocked so tests are deterministic and do not depend on Overpass or
map-tile availability. The browser dashboard remains a manual demonstration;
these tests do not claim automated browser-level end-to-end coverage.

## Core architectural defense

The system separates four questions that are often conflated:

1. **Can the unit economics cover the modeled costs?** A deterministic
   cost-volume-profit (CVP) calculation answers this from declared inputs.
2. **Which explicit risk thresholds are crossed?** A rule engine reports the
   measured value, benchmark, severity, and explanation.
3. **What mapped context is nearby?** OpenStreetMap POIs provide limited
   competitor and demand-anchor proxies, not observed customers or footfall.
4. **How do supplied alternatives compare on selected criteria?** TOPSIS
   provides a relative, auditable multi-criteria ranking.

This is preferable to presenting an ungrounded black-box ML score. There is no
verified, representative dataset of private MSME profit-and-loss statements,
site decisions, and eventual outcomes in this project. Training XGBoost or
another classifier without that ground truth would risk learning fabricated,
biased, or non-generalizable labels and could create false precision. It would
also make it harder for a founder or examiner to trace a result back to a
specific cost, capacity limit, POI count, or criterion weight.

The deterministic and MCDA methods are not assumed to be universally more
accurate. They are chosen because their inputs and assumptions can be inspected,
challenged, and changed. Rules and illustrative weights are heuristics, not
empirically validated laws. A future predictive model would require consented
and legally usable outcome data, documented sampling, leakage controls,
out-of-time and external validation, calibration, subgroup analysis, and a
comparison proving that it adds value beyond these interpretable baselines.

## Mathematical formulations

### Financial feasibility

Let:

- \(p\) be average ticket size per cover and \(v\) variable cost per cover.
- \(R\) be monthly rent and \(O\) other monthly fixed costs.
- \(S\) be seats, \(H\) daily operating hours, and \(T\) seat turnovers per
  seat per operating hour.
- \(D\) be operating days per month, \(E\) expected covers per day, and \(K\)
  initial working capital available after setup costs.

Contribution per cover and contribution margin ratio are:

\[
\mathrm{CM}=p-v,\qquad
\mathrm{CMR}=\frac{p-v}{p}\quad(p>0).
\]

Monthly fixed costs are \(F=R+O\). Break-even exists only when
\(\mathrm{CM}>0\):

\[
\mathrm{BE}_{\mathrm{month}}=\frac{F}{\mathrm{CM}},\qquad
\mathrm{BE}_{\mathrm{day}}=\frac{F}{\mathrm{CM}\,D}.
\]

If contribution is zero or negative, finite break-even is undefined; the
engine returns `None` for break-even covers and the diagnostic engine reports
that break-even is not achievable.

The modeled seating capacity and realized volume are:

\[
\mathrm{Capacity}_{\mathrm{day}}=SHT,\qquad
\mathrm{Covers}_{\mathrm{realized}}=
\min(E,\mathrm{Capacity}_{\mathrm{day}}).
\]

Monthly projected operating profit and cash burn are:

\[
\mathrm{Profit}_{\mathrm{month}}=
D\,\mathrm{Covers}_{\mathrm{realized}}\,\mathrm{CM}-F,\qquad
\mathrm{Burn}_{\mathrm{month}}=
\max(0,-\mathrm{Profit}_{\mathrm{month}}).
\]

When monthly burn is positive, the simple cash-runway estimate is:

\[
\mathrm{Runway}_{\mathrm{months}}=
\frac{K}{\mathrm{Burn}_{\mathrm{month}}}.
\]

When the scenario is profitable or exactly at break-even, the engine returns
`None` for runway because this model does not deplete working capital in that
case. A finite positive runway therefore means the current modeled scenario
has a loss; it is not a statement that the café is profitable.

### TOPSIS location ranking

For candidate \(i\) and criterion \(j\), vector normalization, weighting, and
direction-aware ideal values are:

\[
r_{ij}=\frac{x_{ij}}{\sqrt{\sum_i x_{ij}^{2}}},\qquad
v_{ij}=w_jr_{ij},\qquad \sum_j w_j\approx1.
\]

A zero-norm criterion column is normalized to zero. For benefit criteria,
\(v_j^+=\max_i(v_{ij})\) and \(v_j^-=\min_i(v_{ij})\); for cost criteria the
maximum and minimum are reversed. Euclidean distances to the ideal best and
negative ideal are:

\[
D_i^+=\sqrt{\sum_j(v_{ij}-v_j^+)^2},\qquad
D_i^-=\sqrt{\sum_j(v_{ij}-v_j^-)^2}.
\]

Relative closeness and ranking are:

\[
C_i=\frac{D_i^-}{D_i^++D_i^-},\qquad 0\le C_i\le1.
\]

Candidates are ordered by descending \(C_i\). If both distances are zero (for
example, identical criterion rows), the implementation assigns the neutral
score \(0.5\); equal scores retain input order. A score is relative to the
candidates, criteria, and weights supplied for that run, not an absolute
probability of success.

## Illustrative case studies

The following scenarios use INR and a 30-day modeled month. They are designed
to make the system's calculations and diagnostics reproducible, not to claim
typical costs, sales, or rents for any neighborhood.

### 1. Healthy suburban neighborhood café — near-break-even baseline

**Inputs**

| Assumption | Value |
|---|---:|
| Monthly rent / other fixed costs | ₹20,000 / ₹100,000 |
| Ticket / variable cost per cover | ₹280 / ₹95 |
| Seats / hours / turns per seat-hour | 28 / 12 / 0.75 |
| Expected covers per day / operating days | 20 / 30 |
| Working capital | ₹180,000 |

**Expected result.** Contribution is ₹185 per cover (66.1% margin).
Break-even is 21.62 covers/day versus modeled capacity of 252 covers/day.
Projected revenue is ₹168,000/month; rent is 11.9% of that revenue. At 20
covers/day, projected operating loss is ₹9,000/month, producing a finite
20-month runway. This is a capacity-feasible, low-rent, near-break-even
planning baseline, **not yet a profitable forecast**; roughly 1.62 additional
covers/day would reach modeled break-even if the other assumptions hold.

**Triggered flags.** None of the four implemented rules: rental stress,
capacity deficit, short runway, and low contribution margin. The absence of
these flags does not establish commercial viability.

**Alternative recommendation.** With the example alternatives and default
weights below, HSR Layout Sector 1 ranks first (0.5834), just ahead of Jayanagar
4th Block (0.5803). HSR has more anchors and slightly higher accessibility in
the supplied records, while Jayanagar has fewer competitors and lower listed
rent per square foot. The small score gap makes this a close, weight-sensitive
comparison rather than a decisive site verdict.

### 2. High-rent commercial tech corridor — rent-overburden failure mode

**Inputs**

| Assumption | Value |
|---|---:|
| Monthly rent / other fixed costs | ₹1,200,000 / ₹100,000 |
| Ticket / variable cost per cover | ₹250 / ₹100 |
| Seats / hours / turns per seat-hour | 20 / 10 / 0.5 |
| Expected covers per day / operating days | 100 / 30 |
| Working capital | ₹100,000 |

**Expected result.** Contribution is ₹150 per cover (60% margin). Capacity is
100 covers/day, but break-even requires 288.89 covers/day. At capacity,
projected revenue is ₹750,000/month, rent alone is 160% of projected revenue,
monthly operating loss is ₹850,000, and runway is approximately 0.12 months.

**Triggered flags.** `RENTAL_STRESS` — CRITICAL (160% versus the 18% critical
benchmark); `CAPACITY_DEFICIT` — CRITICAL (288.89 required versus 100
available); and `SHORT_RUNWAY` — WARNING (approximately 0.12 versus the
3-month benchmark). The contribution margin does not trigger a flag.

**Alternative recommendation.** The supplied TOPSIS example again ranks HSR
Layout Sector 1 first (0.5834). That ranking does **not** incorporate this
scenario's rent or financial shortfall: candidate rent-per-square-foot inputs
are separate illustrative criteria. The decision-support conclusion is to
reject or renegotiate this proposed lease under the stated assumptions, not to
treat another preset candidate as verified or automatically feasible.

### 3. High-ticket boutique café — physical seating bottleneck

**Inputs**

| Assumption | Value |
|---|---:|
| Monthly rent / other fixed costs | ₹200,000 / ₹1,000,000 |
| Ticket / variable cost per cover | ₹900 / ₹300 |
| Seats / hours / turns per seat-hour | 20 / 10 / 0.3 |
| Expected covers per day / operating days | 100 / 30 |
| Working capital | ₹1,200,000 |

**Expected result.** Contribution is ₹600 per cover (66.7% margin). Expected
demand is 100 covers/day but the physical model caps realized covers at 60.
Break-even is 66.67 covers/day, exceeding capacity by 6.67. Projected revenue
at capped volume is ₹1,620,000/month; rent is 12.35% of revenue. The projected
loss is ₹120,000/month and modeled runway is 10 months.

**Triggered flags.** `CAPACITY_DEFICIT` — CRITICAL (66.67 required versus 60
available). Rent-to-revenue, contribution margin, and runway do not cross
their configured risk thresholds in this scenario.

**Alternative recommendation.** HSR Layout Sector 1 remains the top-ranked
example alternative at 0.5834, but its score reflects only the supplied
location criteria. The financial analysis still says the boutique concept
cannot break even within its modeled seating capacity; a site ranking cannot
repair that unit-economics constraint.

### Shared illustrative TOPSIS alternatives

These are the sample UI records, not verified current market measurements.
The four default criteria are competitor count (cost, weight 0.25), anchor
count (benefit, 0.30), average rent per square foot (cost, 0.25), and
accessibility (benefit, 0.20).

| Rank | Supplied candidate | TOPSIS score |
|---:|---|---:|
| 1 | HSR Layout Sector 1 | 0.5834 |
| 2 | Jayanagar 4th Block | 0.5803 |
| 3 | Koramangala 5th Block | 0.4738 |
| 4 | Indiranagar 100ft Rd | 0.4197 |

The same ranking appears in all three cases because the API ranks the
candidate metrics independently of the business financial inputs. The
alternative records are not enriched with candidate-specific live POIs or
verified rents. A decision-maker should validate those inputs and test
whether plausible weight changes alter the close HSR/Jayanagar ordering.

## Examiner Q&A

### 1. Why not XGBoost or another machine-learning predictor?

There is no verified, representative ground-truth dataset of private café
financials, site choices, and subsequent outcomes available to this
implementation. A model trained on guessed or synthetic labels would create
unearned authority, and a high validation score on a narrow sample would not
prove transportability to a new city or time period. CVP and TOPSIS expose the
assumptions and trade-offs. If suitable governed data become available, a
predictive model can be evaluated as a separate, validated extension against
these baselines.

### 2. How do you estimate footfall without live GPS or transaction data?

This system does not estimate or claim footfall. It counts selected OSM
competitor and demand-anchor POIs within geodesic radii; these are contextual
proxies only. OSM coverage and tagging vary, and a nearby anchor does not
prove that people visit or purchase. Better demand evidence would require
privacy-preserving and permissioned sources such as field counts, surveys,
lease-level studies, or properly aggregated mobility data, with their
provenance and limitations made explicit.

### 3. How were TOPSIS weights determined, and are the resulting ranks
objective?

The UI defaults (0.25, 0.30, 0.25, 0.20) are explicit demonstration weights,
not weights learned from validated outcomes or claimed to be universal. The
API validates that weights sum approximately to one and records the criteria
and intermediate values. A real decision process should elicit weights from
stakeholders, document their rationale, and conduct sensitivity analysis.
TOPSIS makes the chosen trade-offs visible; it does not remove subjectivity.

### 4. What happens when OpenStreetMap or Overpass is incomplete or unavailable?

POI coverage and freshness depend on community mapping and tagging. The engine
caches successful results with source, time, bounds, and ODbL attribution;
expired cache is refreshed online, and the current implementation does not
silently substitute stale data after a refresh failure. An upstream failure
is surfaced as HTTP 502, rather than being represented as zero nearby
businesses. The dashboard map tiles also require network access.

### 5. How realistic are the financial projections and what validates them?

They are scenario calculations, not audited forecasts. The CVP model assumes
the supplied price, unit variable cost, fixed costs, operating days, and
capacity are stable for a representative month. It omits taxes, financing,
seasonality, opening costs, working-capital cycles, changing demand, and
execution risk. Unit and API tests verify implementation behavior and
mathematical cases; they do not establish that the assumptions or domain
thresholds predict real-world success. Users must validate inputs, and
empirical validation requires suitable real outcomes and a documented study.

## Viva live-demo script (under 5 minutes)

Before the viva, start the FastAPI server from the workspace root and the Vite
server from `frontend/` in separate terminals. Open `http://localhost:5173`,
confirm the header reports the backend as online, and ensure Overpass is
reachable or that a fresh cache is available. A full analysis can return HTTP
502 when spatial data cannot be fetched; do not describe this as a zero-POI
result.

| Time | Exact action | Point to explain |
|---|---|---|
| 0:00–0:30 | Show the dashboard header, default assumptions, map, and “Decision support, not prediction” note. | Inputs are editable; Bengaluru candidate values are illustrative. |
| 0:30–1:20 | Click **Run feasibility analysis** and wait for completion. | The UI calls the full-feasibility endpoint; the selected-site POI response includes cache/source/license provenance. |
| 1:20–2:00 | Point to contribution margin, break-even versus capacity, monthly result/runway, risk cards, and ranked alternatives. | Explain the difference between a relative TOPSIS rank and a feasibility result. Note the close HSR/Jayanagar example scores. |
| 2:00–2:40 | Focus the **Monthly rent** slider and press **End** (₹250,000); focus **Seating capacity** and press **Home** (4 seats). | These are the exact slider maximum and minimum. Keep the other defaults unchanged. |
| 2:40–3:30 | Click **Run feasibility analysis** again. | At 4 seats, 12 hours, and 0.75 turns/hour, modeled capacity is 36 covers/day. The rent and break-even requirements expose rental stress and a capacity deficit under the changed assumptions. |
| 3:30–4:00 | Click **Reset**, then click **Run feasibility analysis** once more. | Reset restores business inputs; outputs remain scenario-dependent and are not a guarantee. Close with OSM and benchmark-data limitations. |

The intended presentation is approximately four minutes, leaving time for
examiner questions. If an API call fails, describe the surfaced upstream
failure and use the documented mocked integration tests to explain the
deterministic verification; do not silently substitute invented live data.
