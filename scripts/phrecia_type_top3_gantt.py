from __future__ import annotations

from pathlib import Path
from datetime import datetime
from collections import defaultdict

import os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp")

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

INPUT = Path("analysis/strategy/top20_week_trades_by_type_combined_unique_name.csv")
PNG_OUTPUT = Path("analysis/strategy/type_top3_gantt.png")
SVG_OUTPUT = Path("analysis/strategy/type_top3_gantt.svg")


def main() -> None:
    if not INPUT.exists():
        raise FileNotFoundError(f"Missing input: {INPUT}")

    df = pd.read_csv(INPUT)
    df["GainPct"] = df["GainPct"].astype(float)
    df["BuyDate"] = pd.to_datetime(df["BuyDate"], format="%Y-%m-%d")
    df["SellDate"] = pd.to_datetime(df["SellDate"], format="%Y-%m-%d")

    # take top 3 per Type by GainPct
    top3_rows = []
    for type_name, group in df.groupby("Type"):
        group = group.sort_values("GainPct", ascending=False).head(3)
        top3_rows.append(group)
    df_top = pd.concat(top3_rows)

    # pick top 5 types by average GainPct of their top 3 trades
    type_scores = (
        df_top.groupby("Type")["GainPct"].mean().sort_values(ascending=False).head(5)
    )
    df_top = df_top[df_top["Type"].isin(type_scores.index)]
    df_top = df_top.sort_values(["Type", "GainPct"], ascending=[True, False])

    # build y positions with spacing between types
    rows = []
    y_labels = []
    y_positions = []
    y = 0
    for type_name in type_scores.index:
        group = df_top[df_top["Type"] == type_name]
        for _, row in group.iterrows():
            rows.append(row)
            y_positions.append(y)
            y_labels.append(f"{row['Name']} ({type_name})")
            y += 1
        y += 0.9  # gap between types

    df_plot = pd.DataFrame(rows)

    # colors by GainPct
    cmap = plt.cm.YlGnBu
    norm = plt.Normalize(df_plot["GainPct"].min(), df_plot["GainPct"].max())
    colors = cmap(norm(df_plot["GainPct"].values))

    fig_height = max(6, 0.32 * len(df_plot))
    fig, ax = plt.subplots(figsize=(13.5, fig_height))
    fig.patch.set_facecolor("#f6f4ef")
    ax.set_facecolor("#f6f4ef")

    # draw bars
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
            edgecolor="#0b1320",
            linewidth=0.6,
        )
        ax.text(
            end + 0.05,
            y_positions[idx],
            f"{row.GainPct:.1f}%",
            va="center",
            ha="left",
            fontsize=9,
            color="#0b1320",
        )

    ax.set_yticks(y_positions)
    ax.set_yticklabels(y_labels, fontsize=8, fontweight="bold")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax.set_xlabel("Buy → Sell Window (First Week)", labelpad=10)
    ax.set_title("Top 3 Trades per Type (Top 5 Types by Avg Gain)", fontsize=17, pad=18)

    ax.grid(axis="x", color="#e0dad1")
    ax.grid(axis="y", visible=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#d8d0c4")
    ax.spines["bottom"].set_color("#d8d0c4")

    # colorbar
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, pad=0.015)
    cbar.set_label("Gain %", rotation=90, labelpad=10)

    plt.tight_layout()
    fig.savefig(PNG_OUTPUT, dpi=300)
    fig.savefig(SVG_OUTPUT)


if __name__ == "__main__":
    main()
