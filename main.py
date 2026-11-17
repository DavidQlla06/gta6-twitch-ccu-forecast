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
signature). Weights favour console-only launches (x8: GTA VI is console-only)
and older launches (2.5x per year back: the 2018-2020 Sony/Rockstar console
launches are the closest analogues for a Rockstar midnight rolling launch);
all three choices were validated on the four practice cases, leave-one-out
over the comparables, and leave-one-practice-out (practice loss ~0.143 vs the
house baseline's ~0.39). The per-hour spread is additionally shrunk 85%
toward the day's median spread, because each hour's residual scale comes
from only ~12 launches and is noisy (practice loss 0.1828 -> 0.1797).

Iteration 2 (practice loss 0.1797 -> 0.1556; leave-one-practice-out 0.1797
-> 0.1667): the v1 median was systematically too low — the truth sits above
the forecast median at almost every hour for the two most GTA-like practice
cases (Wolverine, RDR2), worst late in the day when the US wakes up — so the
median is shifted up by an amount growing linearly with the hour (0 at h2,
+0.15 log at h24), and the upper tail is narrowed (1.4 -> 1.15) to compensate
for the shift. The vintage weight is steepened (1.3 -> 2.0 per year back:
the 2020 console launches are the closest analogues, and a steeper weight
is the one knob whose improvement survives leave-one-practice-out).
Finally, the regression is evaluated at min(ln(v1), 12.6): GTA VI's hour-1
print will exceed every validated launch (largest practice v1 is GoW
Ragnarok, ln 12.50), and a linear slope extrapolated past the data predicts
a declining day (median below hour 1) for a rolling-midnight launch, which
cannot happen — hour 1 is 00:00 UTC, before the US has even unlocked. Past
12.6 the forecast takes the shape of the biggest validated launch instead.
The spread's prediction-interval term still uses the true ln(v1), so a
bigger hour-1 print still widens the intervals.

Iteration 3 (practice loss 0.1556 -> 0.1433; leave-one-practice-out 0.1667
-> 0.1620 for the knob family): the console weight is raised (2 -> 8) and
the vintage weight steepened (2.0 -> 2.5 per year), and the upper tail is
narrowed to 1.0 — with the median shifted up, the widened upper tail was
double-counting the upside, and upper=1.0 is the value leave-one-practice-
out selects for every held-out case. The median is NO LONGER smoothed over
neighbouring hours: smoothing blurs the sharp features the truth actually
has (the h5 US-midnight jump, the h12 midday crater), which is why the
Spider-Man 2 case — the one with the deepest crater — was the worst
practice case; dropping the median smoothing improves every practice case
(0.1473 -> 0.1433) and leaves the high-v1 final shape sane (median peak
1.70x at h20, q95 peak 3.25x, max hourly median jump 0.25x). The spread
IS still smoothed. Honest ceiling found in iteration 3: even fitting 23
free per-hour median shifts directly to the four practice cases only
reaches 0.1359, so the 0.095 practice scores at the top of the leaderboard
cannot be reached by calibrating this model family — they are either
practice-specific tuning that will not transfer to the final case, or a
structurally different model. This submission takes the defensible gain
and does not chase them.

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
UPPER_SCALE = 1.0
LOWER_SCALE = 0.75
MED_SHIFT_GROW = 0.15  # median shift (log units) at h24, growing linearly from 0 at h2
LX_CAP = 12.6  # do not extrapolate the ln(v1) slope past the biggest validated launch
SIGMA_BASE = 0.15  # fallback spread / house-baseline spread
PEAK_MAX = 4.0     # exclude launches whose peak exceeds 4x their hour-1 print
MIN_POINTS = 5     # minimum training launches for a per-hour regression
TIME_WEIGHT = 2.5  # per-year vintage weight, favouring older launches
CONSOLE_WEIGHT = 8.0
SMOOTH_WIN = 1     # smoothing window over neighbouring hours
SPREAD_SHRINK = 0.85  # fraction each hour's spread moves toward the median
# Spread shrinkage: each hour's residual scale is estimated from only ~12
# launches, so it is noisy. Shrink it 85% toward the day's median scale
# (keeps a trace of genuine hour-to-hour structure). Validated on the four
# practice cases: mean pinball loss 0.1828 -> 0.1797 (p00 0.270 -> 0.258,
# p03 0.187 -> 0.186, p01/p02 essentially unchanged); stronger shrinkage
# keeps helping up to a fully flat spread, but that discards the real
# widening of uncertainty over the day, so 85% is the stopping point.


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
    # Cap the regression's evaluation point: past the biggest validated
    # launch the slope is extrapolation, not evidence (see module docstring).
    lx_pred = min(lx, LX_CAP)
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
        med[h] = a + b * lx_pred
        res = [p[1] - (a + b * p[0]) for p in pts]
        dof = max(1, len(pts) - 2)
        s = math.sqrt(sum(r * r for r in res) / dof)
        # Prediction interval: wider when the target extrapolates from the
        # training centre.
        s *= math.sqrt(1 + 1.0 / len(pts) + (lx - mx) ** 2 / max(sxx, 1e-9))
        spr[h] = max(0.05, s)
    # Iteration 3: the median is NOT smoothed. Smoothing blurs the sharp
    # features the truth actually has (the h5 US-midnight jump, the h12
    # midday crater); dropping it improves every practice case. The spread
    # is still smoothed — it is a noise scale, not a signal.
    spr = smooth(spr)
    median_spr = sorted(spr.values())[len(spr) // 2]
    spr = {h: (1.0 - SPREAD_SHRINK) * s + SPREAD_SHRINK * median_spr
           for h, s in spr.items()}

    hours = []
    for h in range(2, 25):
        # Median shift, growing with the hour: the late-day surge (US waking
        # up) is systematically underpredicted by the shape library.
        shift = MED_SHIFT_GROW * (h - 1) / 23.0
        qs = []
        for z in Z:
            scale = UPPER_SCALE if z > 0 else (LOWER_SCALE if z < 0 else 1.0)
            qs.append(p1 * math.exp(med[h] + shift + spr[h] * scale * z))
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
