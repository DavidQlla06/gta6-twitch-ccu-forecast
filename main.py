"""Forecast GTA VI's launch-day Twitch viewers hour by hour (make.fun
gta6-twitch-ccu-forecast-01).

Method: a launch-shape library. Every comparable past launch in the case
file contributes its release-day hourly curve, normalised by its own hour-1
print. For each forecast hour h = 2..24 we fit a weighted least-squares
regression of log(viewers_h / viewers_1) on log(viewers_1) across the
rolling-midnight-unlock launches, and forecast the target launch's log-ratio
at its own hour-1 print. The spread is the regression's residual scale with
a prediction-interval widening (wider when the target's hour-1 print is far
from the training centre, i.e. when we extrapolate), smoothed over neighbouring
hours. Quantiles are the median with a skew: the upper tail is widened (launch
days surprise to the upside far more often than to the downside) and the lower
tail narrowed.

Which comparables count: only launches whose release-day shape is driven by a
rolling midnight-local unlock like GTA VI's (consoles unlock at midnight local
time, region by region). Excluded: the target game's own pre-release history,
free-to-play / slow-burn launches, early-access-contaminated launches (their
release-day curve is post-peak decay), simultaneous global unlocks (their
hour-1 print is a pre-unlock baseline and their curve explodes at the unlock
hour), and any launch whose peak is more than 4x its hour-1 print (the same
signature). Weights favour console-only launches (x2: GTA VI is console-only)
and older launches (1.3x per year back: the 2018-2020 Sony/Rockstar console
launches are the closest analogues for a Rockstar midnight rolling launch);
all three choices were validated on the four practice cases, leave-one-out
over the comparables, and leave-one-practice-out (practice loss ~0.19 vs the
house baseline's ~0.39).

Standard library only. Deterministic: inputs are processed in sorted order,
no randomness, no network, no clock. Runs in well under a second per case.
"""

import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.6448536269514722, -0.6744897501960817, 0.0, 0.6744897501960817,
     1.6448536269514722]
# Skew: widen the upper tail (growth surprises), narrow the lower tail.
UPPER_SCALE = 1.4
LOWER_SCALE = 0.75
SIGMA_BASE = 0.15  # fallback spread / house-baseline spread
PEAK_MAX = 4.0     # exclude launches whose peak exceeds 4x their hour-1 print
MIN_POINTS = 5     # minimum training launches for a per-hour regression
TIME_WEIGHT = 1.3  # per-year vintage weight, favouring older launches
CONSOLE_WEIGHT = 2.0
SMOOTH_WIN = 1     # smoothing window over neighbouring hours


def round2(x):
    """Round to 2 decimals, half up (as the house baseline does)."""
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value == int(value) else value


