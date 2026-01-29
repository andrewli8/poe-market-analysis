from __future__ import annotations

import csv
from pathlib import Path
from typing import List, Tuple

INPUT = Path("analysis/strategy/top20_week_trades_by_type_combined_unique_name.csv")
CSV_OUTPUT = Path("analysis/strategy/type_avg_gain_top3.csv")
SVG_OUTPUT = Path("analysis/strategy/type_avg_gain_top3_lollipop.svg")

# SVG layout
WIDTH = 1100
LEFT_MARGIN = 260
RIGHT_MARGIN = 60
TOP_MARGIN = 40
BOTTOM_MARGIN = 40
ROW_HEIGHT = 26
DOT_RADIUS = 4
LINE_COLOR = "#1f2933"
DOT_COLOR = "#2563eb"
TEXT_COLOR = "#111827"
GRID_COLOR = "#e5e7eb"
FONT_FAMILY = "Helvetica, Arial, sans-serif"


def load_top3_averages() -> List[Tuple[str, float, int]]:
    per_type = {}
    counts = {}

    with open(INPUT, newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                rank = int(row.get("Rank", "0"))
            except ValueError:
                continue
            if rank > 3:
                continue
            type_name = row.get("Type", "")
            if not type_name:
                continue
            gain_pct = float(row.get("GainPct", "0") or 0)
            per_type[type_name] = per_type.get(type_name, 0.0) + gain_pct
            counts[type_name] = counts.get(type_name, 0) + 1

    results = []
    for type_name, total in per_type.items():
        count = counts.get(type_name, 0)
        avg = total / count if count else 0.0
        results.append((type_name, avg, count))

    results.sort(key=lambda row: row[1], reverse=True)
    return results


def write_csv(rows: List[Tuple[str, float, int]]) -> None:
    with open(CSV_OUTPUT, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Type", "AvgGainPctTop3", "Count"])
        writer.writeheader()
        for type_name, avg, count in rows:
            writer.writerow(
                {
                    "Type": type_name,
                    "AvgGainPctTop3": f"{avg:.6f}",
                    "Count": count,
                }
            )


def write_svg(rows: List[Tuple[str, float, int]]) -> None:
    height = TOP_MARGIN + BOTTOM_MARGIN + ROW_HEIGHT * len(rows)
    chart_width = WIDTH - LEFT_MARGIN - RIGHT_MARGIN
    max_value = max((row[1] for row in rows), default=1.0)

    # gridlines at 0%, 25%, 50%, 75%, 100%
    ticks = [0.0, 0.25, 0.5, 0.75, 1.0]

    def x_pos(value: float) -> float:
        return LEFT_MARGIN + (value / max_value) * chart_width

    lines = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{WIDTH}' height='{height}' viewBox='0 0 {WIDTH} {height}'>",
        f"<style>text{{font-family:{FONT_FAMILY};font-size:12px;fill:{TEXT_COLOR};}}</style>",
        f"<rect width='100%' height='100%' fill='white' />",
        f"<text x='{LEFT_MARGIN}' y='{TOP_MARGIN - 18}' font-size='14px' font-weight='600'>Avg GainPct (Top 3 per Type)</text>",
    ]

    # gridlines + axis labels
    for tick in ticks:
        value = max_value * tick
        x = x_pos(value)
        lines.append(
            f"<line x1='{x:.2f}' y1='{TOP_MARGIN - 6}' x2='{x:.2f}' y2='{height - BOTTOM_MARGIN + 6}' stroke='{GRID_COLOR}' stroke-width='1' />"
        )
        lines.append(
            f"<text x='{x:.2f}' y='{height - BOTTOM_MARGIN + 22}' text-anchor='middle'>{value:.1f}</text>"
        )

    for idx, (type_name, avg, count) in enumerate(rows):
        y = TOP_MARGIN + idx * ROW_HEIGHT
        y_center = y + ROW_HEIGHT / 2
        x = x_pos(avg)

        # label
        lines.append(
            f"<text x='{LEFT_MARGIN - 12}' y='{y_center + 4}' text-anchor='end'>{type_name}</text>"
        )
        # line
        lines.append(
            f"<line x1='{LEFT_MARGIN}' y1='{y_center:.2f}' x2='{x:.2f}' y2='{y_center:.2f}' stroke='{LINE_COLOR}' stroke-width='1.5' />"
        )
        # dot
        lines.append(
            f"<circle cx='{x:.2f}' cy='{y_center:.2f}' r='{DOT_RADIUS}' fill='{DOT_COLOR}' />"
        )
        # value
        lines.append(
            f"<text x='{x + 8:.2f}' y='{y_center + 4:.2f}'>{avg:.2f}</text>"
        )

    lines.append("</svg>")
    SVG_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if not INPUT.exists():
        raise FileNotFoundError(f"Missing input: {INPUT}")
    rows = load_top3_averages()
    write_csv(rows)
    write_svg(rows)


if __name__ == "__main__":
    main()
