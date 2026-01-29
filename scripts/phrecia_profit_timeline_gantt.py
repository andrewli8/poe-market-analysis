from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from collections import defaultdict
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp")

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import csv

START_DATE = date(2025, 2, 20)
END_DATE = date(2025, 2, 26)
STARTING_CAPITAL = 100.0
CSV_DELIMITER = ";"

FILTERED_DIR = Path("analysis/filtered")
CURRENCY_INPUT = FILTERED_DIR / "Phrecia.currency.filtered.csv"
ITEMS_INPUT = FILTERED_DIR / "Phrecia.items.filtered.csv"

OUTPUT_DIR = Path("analysis/strategy")

UNIQUE_TYPES = [
    "UniqueWeapon",
    "UniqueArmour",
    "UniqueJewel",
    "UniqueAccessory",
    "UniqueFlask",
]

STABLE_TYPES = [
    "Tattoo",
    "DivinationCard",
    "Scarab",
    "Currency",
]

STYLE = {
    "background": "#f6f4ef",
    "grid": "#e0dad1",
    "spine": "#d8d0c4",
    "edge": "#0b1320",
    "text": "#0b1320",
}


@dataclass(frozen=True)
class Trade:
    asset_id: str
    name: str
    type_name: str
    buy_date: date
    sell_date: date
    buy_price: float
    sell_price: float

    @property
    def gain_pct(self) -> float:
        if self.buy_price <= 0:
            return 0.0
        return (self.sell_price - self.buy_price) / self.buy_price


@dataclass(frozen=True)
class TradeLogEntry:
    trade: Trade
    capital_start: float
    capital_end: float
    units: float


@dataclass(frozen=True)
class AssetSeries:
    asset_id: str
    type_name: str
    name: str
    series: dict[date, float]


def build_dates() -> list[date]:
    dates = []
    current = START_DATE
    while current <= END_DATE:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def load_currency_series() -> dict[str, AssetSeries]:
    sums: dict[tuple[str, str, date], float] = {}
    counts: dict[tuple[str, str, date], int] = {}
    league_by_get: dict[str, str] = {}

    with open(CURRENCY_INPUT, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=CSV_DELIMITER)
        for row in reader:
            if row["Pay"] != "Chaos Orb":
                continue
            row_date = date.fromisoformat(row["Date"])
            if row_date < START_DATE or row_date > END_DATE:
                continue
            key = (row["League"], row["Get"], row_date)
            sums[key] = sums.get(key, 0.0) + float(row["Value"])
            counts[key] = counts.get(key, 0) + 1
            league_by_get[row["Get"]] = row["League"]

    series_map: dict[str, AssetSeries] = {}
    price_map: dict[str, dict[date, float]] = defaultdict(dict)
    for (league, get, row_date), total in sums.items():
        price_map[get][row_date] = total / counts[(league, get, row_date)]

    for get, series in price_map.items():
        asset_id = f"currency|{get}"
        series_map[asset_id] = AssetSeries(
            asset_id=asset_id,
            type_name="Currency",
            name=get,
            series=series,
        )

    return series_map


