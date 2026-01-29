from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

START_DATE = date(2025, 2, 20)
END_DATE = date(2025, 3, 20)
CSV_DELIMITER = ";"

ANALYSIS_DIR = Path("analysis")
FILTERED_DIR = ANALYSIS_DIR / "filtered"
STRATEGY_DIR = ANALYSIS_DIR / "strategy"

CURRENCY_INPUT = FILTERED_DIR / "Phrecia.currency.filtered.csv"
ITEMS_INPUT = FILTERED_DIR / "Phrecia.items.filtered.csv"

STRATEGY_DAILY_OUTPUT = STRATEGY_DIR / "strategy_daily.csv"
STRATEGY_TRADES_OUTPUT = STRATEGY_DIR / "strategy_trades.csv"
STRATEGY_SUMMARY_OUTPUT = STRATEGY_DIR / "strategy_summary.csv"

STARTING_CAPITAL = 100.0


@dataclass(frozen=True)
class AssetMeta:
    asset_id: str
    asset_type: str
    fields: Dict[str, str]


@dataclass(frozen=True)
class Trade:
    asset_id: str
    asset_type: str
    buy_date: date
    sell_date: date
    buy_price: float
    sell_price: float
    capital_start: float
    capital_end: float

    @property
    def gain(self) -> float:
        return self.capital_end - self.capital_start

    @property
    def gain_pct(self) -> float:
        if self.capital_start <= 0:
            return 0.0
        return self.gain / self.capital_start


@dataclass(frozen=True)
class DailyChoice:
    day: date
    asset_id: Optional[str]
    asset_type: Optional[str]
    buy_price: Optional[float]
    sell_price: Optional[float]
    factor: float


def main() -> None:
    if not CURRENCY_INPUT.exists() or not ITEMS_INPUT.exists():
        raise FileNotFoundError(
            "Expected filtered datasets in analysis/. Run scripts/phrecia_time_series_analysis.py first."
        )

    STRATEGY_DIR.mkdir(parents=True, exist_ok=True)

    dates = build_dates()

    currency_prices, currency_meta = load_currency_prices(CURRENCY_INPUT)
    item_prices, item_meta = load_item_prices(ITEMS_INPUT)

    price_map: Dict[str, Dict[date, float]] = {}
    price_map.update(currency_prices)
    price_map.update(item_prices)

    meta_map: Dict[str, AssetMeta] = {}
    meta_map.update(currency_meta)
    meta_map.update(item_meta)

    best_daily = compute_best_daily_choices(dates, price_map, meta_map)
    trades, final_capital = simulate_strategy(dates, best_daily, price_map)

    write_daily_choices(best_daily, meta_map)
    write_trades(trades, meta_map)
    write_summary(final_capital)


# ----------------------------
# Data loading
# ----------------------------

def load_currency_prices(
    path: Path,
) -> Tuple[Dict[str, Dict[date, float]], Dict[str, AssetMeta]]:
    sums: Dict[Tuple[str, str, date], float] = {}
    counts: Dict[Tuple[str, str, date], int] = {}
    meta: Dict[str, AssetMeta] = {}

    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=CSV_DELIMITER)
        for row in reader:
            if row["Pay"] != "Chaos Orb":
                continue
            row_date = date.fromisoformat(row["Date"])
            key = (row["League"], row["Get"], row_date)
            sums[key] = sums.get(key, 0.0) + float(row["Value"])
            counts[key] = counts.get(key, 0) + 1

    prices: Dict[str, Dict[date, float]] = {}

    for (league, get, row_date), total in sums.items():
        count = counts[(league, get, row_date)]
        asset_id = f"currency|{get}"
        prices.setdefault(asset_id, {})[row_date] = total / count
        if asset_id not in meta:
            meta[asset_id] = AssetMeta(
                asset_id=asset_id,
                asset_type="currency",
                fields={
                    "League": league,
                    "Get": get,
                    "Pay": "Chaos Orb",
                },
            )

    return prices, meta


