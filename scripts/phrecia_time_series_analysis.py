from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

START_DATE = date(2025, 2, 20)
END_DATE = date(2025, 3, 20)
CSV_DELIMITER = ";"

PHRECIA_DIR = Path("Phrecia")
ANALYSIS_DIR = Path("analysis")
FILTERED_DIR = ANALYSIS_DIR / "filtered"
MOVING_AVG_DIR = ANALYSIS_DIR / "moving_avg"
TRADES_DIR = ANALYSIS_DIR / "trades"

CURRENCY_INPUT = PHRECIA_DIR / "Phrecia.currency.csv"
ITEMS_INPUT = PHRECIA_DIR / "Phrecia.items.csv"

CURRENCY_FILTERED = FILTERED_DIR / "Phrecia.currency.filtered.csv"
ITEMS_FILTERED = FILTERED_DIR / "Phrecia.items.filtered.csv"

CURRENCY_MA_OUTPUT = MOVING_AVG_DIR / "currency_daily_ma.csv"
ITEMS_MA_OUTPUT = MOVING_AVG_DIR / "items_daily_ma.csv"

CURRENCY_TRADES_OUTPUT = TRADES_DIR / "currency_best_trades.csv"
ITEMS_TRADES_OUTPUT = TRADES_DIR / "items_best_trades.csv"

CURRENCY_ALL_TRADES_OUTPUT = TRADES_DIR / "currency_profitable_trades.csv"
ITEMS_ALL_TRADES_OUTPUT = TRADES_DIR / "items_profitable_trades.csv"


@dataclass(frozen=True)
class DailyValue:
    day: date
    value: float


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze Phrecia time-series data for moving averages and trades."
    )
    parser.add_argument(
        "--min-gain",
        type=float,
        default=0.0,
        help="Minimum absolute gain for a trade to be included.",
    )
    parser.add_argument(
        "--min-gain-pct",
        type=float,
        default=None,
        help="Minimum gain percentage (e.g. 0.2 for 20%%) to include a trade.",
    )
    args = parser.parse_args()

    FILTERED_DIR.mkdir(parents=True, exist_ok=True)
    MOVING_AVG_DIR.mkdir(parents=True, exist_ok=True)
    TRADES_DIR.mkdir(parents=True, exist_ok=True)

    currency_daily = filter_and_aggregate_currency()
    items_daily = filter_and_aggregate_items()

    write_currency_daily_ma(currency_daily)
    write_items_daily_ma(items_daily)

    write_best_trades_currency(currency_daily)
    write_best_trades_items(items_daily)

    write_profitable_trades_currency(
        currency_daily, min_gain=args.min_gain, min_gain_pct=args.min_gain_pct
    )
    write_profitable_trades_items(
        items_daily, min_gain=args.min_gain, min_gain_pct=args.min_gain_pct
    )


# ----------------------------
# Filtering + aggregation
# ----------------------------

def filter_and_aggregate_currency() -> Dict[Tuple[str, str, str], Dict[date, Tuple[float, int]]]:
    daily: Dict[Tuple[str, str, str], Dict[date, Tuple[float, int]]] = defaultdict(dict)

    with open(CURRENCY_INPUT, newline="", encoding="utf-8") as read_handle, open(
        CURRENCY_FILTERED, "w", newline="", encoding="utf-8"
    ) as write_handle:
        reader = csv.DictReader(read_handle, delimiter=CSV_DELIMITER)
        writer = csv.DictWriter(write_handle, fieldnames=reader.fieldnames, delimiter=CSV_DELIMITER)
        writer.writeheader()

        for row in reader:
            row_date = parse_date(row["Date"])
            if not in_range(row_date):
                continue
            writer.writerow(row)

            key = (row["League"], row["Get"], row["Pay"])
            current_sum, current_count = daily[key].get(row_date, (0.0, 0))
            daily[key][row_date] = (current_sum + float(row["Value"]), current_count + 1)

    return daily


def filter_and_aggregate_items() -> Dict[Tuple[str, str, str, str, str, str, str], Dict[date, Tuple[float, int]]]:
    daily: Dict[Tuple[str, str, str, str, str, str, str], Dict[date, Tuple[float, int]]] = defaultdict(dict)

    with open(ITEMS_INPUT, newline="", encoding="utf-8") as read_handle, open(
        ITEMS_FILTERED, "w", newline="", encoding="utf-8"
    ) as write_handle:
        reader = csv.DictReader(read_handle, delimiter=CSV_DELIMITER)
        writer = csv.DictWriter(write_handle, fieldnames=reader.fieldnames, delimiter=CSV_DELIMITER)
        writer.writeheader()

        for row in reader:
            row_date = parse_date(row["Date"])
            if not in_range(row_date):
                continue
            writer.writerow(row)

            key = (
                row["League"],
                row["Id"],
                row["Type"],
                row["Name"],
                row["BaseType"],
                row["Variant"],
                row["Links"],
            )
            current_sum, current_count = daily[key].get(row_date, (0.0, 0))
            daily[key][row_date] = (current_sum + float(row["Value"]), current_count + 1)

    return daily