def load_item_series(allowed_types: list[str]) -> dict[str, AssetSeries]:
    sums: dict[tuple[str, str, str, str, str, str, date], float] = {}
    counts: dict[tuple[str, str, str, str, str, str, date], int] = {}
    meta: dict[tuple[str, str, str, str, str, str], dict[str, str]] = {}

    with open(ITEMS_INPUT, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=CSV_DELIMITER)
        for row in reader:
            if row["Type"] in {"BaseType", "SkillGem", "ClusterJewel"}:
                continue
            if row["Type"] not in allowed_types:
                continue
            row_date = date.fromisoformat(row["Date"])
            if row_date < START_DATE or row_date > END_DATE:
                continue
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
            meta_key = (
                row["League"],
                row["Id"],
                row["Type"],
                row["Name"],
                row["Variant"],
                row["Links"],
            )
            meta[meta_key] = {
                "Type": row["Type"],
                "Name": row["Name"],
                "Variant": row["Variant"],
                "Links": row["Links"],
            }

    price_map: dict[tuple[str, str, str, str, str, str], dict[date, float]] = defaultdict(dict)
    for (league, item_id, item_type, name, variant, links, row_date), total in sums.items():
        key = (league, item_id, item_type, name, variant, links)
        price_map[key][row_date] = total / counts[(league, item_id, item_type, name, variant, links, row_date)]

    series_map: dict[str, AssetSeries] = {}
    for (league, item_id, item_type, name, variant, links), series in price_map.items():
        asset_id = f"item|{item_id}|{variant or ''}|{links or ''}"
        series_map[asset_id] = AssetSeries(
            asset_id=asset_id,
            type_name=item_type,
            name=name,
            series=series,
        )

    return series_map


def build_trades(series_map: dict[str, AssetSeries]) -> list[Trade]:
    trades: list[Trade] = []
    for asset in series_map.values():
        days = sorted(asset.series.keys())
        for i, buy_day in enumerate(days):
            buy_price = asset.series[buy_day]
            if buy_price <= 0:
                continue
            for sell_day in days[i + 1 :]:
                sell_price = asset.series[sell_day]
                if sell_price <= buy_price:
                    continue
                trades.append(
                    Trade(
                        asset_id=asset.asset_id,
                        name=asset.name,
                        type_name=asset.type_name,
                        buy_date=buy_day,
                        sell_date=sell_day,
                        buy_price=buy_price,
                        sell_price=sell_price,
                    )
                )
    return trades


def optimize_trades(trades: list[Trade], dates: list[date]) -> list[TradeLogEntry]:
    trades_by_buy: dict[date, list[Trade]] = defaultdict(list)
    for trade in trades:
        trades_by_buy[trade.buy_date].append(trade)

    best_capital: dict[date, float] = {dates[0]: STARTING_CAPITAL}
    prev: dict[date, tuple[date, Trade | None]] = {dates[0]: (dates[0], None)}

    for idx, day in enumerate(dates):
        if day not in best_capital:
            best_capital[day] = best_capital[dates[idx - 1]] if idx > 0 else STARTING_CAPITAL
            prev[day] = (dates[idx - 1], None) if idx > 0 else (day, None)

        capital = best_capital[day]

        # take trades starting today
        for trade in trades_by_buy.get(day, []):
            units = capital / trade.buy_price
            capital_end = units * trade.sell_price
            sell_day = trade.sell_date
            if sell_day not in best_capital or capital_end > best_capital[sell_day]:
                best_capital[sell_day] = capital_end
                prev[sell_day] = (day, trade)

        # carry forward cash
        if idx + 1 < len(dates):
            next_day = dates[idx + 1]
            if next_day not in best_capital or capital > best_capital[next_day]:
                best_capital[next_day] = capital
                prev[next_day] = (day, None)

    # reconstruct path from end date
    path_trades: list[TradeLogEntry] = []
    current = dates[-1]
    while current != dates[0]:
        prev_day, trade = prev.get(current, (dates[0], None))
        if trade is None:
            current = prev_day
            continue
        capital_start = best_capital[prev_day]
        units = capital_start / trade.buy_price
        capital_end = units * trade.sell_price
        path_trades.append(
            TradeLogEntry(
                trade=trade,
                capital_start=capital_start,
                capital_end=capital_end,
                units=units,
            )
        )
        current = prev_day

    path_trades.reverse()
    return path_trades


