from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

START_DATE = date(2025, 2, 20)
END_DATE = date(2025, 3, 20)
FIRST_WEEK_END = START_DATE + timedelta(days=6)
CSV_DELIMITER = ";"

ANALYSIS_DIR = Path("analysis")
FILTERED_DIR = ANALYSIS_DIR / "filtered"
STRATEGY_DIR = ANALYSIS_DIR / "strategy"

CURRENCY_INPUT = FILTERED_DIR / "Phrecia.currency.filtered.csv"
ITEMS_INPUT = FILTERED_DIR / "Phrecia.items.filtered.csv"

BEST_DAILY_OUTPUT = STRATEGY_DIR / "best_daily.csv"

ALL_IN_DIR = STRATEGY_DIR / "all_in"
EQUAL_SPLIT_DIR = STRATEGY_DIR / "equal_split"
GREEDY_ONE_UNIT_DIR = STRATEGY_DIR / "greedy_one_unit"

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
    units: float
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


@dataclass(frozen=True)
class Opportunity:
    asset_id: str
    buy_date: date
    sell_date: date
    buy_price: float
    sell_price: float
    gain_pct: float


@dataclass(frozen=True)
class StrategyOutputs:
    daily_path: Path
    trades_path: Path
    summary_path: Path


@dataclass(frozen=True)
class DailySummary:
    day: date
    capital_start: float
    capital_end: float
    invested: float
    cash_left: float
    trade_count: int


def main() -> None:
    if not CURRENCY_INPUT.exists() or not ITEMS_INPUT.exists():
        raise FileNotFoundError(
            "Expected filtered datasets in analysis/. Run scripts/phrecia_time_series_analysis.py first."
        )

    STRATEGY_DIR.mkdir(parents=True, exist_ok=True)
    ALL_IN_DIR.mkdir(parents=True, exist_ok=True)
    EQUAL_SPLIT_DIR.mkdir(parents=True, exist_ok=True)
    GREEDY_ONE_UNIT_DIR.mkdir(parents=True, exist_ok=True)

    dates = build_dates(START_DATE, FIRST_WEEK_END)

    currency_prices, currency_meta = load_currency_prices(CURRENCY_INPUT)
    item_prices, item_meta = load_item_prices(ITEMS_INPUT)

    price_map: Dict[str, Dict[date, float]] = {}
    price_map.update(currency_prices)
    price_map.update(item_prices)

    meta_map: Dict[str, AssetMeta] = {}
    meta_map.update(currency_meta)
    meta_map.update(item_meta)

    best_daily = compute_best_daily_choices(dates, price_map, meta_map)
    opportunities = build_opportunities(dates, price_map)

    write_best_daily_choices(best_daily, meta_map)

    strategies = {
        "all_in": StrategyOutputs(
            daily_path=ALL_IN_DIR / "daily.csv",
            trades_path=ALL_IN_DIR / "trades.csv",
            summary_path=ALL_IN_DIR / "summary.csv",
        ),
        "equal_split": StrategyOutputs(
            daily_path=EQUAL_SPLIT_DIR / "daily.csv",
            trades_path=EQUAL_SPLIT_DIR / "trades.csv",
            summary_path=EQUAL_SPLIT_DIR / "summary.csv",
        ),
        "greedy_one_unit": StrategyOutputs(
            daily_path=GREEDY_ONE_UNIT_DIR / "daily.csv",
            trades_path=GREEDY_ONE_UNIT_DIR / "trades.csv",
            summary_path=GREEDY_ONE_UNIT_DIR / "summary.csv",
        ),
    }

    for strategy_name, outputs in strategies.items():
        daily_summaries, trades, ending_capital = simulate_daily_strategy(
            dates, opportunities, strategy_name
        )
        write_daily_summary(outputs.daily_path, daily_summaries)
        write_trades(outputs.trades_path, trades, meta_map)
        write_summary(outputs.summary_path, trades, ending_capital)


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
                    "Name": get,
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
            if row["Type"] == "BaseType":
                continue
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


