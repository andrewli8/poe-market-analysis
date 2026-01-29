from __future__ import annotations

from pathlib import Path
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp")

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

INPUT = Path("analysis/strategy/top20_week_trades_by_type_combined_unique_name.csv")
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
    "Beast",
]


STYLE = {
    "background": "#f6f4ef",
    "grid": "#e0dad1",
    "spine": "#d8d0c4",
    "edge": "#0b1320",
    "text": "#0b1320",
}


def build_gantt(df: pd.DataFrame, title: str, output_name: str, types: list[str]) -> None:
    df = df[df["Type"].isin(types)].copy()
    if df.empty:
        raise ValueError(f"No rows for types: {types}")

    # top 3 per type by GainPct
    rows = []
    for type_name in types:
        group = df[df["Type"] == type_name].sort_values("GainPct", ascending=False).head(3)
        if not group.empty:
            rows.append(group)
    if not rows:
        raise ValueError("No rows to plot after filtering.")

    df_top = pd.concat(rows)

    # build y positions with spacing
    plot_rows = []
    y_positions = []
    y_labels = []
    y = 0
    for type_name in types:
        group = df_top[df_top["Type"] == type_name].sort_values("GainPct", ascending=False)
        for _, row in group.iterrows():
            plot_rows.append(row)
            y_positions.append(y)
            y_labels.append(f"{row['Name']} ({type_name})")
            y += 1
        y += 0.9

    df_plot = pd.DataFrame(plot_rows)

    cmap = plt.cm.YlGnBu
    norm = plt.Normalize(df_plot["GainPct"].min(), df_plot["GainPct"].max())
    colors = cmap(norm(df_plot["GainPct"].values))

    fig_height = max(6, 0.34 * len(df_plot))
    fig, ax = plt.subplots(figsize=(13.5, fig_height))
    fig.patch.set_facecolor(STYLE["background"])
    ax.set_facecolor(STYLE["background"])

    for idx, row in enumerate(df_plot.itertuples()):
        start = mdates.date2num(row.BuyDate)
        end = mdates.date2num(row.SellDate)
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
            f"{row.GainPct:.1f}%",
            va="center",
            ha="left",
            fontsize=9,
            color=STYLE["text"],
        )

    ax.set_yticks(y_positions)
    ax.set_yticklabels(y_labels, fontsize=8, fontweight="bold")

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

    png_path = OUTPUT_DIR / f"{output_name}.png"
    svg_path = OUTPUT_DIR / f"{output_name}.svg"
    fig.savefig(png_path, dpi=300)
    fig.savefig(svg_path)


def main() -> None:
    if not INPUT.exists():
        raise FileNotFoundError(f"Missing input: {INPUT}")

    df = pd.read_csv(INPUT)
    df["GainPct"] = df["GainPct"].astype(float)
    df["BuyDate"] = pd.to_datetime(df["BuyDate"], format="%Y-%m-%d")
    df["SellDate"] = pd.to_datetime(df["SellDate"], format="%Y-%m-%d")

    # Ignore ClusterJewel type explicitly
    df = df[df["Type"] != "ClusterJewel"]

    build_gantt(
        df,
        title="Unique Gantt (Top 3 per Type)",
        output_name="unique_gantt",
        types=UNIQUE_TYPES,
    )

    build_gantt(
        df,
        title="Stable Gantt (Top 3 per Type)",
        output_name="stable_gantt",
        types=STABLE_TYPES,
    )


if __name__ == "__main__":
    main()