def write_log(path: Path, log: list[TradeLogEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "BuyDate",
                "SellDate",
                "Name",
                "Type",
                "BuyPrice",
                "SellPrice",
                "Units",
                "CapitalStart",
                "CapitalEnd",
                "GainPct",
            ],
        )
        writer.writeheader()
        for entry in log:
            trade = entry.trade
            writer.writerow(
                {
                    "BuyDate": trade.buy_date.isoformat(),
                    "SellDate": trade.sell_date.isoformat(),
                    "Name": trade.name,
                    "Type": trade.type_name,
                    "BuyPrice": f"{trade.buy_price:.6f}",
                    "SellPrice": f"{trade.sell_price:.6f}",
                    "Units": f"{entry.units:.6f}",
                    "CapitalStart": f"{entry.capital_start:.6f}",
                    "CapitalEnd": f"{entry.capital_end:.6f}",
                    "GainPct": f"{trade.gain_pct * 100:.2f}",
                }
            )


def plot_gantt(path: Path, title: str, log: list[TradeLogEntry]) -> None:
    if not log:
        raise ValueError("No trades in log to plot.")

    y_positions = list(range(len(log)))
    labels = [f"{entry.trade.name} ({entry.trade.type_name})" for entry in log]

    gains = [entry.trade.gain_pct * 100 for entry in log]
    cmap = plt.cm.YlGnBu
    norm = plt.Normalize(min(gains), max(gains))
    colors = cmap(norm(gains))

    fig_height = max(5, 0.45 * len(log))
    fig, ax = plt.subplots(figsize=(13.5, fig_height))
    fig.patch.set_facecolor(STYLE["background"])
    ax.set_facecolor(STYLE["background"])

    for idx, entry in enumerate(log):
        trade = entry.trade
        start = mdates.date2num(trade.buy_date)
        end = mdates.date2num(trade.sell_date)
        width = end - start
        ax.barh(
            y_positions[idx],
            width,
            left=start,
            height=0.6,
            color=colors[idx],
            edgecolor=STYLE["edge"],
            linewidth=0.6,
        )
        ax.text(
            end + 0.05,
            y_positions[idx],
            f"{trade.gain_pct * 100:.1f}%",
            va="center",
            ha="left",
            fontsize=9,
            color=STYLE["text"],
        )

    ax.set_yticks(y_positions)
    ax.set_yticklabels(labels, fontsize=9, fontweight="bold")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax.set_xlabel("Buy → Sell Window (First Week)", labelpad=10)
    ax.set_title(title, fontsize=17, pad=18)

    ax.grid(axis="x", color=STYLE["grid"])
    ax.grid(axis="y", visible=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(STYLE["spine"])
    ax.spines["bottom"].set_color(STYLE["spine"])

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, pad=0.015)
    cbar.set_label("Gain %", rotation=90, labelpad=10)

    plt.tight_layout()
    fig.savefig(path.with_suffix(".png"), dpi=300)
    fig.savefig(path.with_suffix(".svg"))


def ending_capital(log: list[TradeLogEntry]) -> float:
    if not log:
        return STARTING_CAPITAL
    return log[-1].capital_end


def run_bucket(name: str, types: list[str], include_currency: bool) -> None:
    dates = build_dates()

    series_map: dict[str, AssetSeries] = {}
    if include_currency:
        series_map.update(load_currency_series())

    if types:
        series_map.update(load_item_series(types))

    trades = build_trades(series_map)
    log = optimize_trades(trades, dates)

    log_path = OUTPUT_DIR / f"{name}_profit_timeline.csv"
    write_log(log_path, log)

    chart_path = OUTPUT_DIR / f"{name}_profit_timeline"
    final_capital = ending_capital(log)
    plot_gantt(
        chart_path,
        f"{name.title()} Profit Timeline (Start 100c → End {final_capital:,.0f}c)",
        log,
    )


def main() -> None:
    if not CURRENCY_INPUT.exists() or not ITEMS_INPUT.exists():
        raise FileNotFoundError("Missing filtered inputs in analysis/filtered")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    run_bucket("unique", UNIQUE_TYPES, include_currency=False)
    run_bucket("stable", STABLE_TYPES, include_currency=True)


if __name__ == "__main__":
    main()
