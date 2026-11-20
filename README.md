# Corporate Hedging and Renewable FP&A Simulation



All data is **SYNTHETIC**. No real clients, employers, assets or market observations are represented. This project connects corporate treasury risk management with a solar asset budget, debt model and lender monitoring.

## Run

From this folder in PowerShell:

```powershell
python tests/test_models.py
python run_all.py
python tests/test_outputs.py
python tests/test_independent.py
```

Requires Python 3, NumPy, pandas and openpyxl. No installation or network request occurs. Matplotlib and pytest were unavailable in the supplied runtime. Tests use plain assertions; charts are embedded in Excel. Change financial inputs in `python/config.py`, then rerun. Export layout settings are in the CONFIG block in `python/reporting.py`. The workbook is a calculated snapshot, not an interactive formula model. CSVs preserve 17 significant digits and numeric results reproduce from the seed; workbook ZIP metadata can differ between runs. README and Project Notes results describe the default configuration and must be refreshed after changing inputs; the generated policy memo follows configured values.

## Files

| Path | Purpose |
| :--- | :--- |
| `python/config.py` | Paths, column names, seeds and financial assumptions |
| `python/hedging.py` | Daily history, 36 monthly forecasts, forwards, swap coupons, MTM, effectiveness and VaR |
| `python/solar.py` | 240-month budget, calibrated tariff, debt sculpt, actuals, variance, reserves and scenarios |
| `python/reporting.py` | CSVs, workbook with chart, JSON summary and policy memo |
| `run_all.py` | Regenerate all outputs |
| `tests/` | Model invariants and generated-output checks |
| `data/` | Generated history, factors, exposures, solar budget and actuals |
| `outputs/synthetic_finance_model.xlsx` | Summary, assumptions and complete model schedules |
| `outputs/hedge_policy_and_fpa_report.md` | Hedge policy, accounting limits, variance narrative and covenant results |
| `outputs/summary.json` | Machine-readable headline results |
| `REVIEW.md` | Specification coverage, fixes, independent checks and remaining limits |

## Results

| Metric | Seed 815 result |
| :--- | ---: |
| Daily historical observations | 756 |
| Forecast months / monthly hedge positions | 36 / 108 |
| First-layer unhedged one-month 95% cash-flow VaR | $95,708 |
| First-layer hedged one-month 95% cash-flow VaR | $18,865 |
| First-layer VaR reduction | 80.29% |
| Educational effectiveness screens passed | 3 of 3 |
| Solar capacity / original debt | 50 MW / $70,000,000 |
| Calibrated flat PPA | $89.89/MWh |
| Budget DSCR / amortization term | 1.30x / 20 years |
| Actual minimum monthly DSCR | 1.073x |
| Actual covenant breaches at 1.15x | 1 of 36 months |
| Actual liquidity shortfall | $0 |
| Actual EBITDA variance over 36 months | ($394,579) |
| One-time inverter expense | $180,000 |
| Maximum consolidated cash conservation error | Less than $0.000001 |

## Methods and limits

Treasury uses a constant monthly EUR 1M revenue forecast, 120 tonnes of copper purchases and $40M floating debt. FX and copper cover 80%, 60% and 40% by successive forecast years. The swap covers all debt for 36 monthly coupons. Positive derivative settlement offsets falling EUR revenue, rising copper costs or rising floating interest. Only designated quantities enter effectiveness testing.

Risk factors use independent seeded lognormal FX and copper paths and a mean-reverting rate with a floor. Monthly future observations use every 21st synthetic business-day step. History dates and future monthly labels are illustrative; no market holiday or calendar-gap calibration is performed. No correlations, liquidity shocks, credit risk, bid/ask spreads, collateral, basis mismatch or forecast error are modeled. VaR uses 735 overlapping 21-day historical shocks applied to each month's cash flow separately. It does not measure whole-program MTM risk or aggregate 36-month cash risk.

Effectiveness regresses derivative changes on opposite-signed hypothetical item changes. Slope, R squared and gross absolute dollar-offset screens illustrate an ASC 815 style workflow. Exact matching intentionally gives perfect base effectiveness. These screens and the simplified OCI allocation do not establish compliance with ASC 815. OCI is a period change before settlement recycling. Dollar-offset denominator is the sum of absolute monthly item changes, not a signed cumulative ratio. Forward discounting uses a constant USD rate; swap coupons use a flat current-rate approximation.

Solar energy uses actual calendar month lengths, assumed 25% capacity factor, 98% availability, seasonal irradiance and 0.4% annual degradation. Opex starts at $1.8M annually with 2% escalation. A flat tariff is solved so budget CFADS supports $70M debt at 5% over 20 years with exactly 1.30x monthly DSCR. The tariff is a financing calibration, not an observed price or valuation. This avoids an undisclosed balloon or a debt resize.

CFADS equals EBITDA. Taxes, working capital, operating capex and financing fees are excluded. Initial cash and reserves are additional assumed equity funding; construction cost and equity returns are not modeled. DSRA targets the next six scheduled payments. Maintenance contributions are liquidity-limited; the full $600,000 year-five event draws its reserve and then unrestricted cash. Reserve spending is outside simplified CFADS. Covenant breaches block distributions. Negative unrestricted cash is explicitly reported as a funding shortfall. The simplified waterfall permits DSRA to support net cash deficits without lender-use restrictions. Conservation includes unrestricted cash, DSRA and maintenance reserves.

Actuals cover 36 months, with seeded irradiance noise, a recurring availability decline, higher recurring opex and a one-time inverter expense. The variance bridge exactly separates energy, price, recurring opex and one-time effects. Scenarios keep original debt service. P50 is the budget; P90 is an assumed 10% irradiance haircut, not a statistically estimated probability. Lower price and higher opex sensitivities are independent driver stresses.

## Verification and provenance

Seven model tests cover notional limits and layers, seed determinism, known linear effectiveness and rejection cases, MTM settlement reconciliation, OCI allocation, exact debt amortization, reserve/cash conservation, severe liquidity stress, variance bridges and fixed-debt scenario sensitivities. Date tests cover reordered schedules, missing debt dates and missing waterfall periods. Output tests compare every workbook data cell with its CSV, check finite numeric tables, chart references, author metadata, plain formatting and prohibited punctuation in authored text. Three independent scalar checks recompute VaR, calibrated PPA and debt, and EBITDA variance with consolidated cash conservation from exported data.

No external data source was used or attempted. Installed NumPy, pandas and openpyxl worked. Maintenance tests verify that the full obligation is paid and conserved across cash accounts even when its reserve is insufficient. Reviewer fixes and numerical evidence are recorded in `REVIEW.md`.
