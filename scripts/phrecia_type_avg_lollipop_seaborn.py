from __future__ import annotations

from pathlib import Path
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp")

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

INPUT = Path("analysis/strategy/type_avg_gain_top3.csv")
PNG_OUTPUT = Path("analysis/strategy/type_avg_gain_top3_lollipop_seaborn.png")
SVG_OUTPUT = Path("analysis/strategy/type_avg_gain_top3_lollipop_seaborn.svg")


def main() -> None:
    if not INPUT.exists():
        raise FileNotFoundError(f"Missing input: {INPUT}")

    df = pd.read_csv(INPUT)
    df = df.sort_values("AvgGainPctTop3", ascending=False).reset_index(drop=True)

    sns.set_theme(style="whitegrid")

    # dynamic height based on rows
    height = max(6, 0.32 * len(df))
    fig, ax = plt.subplots(figsize=(12, height))

    # background
    fig.patch.set_facecolor("#f8fafc")
    ax.set_facecolor("#f8fafc")

    # lollipop stems
    ax.hlines(
        y=df["Type"],
        xmin=0,
        xmax=df["AvgGainPctTop3"],
        color="#1f2937",
        linewidth=2,
        alpha=0.8,
    )

    # dots
    palette = sns.color_palette("Blues", n_colors=len(df))
    ax.scatter(
        df["AvgGainPctTop3"],
        df["Type"],
        s=70,
        c=palette,
        edgecolors="#0f172a",
        linewidths=0.6,
        zorder=3,
    )

    # labels
    for _, row in df.iterrows():
        ax.text(
            row["AvgGainPctTop3"] + 0.4,
            row["Type"],
            f"{row['AvgGainPctTop3']:.2f}%",
            va="center",
            ha="left",
            fontsize=9,
            color="#111827",
        )

    ax.set_title("Avg % Gain of Top 3 Trades per Type (First Week)", fontsize=16, pad=16)
    ax.set_xlabel("Average % Gain")
    ax.set_ylabel("Type")

    # tidy
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#e5e7eb")
    ax.spines["bottom"].set_color("#e5e7eb")
    ax.grid(axis="x", color="#e5e7eb")
    ax.grid(axis="y", visible=False)

    plt.tight_layout()
    fig.savefig(PNG_OUTPUT, dpi=300)
    fig.savefig(SVG_OUTPUT)


if __name__ == "__main__":
    main()