# ----------------------------
# Moving averages
# ----------------------------

def write_currency_daily_ma(
    daily: Dict[Tuple[str, str, str], Dict[date, Tuple[float, int]]]
) -> None:
    fieldnames = ["League", "Get", "Pay", "Date", "Value", "MA3"]
    with open(CURRENCY_MA_OUTPUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for (league, get, pay), series in daily.items():
            daily_values = build_daily_values(series)
            ma_values = moving_average(daily_values, window=3)
            for day_value, ma in zip(daily_values, ma_values):
                writer.writerow(
                    {
                        "League": league,
                        "Get": get,
                        "Pay": pay,
                        "Date": day_value.day.isoformat(),
                        "Value": round(day_value.value, 6),
                        "MA3": round(ma, 6),
                    }
                )


def write_items_daily_ma(
    daily: Dict[Tuple[str, str, str, str, str, str, str], Dict[date, Tuple[float, int]]]
) -> None:
    fieldnames = [
        "League",
        "Id",
        "Type",
        "Name",
        "BaseType",
        "Variant",
        "Links",
        "Date",
        "Value",
        "MA3",
    ]
    with open(ITEMS_MA_OUTPUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for (league, item_id, item_type, name, base_type, variant, links), series in daily.items():
            daily_values = build_daily_values(series)
            ma_values = moving_average(daily_values, window=3)
            for day_value, ma in zip(daily_values, ma_values):
                writer.writerow(
                    {
                        "League": league,
                        "Id": item_id,
                        "Type": item_type,
                        "Name": name,
                        "BaseType": base_type,
                        "Variant": variant,
                        "Links": links,
                        "Date": day_value.day.isoformat(),
                        "Value": round(day_value.value, 6),
                        "MA3": round(ma, 6),
                    }
                )


# ----------------------------
# Best trades
# ----------------------------

def write_best_trades_currency(
    daily: Dict[Tuple[str, str, str], Dict[date, Tuple[float, int]]]
) -> None:
    fieldnames = [
        "League",
        "Get",
        "Pay",
        "BuyDate",
        "BuyValue",
        "SellDate",
        "SellValue",
        "Gain",
        "GainPct",
    ]
    with open(CURRENCY_TRADES_OUTPUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for (league, get, pay), series in daily.items():
            trade = best_trade(build_daily_values(series))
            if trade is None:
                continue
            buy_day, buy_value, sell_day, sell_value, gain, gain_pct = trade
            writer.writerow(
                {
                    "League": league,
                    "Get": get,
                    "Pay": pay,
                    "BuyDate": buy_day.isoformat(),
                    "BuyValue": round(buy_value, 6),
                    "SellDate": sell_day.isoformat(),
                    "SellValue": round(sell_value, 6),
                    "Gain": round(gain, 6),
                    "GainPct": round(gain_pct, 6) if gain_pct is not None else "",
                }
            )


def write_best_trades_items(
    daily: Dict[Tuple[str, str, str, str, str, str, str], Dict[date, Tuple[float, int]]]
) -> None:
    fieldnames = [
        "League",
        "Id",
        "Type",
        "Name",
        "BaseType",
        "Variant",
        "Links",
        "BuyDate",
        "BuyValue",
        "SellDate",
        "SellValue",
        "Gain",
        "GainPct",
    ]
    with open(ITEMS_TRADES_OUTPUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for (league, item_id, item_type, name, base_type, variant, links), series in daily.items():
            trade = best_trade(build_daily_values(series))
            if trade is None:
                continue
            buy_day, buy_value, sell_day, sell_value, gain, gain_pct = trade
            writer.writerow(
                {
                    "League": league,
                    "Id": item_id,
                    "Type": item_type,
                    "Name": name,
                    "BaseType": base_type,
                    "Variant": variant,
                    "Links": links,
                    "BuyDate": buy_day.isoformat(),
                    "BuyValue": round(buy_value, 6),
                    "SellDate": sell_day.isoformat(),
                    "SellValue": round(sell_value, 6),
                    "Gain": round(gain, 6),
                    "GainPct": round(gain_pct, 6) if gain_pct is not None else "",
                }
            )


def write_profitable_trades_currency(
    daily: Dict[Tuple[str, str, str], Dict[date, Tuple[float, int]]],
    *,
    min_gain: float,
    min_gain_pct: Optional[float],
) -> None:
    fieldnames = [
        "League",
        "Get",
        "Pay",
        "BuyDate",
        "BuyValue",
        "SellDate",
        "SellValue",
        "Gain",
        "GainPct",
    ]
    with open(CURRENCY_ALL_TRADES_OUTPUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for (league, get, pay), series in daily.items():
            for trade in iter_profitable_trades(
                build_daily_values(series),
                min_gain=min_gain,
                min_gain_pct=min_gain_pct,
            ):
                buy_day, buy_value, sell_day, sell_value, gain, gain_pct = trade
                writer.writerow(
                    {
                        "League": league,
                        "Get": get,
                        "Pay": pay,
                        "BuyDate": buy_day.isoformat(),
                        "BuyValue": round(buy_value, 6),
                        "SellDate": sell_day.isoformat(),
                        "SellValue": round(sell_value, 6),
                        "Gain": round(gain, 6),
                        "GainPct": round(gain_pct, 6) if gain_pct is not None else "",
                    }
                )


def write_profitable_trades_items(
    daily: Dict[Tuple[str, str, str, str, str, str, str], Dict[date, Tuple[float, int]]],
    *,
    min_gain: float,
    min_gain_pct: Optional[float],
) -> None:
    fieldnames = [
        "League",
        "Id",
        "Type",
        "Name",
        "BaseType",
        "Variant",
        "Links",
        "BuyDate",
        "BuyValue",
        "SellDate",
        "SellValue",
        "Gain",
        "GainPct",
    ]
    with open(ITEMS_ALL_TRADES_OUTPUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for (league, item_id, item_type, name, base_type, variant, links), series in daily.items():
            for trade in iter_profitable_trades(
                build_daily_values(series),
                min_gain=min_gain,
                min_gain_pct=min_gain_pct,
            ):
                buy_day, buy_value, sell_day, sell_value, gain, gain_pct = trade
                writer.writerow(
                    {
                        "League": league,
                        "Id": item_id,
                        "Type": item_type,
                        "Name": name,
                        "BaseType": base_type,
                        "Variant": variant,
                        "Links": links,
                        "BuyDate": buy_day.isoformat(),
                        "BuyValue": round(buy_value, 6),
                        "SellDate": sell_day.isoformat(),
                        "SellValue": round(sell_value, 6),
                        "Gain": round(gain, 6),
                        "GainPct": round(gain_pct, 6) if gain_pct is not None else "",
                    }
                )


# ----------------------------
# Helpers
# ----------------------------

def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def in_range(value: date) -> bool:
    return START_DATE <= value <= END_DATE


def build_daily_values(series: Dict[date, Tuple[float, int]]) -> List[DailyValue]:
    daily_values: List[DailyValue] = []
    for day in sorted(series.keys()):
        total, count = series[day]
        daily_values.append(DailyValue(day=day, value=total / count))
    return daily_values


def moving_average(values: Sequence[DailyValue], window: int) -> List[float]:
    if window <= 0:
        raise ValueError("window must be positive")

    ma: List[float] = []
    running_sum = 0.0
    window_values: List[float] = []

    for item in values:
        window_values.append(item.value)
        running_sum += item.value
        if len(window_values) > window:
            running_sum -= window_values.pop(0)
        ma.append(running_sum / len(window_values))

    return ma


def best_trade(values: Sequence[DailyValue]) -> Optional[Tuple[date, float, date, float, float, Optional[float]]]:
    if len(values) < 2:
        return None

    min_day = values[0].day
    min_value = values[0].value
    best_gain = float("-inf")
    best_buy_day = min_day
    best_buy_value = min_value
    best_sell_day = values[0].day
    best_sell_value = values[0].value

    for item in values[1:]:
        gain = item.value - min_value
        if gain > best_gain:
            best_gain = gain
            best_buy_day = min_day
            best_buy_value = min_value
            best_sell_day = item.day
            best_sell_value = item.value

        if item.value < min_value:
            min_value = item.value
            min_day = item.day

    gain_pct: Optional[float] = None
    if best_buy_value > 0:
        gain_pct = best_gain / best_buy_value

    return (
        best_buy_day,
        best_buy_value,
        best_sell_day,
        best_sell_value,
        best_gain,
        gain_pct,
    )


def iter_profitable_trades(
    values: Sequence[DailyValue],
    *,
    min_gain: float,
    min_gain_pct: Optional[float],
) -> Iterator[Tuple[date, float, date, float, float, Optional[float]]]:
    if len(values) < 2:
        return iter(())

    for idx, buy in enumerate(values[:-1]):
        for sell in values[idx + 1 :]:
            gain = sell.value - buy.value
            if gain <= min_gain:
                continue
            gain_pct: Optional[float] = None
            if buy.value > 0:
                gain_pct = gain / buy.value
                if min_gain_pct is not None and gain_pct < min_gain_pct:
                    continue
            elif min_gain_pct is not None:
                continue
            yield buy.day, buy.value, sell.day, sell.value, gain, gain_pct


if __name__ == "__main__":
    main()
