from __future__ import annotations

import csv
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio

INPUT = Path("analysis/strategy/type_avg_gain_top3.csv")
HTML_OUTPUT = Path("analysis/strategy/type_avg_gain_top3_lollipop_plotly.html")
PNG_OUTPUT = Path("analysis/strategy/type_avg_gain_top3_lollipop_plotly.png")
SVG_OUTPUT = Path("analysis/strategy/type_avg_gain_top3_lollipop_plotly.svg")

CHROME_FOR_TESTING = Path(
    ".venv/lib/python3.14/site-packages/choreographer/cli/browser_exe/chrome-mac-arm64/"
    "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
)


def load_rows():
    rows = []
    with open(INPUT, newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                avg = float(row.get("AvgGainPctTop3", "0") or 0)
            except ValueError:
                continue
            rows.append((row.get("Type", ""), avg))
    rows = [row for row in rows if row[0]]
    rows.sort(key=lambda item: item[1], reverse=True)
    return rows


def build_figure(rows):
    types = [row[0] for row in rows]
    values = [row[1] for row in rows]

    # Lollipop lines
    line_x = []
    line_y = []
    for t, v in rows:
        line_x.extend([0, v, None])
        line_y.extend([t, t, None])

    line_trace = go.Scatter(
        x=line_x,
        y=line_y,
        mode="lines",
        line=dict(color="#1f2937", width=2),
        hoverinfo="skip",
        showlegend=False,
    )

    marker_trace = go.Scatter(
        x=values,
        y=types,
        mode="markers",
        marker=dict(
            size=10,
            color=values,
            colorscale="Blues",
            line=dict(color="#0f172a", width=0.5),
            showscale=True,
            colorbar=dict(title="Avg % Gain"),
        ),
        hovertemplate="%{y}<br>Avg Gain: %{x:.2f}%<extra></extra>",
        showlegend=False,
    )

    fig = go.Figure(data=[line_trace, marker_trace])
    fig.update_layout(
        title="Avg % Gain of Top 3 Trades per Type (First Week)",
        xaxis_title="Average % Gain",
        yaxis_title="Type",
        template="plotly_white",
        height=600 + len(types) * 10,
        margin=dict(l=220, r=60, t=70, b=50),
    )

    fig.update_xaxes(showgrid=True, gridcolor="#e5e7eb")
    fig.update_yaxes(autorange="reversed")

    return fig


def main() -> None:
    if not INPUT.exists():
        raise FileNotFoundError(f"Missing input: {INPUT}")
    rows = load_rows()
    fig = build_figure(rows)

    pio.write_html(fig, HTML_OUTPUT, include_plotlyjs="cdn")
    if CHROME_FOR_TESTING.exists():
        pio.defaults.chromium_executable = str(CHROME_FOR_TESTING)
    pio.defaults.chromium_args = [
        "--disable-gpu",
        "--headless=new",
        "--no-sandbox",
    ]
    try:
        fig.write_image(PNG_OUTPUT, scale=2)
        fig.write_image(SVG_OUTPUT)
    except Exception as exc:
        print(f"Skipping static image export: {exc}")


if __name__ == "__main__":
    main()
