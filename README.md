# poe-market-analysis

Schemas for Path of Exile market CSVs in the Phrecia league.

## Layout
- `Phrecia/Phrecia.currency.csv` -> `CurrencyRow`
- `Phrecia/Phrecia.items.csv` -> `ItemRow`
- `src/poe_market_analysis/schemas.py` contains the schema models and CSV loaders.

## Environment setup
### venv (already created)
```bash
source .venv/bin/activate
python -m pip install -U pip
```

### pipenv
```bash
pip install --user pipenv
pipenv install
pipenv shell
```

## Quick usage
```python
from poe_market_analysis import read_currency_rows, read_item_rows

currency_rows = list(read_currency_rows("Phrecia/Phrecia.currency.csv"))
item_rows = list(read_item_rows("Phrecia/Phrecia.items.csv"))
```