def load_item_prices(
    path: Path,
) -> Tuple[Dict[str, Dict[date, float]], Dict[str, AssetMeta]]:
    sums: Dict[Tuple[str, str, str, str, str, str, date], float] = {}
    counts: Dict[Tuple[str, str, str, str, str, str, date], int] = {}
    meta: Dict[str, AssetMeta] = {}

    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=CSV_DELIMITER)
        for row in reader:
            row_date = date.fromisoformat(row["Date"])
            key = (
                row["League"],
                row["Id"],
                row["Type"],
                row["Name"],
                row["Variant"],
                row["Links"],
                row_date,
            )
            sums[key] = sums.get(key, 0.0) + float(row["Value"])
            counts[key] = counts.get(key, 0) + 1

    prices: Dict[str, Dict[date, float]] = {}

    for (league, item_id, item_type, name, variant, links, row_date), total in sums.items():
        count = counts[(league, item_id, item_type, name, variant, links, row_date)]
        asset_id = f"item|{item_id}|{variant or ''}|{links or ''}"
        prices.setdefault(asset_id, {})[row_date] = total / count
        if asset_id not in meta:
            meta[asset_id] = AssetMeta(
                asset_id=asset_id,
                asset_type="item",
                fields={
                    "League": league,
                    "Id": item_id,
                    "Type": item_type,
                    "Name": name,
                    "Variant": variant,
                    "Links": links,
                },
            )

    return prices, meta


# ----------------------------
# Strategy
# ----------------------------

def compute_best_daily_choices(
    dates: List[date],
    prices: Dict[str, Dict[date, float]],
    meta: Dict[str, AssetMeta],
) -> Dict[date, DailyChoice]:
    best: Dict[date, DailyChoice] = {}

    for idx in range(len(dates) - 1):
        day = dates[idx]
        next_day = dates[idx + 1]
        best_factor = 1.0
        best_asset: Optional[str] = None
        best_buy_price: Optional[float] = None
        best_sell_price: Optional[float] = None

        for asset_id, series in prices.items():
            if day not in series or next_day not in series:
                continue
            buy_price = series[day]
            sell_price = series[next_day]
            if buy_price <= 0:
                continue
            factor = sell_price / buy_price
            if factor > best_factor:
                best_factor = factor
                best_asset = asset_id
                best_buy_price = buy_price
                best_sell_price = sell_price

        asset_type = meta[best_asset].asset_type if best_asset else None
        best[day] = DailyChoice(
            day=day,
            asset_id=best_asset,
            asset_type=asset_type,
            buy_price=best_buy_price,
            sell_price=best_sell_price,
            factor=best_factor,
        )

    return best


def simulate_strategy(
    dates: List[date],
    daily_choices: Dict[date, DailyChoice],
    prices: Dict[str, Dict[date, float]],
) -> Tuple[List[Trade], float]:
    capital = STARTING_CAPITAL
    trades: List[Trade] = []

    open_asset: Optional[str] = None
    open_buy_date: Optional[date] = None
    open_buy_price: Optional[float] = None
    open_units: Optional[float] = None
    open_capital: Optional[float] = None

    for idx in range(len(dates) - 1):
        day = dates[idx]
        choice = daily_choices[day]
        next_day = dates[idx + 1]

        if choice.asset_id != open_asset:
            if open_asset is not None:
                sell_price = prices[open_asset][day]
                capital = open_units * sell_price
                trades.append(
                    Trade(
                        asset_id=open_asset,
                        asset_type="",
                        buy_date=open_buy_date,
                        sell_date=day,
                        buy_price=open_buy_price,
                        sell_price=sell_price,
                        capital_start=open_capital,
                        capital_end=capital,
                    )
                )
                open_asset = None
                open_buy_date = None
                open_buy_price = None
                open_units = None
                open_capital = None

            if choice.asset_id is not None:
                open_asset = choice.asset_id
                open_buy_date = day
                open_buy_price = prices[open_asset][day]
                open_units = capital / open_buy_price
                open_capital = capital

        if choice.asset_id is None:
            continue

    if open_asset is not None:
        final_day = dates[-1]
        sell_price = prices[open_asset][final_day]
        capital = open_units * sell_price
        trades.append(
            Trade(
                asset_id=open_asset,
                asset_type="",
                buy_date=open_buy_date,
                sell_date=final_day,
                buy_price=open_buy_price,
                sell_price=sell_price,
                capital_start=open_capital,
                capital_end=capital,
            )
        )

    return trades, capital