def build_opportunities(
    dates: List[date],
    prices: Dict[str, Dict[date, float]],
) -> Dict[date, List[Opportunity]]:
    opportunities: Dict[date, List[Opportunity]] = {}

    for asset_id, series in prices.items():
        for idx in range(len(dates) - 1):
            day = dates[idx]
            next_day = dates[idx + 1]
            if day not in series or next_day not in series:
                continue
            buy_price = series[day]
            sell_price = series[next_day]
            if buy_price <= 0 or sell_price <= buy_price:
                continue
            gain_pct = (sell_price - buy_price) / buy_price
            opportunities.setdefault(day, []).append(
                Opportunity(
                    asset_id=asset_id,
                    buy_date=day,
                    sell_date=next_day,
                    buy_price=buy_price,
                    sell_price=sell_price,
                    gain_pct=gain_pct,
                )
            )

    return opportunities


def simulate_daily_strategy(
    dates: List[date],
    opportunities: Dict[date, List[Opportunity]],
    strategy_name: str,
) -> Tuple[List[DailySummary], List[Trade], float]:
    capital = STARTING_CAPITAL
    trades: List[Trade] = []
    summaries: List[DailySummary] = []

    for idx in range(len(dates) - 1):
        day = dates[idx]
        daily_opps = opportunities.get(day, [])
        if strategy_name == "all_in":
            day_trades, cash_left = allocate_all_in(daily_opps, capital)
        elif strategy_name == "equal_split":
            day_trades, cash_left = allocate_equal_split(daily_opps, capital)
        elif strategy_name == "greedy_one_unit":
            day_trades, cash_left = allocate_greedy_one_unit(daily_opps, capital)
        else:
            raise ValueError(f"Unknown strategy {strategy_name}")

        invested = sum(trade.capital_start for trade in day_trades)
        proceeds = sum(trade.capital_end for trade in day_trades)
        capital_next = cash_left + proceeds

        summaries.append(
            DailySummary(
                day=day,
                capital_start=capital,
                capital_end=capital_next,
                invested=invested,
                cash_left=cash_left,
                trade_count=len(day_trades),
            )
        )
        trades.extend(day_trades)
        capital = capital_next

    return summaries, trades, capital


def allocate_all_in(
    opportunities: List[Opportunity],
    capital: float,
) -> Tuple[List[Trade], float]:
    if not opportunities:
        return [], capital
    best = max(opportunities, key=lambda opp: opp.gain_pct)
    units = capital / best.buy_price
    trade = Trade(
        asset_id=best.asset_id,
        asset_type="",
        buy_date=best.buy_date,
        sell_date=best.sell_date,
        buy_price=best.buy_price,
        sell_price=best.sell_price,
        units=units,
        capital_start=capital,
        capital_end=units * best.sell_price,
    )
    return [trade], 0.0


def allocate_equal_split(
    opportunities: List[Opportunity],
    capital: float,
) -> Tuple[List[Trade], float]:
    if not opportunities:
        return [], capital
    allocation = capital / len(opportunities)
    trades: List[Trade] = []
    for opp in opportunities:
        units = allocation / opp.buy_price
        trades.append(
            Trade(
                asset_id=opp.asset_id,
                asset_type="",
                buy_date=opp.buy_date,
                sell_date=opp.sell_date,
                buy_price=opp.buy_price,
                sell_price=opp.sell_price,
                units=units,
                capital_start=allocation,
                capital_end=units * opp.sell_price,
            )
        )
    return trades, 0.0


def allocate_greedy_one_unit(
    opportunities: List[Opportunity],
    capital: float,
) -> Tuple[List[Trade], float]:
    if not opportunities:
        return [], capital
    remaining = capital
    trades: List[Trade] = []
    for opp in sorted(opportunities, key=lambda item: item.gain_pct, reverse=True):
        if opp.buy_price > remaining:
            continue
        remaining -= opp.buy_price
        trades.append(
            Trade(
                asset_id=opp.asset_id,
                asset_type="",
                buy_date=opp.buy_date,
                sell_date=opp.sell_date,
                buy_price=opp.buy_price,
                sell_price=opp.sell_price,
                units=1.0,
                capital_start=opp.buy_price,
                capital_end=opp.sell_price,
            )
        )
    return trades, remaining


