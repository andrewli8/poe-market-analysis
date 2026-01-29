# poe-market-analysis

Time-series analysis and strategy exploration for Path of Exile market CSVs (Phrecia).

## Project layout
- `Phrecia/` raw CSV inputs (gitignored)
  - `Phrecia.currency.csv`
  - `Phrecia.items.csv`
- `analysis/` generated outputs (gitignored)
  - `filtered/` 1‑month window CSVs
  - `moving_avg/` daily moving averages
  - `trades/` best + all profitable trades
  - `strategy/` capital‑constrained strategy outputs + charts
- `scripts/` analysis + chart generation
- `src/poe_market_analysis/` schema models + loaders

## Environment setup
### venv (recommended)
```bash
source .venv/bin/activate
python -m pip install -U pip
```

### Dependencies for analysis + charts
```bash
python -m pip install pandas seaborn matplotlib
```

## Schema usage (optional)
```python
from poe_market_analysis import read_currency_rows, read_item_rows

currency_rows = list(read_currency_rows("Phrecia/Phrecia.currency.csv"))
item_rows = list(read_item_rows("Phrecia/Phrecia.items.csv"))
```

## Analysis workflow
1) Ensure the raw CSVs exist in `Phrecia/`:
   - `Phrecia/Phrecia.currency.csv`
   - `Phrecia/Phrecia.items.csv`

2) Generate filtered data, moving averages, and trade lists:
```bash
python scripts/phrecia_time_series_analysis.py
```
Outputs:
- `analysis/filtered/*`
- `analysis/moving_avg/*`
- `analysis/trades/*`

3) Generate first‑week strategy outputs (multiple allocation modes):
```bash
python scripts/phrecia_strategy.py
```
Outputs:
- `analysis/strategy/all_in/*`
- `analysis/strategy/equal_split/*`
- `analysis/strategy/greedy_one_unit/*`
- `analysis/strategy/best_daily.csv`

4) Generate the “avg gain top‑3 per type” lollipop chart:
```bash
python scripts/phrecia_type_avg_lollipop_seaborn.py
```
Outputs:
- `analysis/strategy/type_avg_gain_top3.csv`
- `analysis/strategy/type_avg_gain_top3_lollipop_seaborn.png`
- `analysis/strategy/type_avg_gain_top3_lollipop_seaborn.svg`

5) Generate Gantt charts (top 3 trades per type):
```bash
python scripts/phrecia_type_top3_gantt.py
```
Outputs:
- `analysis/strategy/type_top3_gantt.png`
- `analysis/strategy/type_top3_gantt.svg`

6) Generate custom Gantt charts (unique + stable buckets):
```bash
python scripts/phrecia_custom_gantt.py
```
Outputs:
- `analysis/strategy/unique_gantt.*`
- `analysis/strategy/stable_gantt.*`

## Notes
- The raw `Phrecia/` and generated `analysis/` folders are gitignored to avoid large‑file commits.
- All scripts assume the first‑week window is 2025‑02‑20 → 2025‑02‑26 unless otherwise stated in the script.
