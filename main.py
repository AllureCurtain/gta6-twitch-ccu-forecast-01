#!/usr/bin/env python3
"""Forecast a big game launch's Twitch viewers hour by hour, from its first hour.

Method: analog launches. Every case ships past big launches with their hourly
viewer counts. For each past launch, take the ratio of its viewers in hour h
to its viewers in hour 1. Two facts about those ratios drive the forecast:

1. The ratio curve has a shape: a dip in the small hours, a jump when the
   United States unlocks (about hour 5), a peak in the evening (hours 17-21),
   then a fall. The shape is shared across launches.
2. The size of the curve depends on how big hour 1 already was: a launch
   whose first hour was already huge has little headroom left, while one
   whose first hour was small (few regions unlocked yet) ramps much further.
   Across the comparables, log peak ratio correlates about -0.79 with
   log hour-1 viewers.

So for each hour h we fit a straight line through the comparables,
log(viewers_h / viewers_1) against log(viewers_1), and read it off at this
launch's own hour-1 print. The spread around the line is the residual
standard deviation of that fit, shrunk by 0.8 (the factor that scored best
when the same procedure was run over the practice launches and over
leave-one-out repeats on the comparables). Quantiles are normal quantiles
of that log-scale distribution, turned back into viewer counts.

Comparables are used only when they behave like a real launch day: all 24
release-day hours present, a positive hour-1 print, and hour 1 at least 1%
of the launch's peak (this drops simultaneous-global launches whose hour 1
was nearly dead before a later single unlock, and the target game's own
pre-release history, which has no release day yet).

Standard library only, no network, no randomness: two runs on the same
case write byte-identical output.
"""

import json
import math
import os
from datetime import datetime

LEVELS = (0.05, 0.25, 0.5, 0.75, 0.95)
# Standard normal quantiles at the five levels.
Z_SCORES = (-1.6448536269514722, -0.6744897501960817, 0.0,
            0.6744897501960817, 1.6448536269514722)
SPREAD_SHRINK = 0.8
MIN_HOUR1_FRACTION_OF_PEAK = 0.01
MIN_VIEWERS = 1.0
MAX_VIEWERS = 1.0e9


def parse_instant(text):
    """Parse an ISO 8601 UTC timestamp into a datetime."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def release_day_hours(comparable):
    """Map hour 1..24 of a comparable's release day to its viewer count.

    A point at `from` covers the hour starting then, in UTC. Hours with no
    point stay absent; nothing is interpolated.
    """
    day_start = parse_instant(comparable["day_start"])
    hours = {}
    for point in comparable.get("hourly") or []:
        viewers = point.get("viewers")
        if viewers is None:
            continue
        when = parse_instant(point["from"])
        hour = int((when - day_start).total_seconds() // 3600) + 1
        if 1 <= hour <= 24 and hour not in hours:
            hours[hour] = float(viewers)
    return hours


def usable_launches(case):
    """Comparables that can anchor a ratio curve, as (log hour-1, hours)."""
    launches = []
    for comparable in case.get("comparables") or []:
        hours = release_day_hours(comparable)
        if len(hours) < 24:
            continue
        hour1 = hours.get(1)
        if not hour1 or hour1 <= 0:
            continue
        if hour1 < MIN_HOUR1_FRACTION_OF_PEAK * max(hours.values()):
            continue
        launches.append((math.log(hour1), hours))
    return launches


def fit_line(xs, ys):
    """Least-squares line y = intercept + slope * x. Returns (intercept, slope)."""
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    spread_xx = sum((x - mean_x) ** 2 for x in xs)
    if spread_xx == 0:
        return mean_y, 0.0
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / spread_xx
    return mean_y - slope * mean_x, slope


def hour_forecast(launches, log_hour1, hour):
    """Five quantiles of hour `hour`'s viewers, as fractions of hour 1."""
    points = []
    for log_h1, hours in launches:
        viewers = hours.get(hour)
        if viewers is not None and viewers > 0:
            points.append((log_h1, math.log(viewers) - log_h1))
    if len(points) < 3:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    intercept, slope = fit_line(xs, ys)
    residuals = [y - (intercept + slope * x) for x, y in points]
    dof = max(len(residuals) - 2, 1)
    spread = math.sqrt(sum(r * r for r in residuals) / dof)
    # Never forecast outside the hour-1 range the line was fit on.
    clamped = min(max(log_hour1, min(xs)), max(xs))
    centre = intercept + slope * clamped
    return [math.exp(centre + z * spread * SPREAD_SHRINK) for z in Z_SCORES]


def forecast_case(case):
    """Build the {"hours": [...]} forecast for one case dictionary."""
    known = case.get("known") or [{}]
    hour1 = known[0].get("viewers") or 0
    hour1 = max(float(hour1), MIN_VIEWERS)
    log_hour1 = math.log(hour1)
    launches = usable_launches(case)

    wanted = [row.get("hour") for row in case.get("forecast") or []]
    wanted = [h for h in wanted if isinstance(h, int) and 2 <= h <= 24]
    if not wanted:
        wanted = list(range(2, 25))

    rows = []
    for hour in sorted(wanted):
        ratios = hour_forecast(launches, log_hour1, hour)
        if ratios is None:
            ratios = [1.0] * 5
        quantiles = []
        for ratio in ratios:
            value = hour1 * ratio
            value = min(max(value, MIN_VIEWERS), MAX_VIEWERS)
            quantiles.append(round(value, 2))
        for i in range(1, 5):
            quantiles[i] = max(quantiles[i], quantiles[i - 1])
        rows.append({"hour": hour, "q": quantiles})
    return {"hours": rows}


def main():
    input_dir = os.environ.get("MAKEFUN_INPUT_DIR") or "/input/"
    output_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output/"
    os.makedirs(output_dir, exist_ok=True)
    names = sorted(name for name in os.listdir(input_dir) if name.endswith(".in"))
    for name in names:
        with open(os.path.join(input_dir, name), "r", encoding="utf-8") as handle:
            case = json.load(handle)
        forecast = forecast_case(case)
        case_id = case.get("id") or name[:-3]
        out_path = os.path.join(output_dir, case_id + ".out")
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump(forecast, handle, separators=(",", ":"))
            handle.write("\n")


if __name__ == "__main__":
    main()