# ----------------------------
# Outputs
# ----------------------------

def write_daily_choices(choices: Dict[date, DailyChoice], meta: Dict[str, AssetMeta]) -> None:
    fieldnames = [
        "Date",
        "AssetId",
        "AssetType",
        "BuyPrice",
        "SellPrice",
        "Factor",
    ]
    with open(STRATEGY_DAILY_OUTPUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for day in sorted(choices.keys()):
            choice = choices[day]
            writer.writerow(
                {
                    "Date": day.isoformat(),
                    "AssetId": choice.asset_id or "",
                    "AssetType": choice.asset_type or "",
                    "BuyPrice": round(choice.buy_price, 6) if choice.buy_price is not None else "",
                    "SellPrice": round(choice.sell_price, 6) if choice.sell_price is not None else "",
                    "Factor": round(choice.factor, 6),
                }
            )


def write_trades(trades: List[Trade], meta: Dict[str, AssetMeta]) -> None:
    fieldnames = [
        "AssetId",
        "AssetType",
        "BuyDate",
        "SellDate",
        "BuyPrice",
        "SellPrice",
        "CapitalStart",
        "CapitalEnd",
        "Gain",
        "GainPct",
        "League",
        "Get",
        "Pay",
        "Id",
        "Type",
        "Name",
        "Variant",
        "Links",
    ]
    with open(STRATEGY_TRADES_OUTPUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for trade in trades:
            asset_meta = meta.get(trade.asset_id)
            fields = asset_meta.fields if asset_meta else {}
            writer.writerow(
                {
                    "AssetId": trade.asset_id,
                    "AssetType": asset_meta.asset_type if asset_meta else "",
                    "BuyDate": trade.buy_date.isoformat(),
                    "SellDate": trade.sell_date.isoformat(),
                    "BuyPrice": round(trade.buy_price, 6),
                    "SellPrice": round(trade.sell_price, 6),
                    "CapitalStart": round(trade.capital_start, 6),
                    "CapitalEnd": round(trade.capital_end, 6),
                    "Gain": round(trade.gain, 6),
                    "GainPct": round(trade.gain_pct, 6),
                    "League": fields.get("League", ""),
                    "Get": fields.get("Get", ""),
                    "Pay": fields.get("Pay", ""),
                    "Id": fields.get("Id", ""),
                    "Type": fields.get("Type", ""),
                    "Name": fields.get("Name", ""),
                    "Variant": fields.get("Variant", ""),
                    "Links": fields.get("Links", ""),
                }
            )


def write_summary(final_capital: float) -> None:
    fieldnames = ["StartingCapital", "EndingCapital", "TotalReturnPct"]
    total_return = 0.0
    if STARTING_CAPITAL > 0:
        total_return = (final_capital - STARTING_CAPITAL) / STARTING_CAPITAL

    with open(STRATEGY_SUMMARY_OUTPUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "StartingCapital": round(STARTING_CAPITAL, 6),
                "EndingCapital": round(final_capital, 6),
                "TotalReturnPct": round(total_return, 6),
            }
        )


# ----------------------------
# Utility
# ----------------------------

def build_dates() -> List[date]:
    dates: List[date] = []
    current = START_DATE
    while current <= END_DATE:
        dates.append(current)
        current += timedelta(days=1)
    return dates


if __name__ == "__main__":
    main()