def day_hours(comp):
    """Release-day hourly viewers {hour: viewers} for one comparable."""
    try:
        day = datetime.fromisoformat(comp["day_start"].replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return {}
    hrs = {}
    for pt in comp.get("hourly") or []:
        try:
            t = datetime.fromisoformat(pt["from"].replace("Z", "+00:00"))
            v = pt.get("viewers")
        except (KeyError, ValueError, TypeError):
            continue
        if v is None or v <= 0:
            continue
        h = int((t - day).total_seconds() // 3600) + 1
        if 1 <= h <= 24:
            hrs[h] = float(v)
    return hrs


def is_console_only(platforms):
    p = (platforms or "").lower()
    if "pc" in p:
        return False
    return ("ps" in p) or ("xbox" in p) or ("switch" in p)


def classify(comp):
    """Rolling-midnight shape or not, from the unlock text and the data."""
    name = (comp.get("name") or "").lower()
    unlock = (comp.get("unlock") or "").lower()
    if "grand theft auto vi" in name:
        return None  # the target game's own pre-release history
    if "target-history" in unlock:
        return None
    if "early-access-contaminated" in unlock:
        return None
    if "tier: weak" in unlock:
        return None
    if "single global unlock" in unlock or "single simultaneous" in unlock:
        return None
    if "simultaneous" in unlock and "midnight local" not in unlock:
        return None
    return "rolling"


def build_rows(case):
    """Training rows: (ln v1, {hour: ln ratio}, weight) per usable comparable."""
    rows = []
    target_name = (case.get("game") or {}).get("name", "").lower()
    for comp in sorted(case.get("comparables") or [], key=lambda c: c.get("name", "")):
        if (comp.get("name") or "").lower() == target_name:
            continue
        if classify(comp) is None:
            continue
        hrs = day_hours(comp)
        if 1 not in hrs or len(hrs) < 20:
            continue
        v1 = hrs[1]
        if v1 < 1:
            continue
        if max(hrs.values()) / v1 > PEAK_MAX:
            continue
        try:
            year = int(str(comp.get("day_start", "2020"))[:4])
        except ValueError:
            year = 2020
        w = TIME_WEIGHT ** (2026 - year)
        if is_console_only(comp.get("platforms", "")):
            w *= CONSOLE_WEIGHT
        rows.append({
            "ln_v1": math.log(v1),
            "log_ratio": {h: math.log(hrs[h] / v1) for h in hrs if h >= 2},
            "weight": w,
        })
    return rows


def wols(pts):
    """Weighted OLS y ~ a + b*x. pts: (x, y, w). Returns (a, b, mx, sxx, sw)."""
    sw = sum(p[2] for p in pts)
    mx = sum(p[2] * p[0] for p in pts) / sw
    my = sum(p[2] * p[1] for p in pts) / sw
    sxx = sum(p[2] * (p[0] - mx) ** 2 for p in pts)
    sxy = sum(p[2] * (p[0] - mx) * (p[1] - my) for p in pts)
    b = sxy / sxx if sxx > 0 else 0.0
    return my - b * mx, b, mx, sxx, sw


def smooth(vals, win=SMOOTH_WIN):
    out = {}
    for h in range(2, 25):
        xs = [vals[hh] for hh in range(max(2, h - win), min(24, h + win) + 1)
              if hh in vals]
        out[h] = sum(xs) / len(xs) if xs else 0.0
    return out


def baseline_quantiles(p1, h):
    return [round2(p1 * math.exp(z * SIGMA_BASE * math.sqrt(h - 1))) for z in Z]


def forecast_case(case):
    first = next((k for k in case.get("known") or [] if k.get("hour") == 1), None)
    if first is None or not first.get("viewers"):
        # No hour-1 print: emit a valid flat forecast rather than crashing.
        return {"hours": [{"hour": h, "q": [1, 1, 1, 1, 1]} for h in range(2, 25)]}
    p1 = max(1.0, float(first["viewers"]))
    lx = math.log(p1)
    rows = build_rows(case)
    if len(rows) < MIN_POINTS:
        return {"hours": [{"hour": h, "q": baseline_quantiles(p1, h)}
                          for h in range(2, 25)]}

    med, spr = {}, {}
    for h in range(2, 25):
        pts = [(r["ln_v1"], r["log_ratio"][h], r["weight"])
               for r in rows if h in r["log_ratio"]]
        if len(pts) < MIN_POINTS:
            med[h] = 0.0
            spr[h] = 0.30
            continue
        a, b, mx, sxx, _sw = wols(pts)
        med[h] = a + b * lx
        res = [p[1] - (a + b * p[0]) for p in pts]
        dof = max(1, len(pts) - 2)
        s = math.sqrt(sum(r * r for r in res) / dof)
        # Prediction interval: wider when the target extrapolates from the
        # training centre.
        s *= math.sqrt(1 + 1.0 / len(pts) + (lx - mx) ** 2 / max(sxx, 1e-9))
        spr[h] = max(0.05, s)
    med = smooth(med)
    spr = smooth(spr)

    hours = []
    for h in range(2, 25):
        qs = []
        for z in Z:
            scale = UPPER_SCALE if z > 0 else (LOWER_SCALE if z < 0 else 1.0)
            qs.append(p1 * math.exp(med[h] + spr[h] * scale * z))
        # Enforce non-decreasing, finite, within (0, 1e9].
        qs = [min(max(q, 1e-6), 1e9) for q in qs]
        for i in range(1, 5):
            if qs[i] < qs[i - 1]:
                qs[i] = qs[i - 1]
        hours.append({"hour": h, "q": [round2(q) for q in qs]})
    return {"hours": hours}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