# ----------------------------
# Outputs
# ----------------------------

def write_best_daily_choices(choices: Dict[date, DailyChoice], meta: Dict[str, AssetMeta]) -> None:
    fieldnames = [
        "Date",
        "AssetId",
        "AssetType",
        "Name",
        "BaseType",
        "BuyPrice",
        "SellPrice",
        "Factor",
    ]
    with open(BEST_DAILY_OUTPUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for day in sorted(choices.keys()):
            choice = choices[day]
            asset_fields = meta[choice.asset_id].fields if choice.asset_id in meta else {}
            writer.writerow(
                {
                    "Date": day.isoformat(),
                    "AssetId": choice.asset_id or "",
                    "AssetType": choice.asset_type or "",
                    "Name": asset_fields.get("Name", ""),
                    "BaseType": asset_fields.get("BaseType", ""),
                    "BuyPrice": round(choice.buy_price, 6) if choice.buy_price is not None else "",
                    "SellPrice": round(choice.sell_price, 6) if choice.sell_price is not None else "",
                    "Factor": round(choice.factor, 6),
                }
            )

def write_daily_summary(path: Path, summaries: List[DailySummary]) -> None:
    fieldnames = [
        "Date",
        "CapitalStart",
        "CapitalEnd",
        "Invested",
        "CashLeft",
        "TradeCount",
    ]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for summary in summaries:
            writer.writerow(
                {
                    "Date": summary.day.isoformat(),
                    "CapitalStart": round(summary.capital_start, 6),
                    "CapitalEnd": round(summary.capital_end, 6),
                    "Invested": round(summary.invested, 6),
                    "CashLeft": round(summary.cash_left, 6),
                    "TradeCount": summary.trade_count,
                }
            )


def write_trades(path: Path, trades: List[Trade], meta: Dict[str, AssetMeta]) -> None:
    fieldnames = [
        "AssetId",
        "AssetType",
        "BuyDate",
        "SellDate",
        "BuyPrice",
        "SellPrice",
        "Units",
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
        "BaseType",
        "Variant",
        "Links",
    ]
    with open(path, "w", newline="", encoding="utf-8") as handle:
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
                    "Units": round(trade.units, 6),
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
                    "BaseType": fields.get("BaseType", ""),
                    "Variant": fields.get("Variant", ""),
                    "Links": fields.get("Links", ""),
                }
            )


def write_summary(path: Path, trades: List[Trade], final_capital: float) -> None:
    fieldnames = [
        "WindowStart",
        "WindowEnd",
        "StartingCapital",
        "EndingCapital",
        "TotalReturnPct",
        "TradeCount",
        "AvgGainPct",
        "MedianGainPct",
    ]
    gain_pcts = sorted(trade.gain_pct for trade in trades)
    avg_gain = sum(gain_pcts) / len(gain_pcts) if gain_pcts else 0.0
    median_gain = 0.0
    if gain_pcts:
        mid = len(gain_pcts) // 2
        if len(gain_pcts) % 2 == 1:
            median_gain = gain_pcts[mid]
        else:
            median_gain = (gain_pcts[mid - 1] + gain_pcts[mid]) / 2

    total_return = 0.0
    if STARTING_CAPITAL > 0:
        total_return = (final_capital - STARTING_CAPITAL) / STARTING_CAPITAL

    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "WindowStart": START_DATE.isoformat(),
                "WindowEnd": FIRST_WEEK_END.isoformat(),
                "StartingCapital": round(STARTING_CAPITAL, 6),
                "EndingCapital": round(final_capital, 6),
                "TotalReturnPct": round(total_return, 6),
                "TradeCount": len(trades),
                "AvgGainPct": round(avg_gain, 6),
                "MedianGainPct": round(median_gain, 6),
            }
        )


# ----------------------------
# Utility
# ----------------------------

def build_dates(start: date, end: date) -> List[date]:
    dates: List[date] = []
    current = start
    while current <= end:
        dates.append(current)
        current += timedelta(days=1)
    return dates


if __name__ == "__main__":
    main()
