# GTA VI launch-day Twitch viewer forecaster

[![make.fun](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/DavidQlla06/gta6-twitch-ccu-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/DavidQlla06/gta6-twitch-ccu-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)

Entry for [make.fun's GTA VI Twitch forecast bounty](https://make.fun/bounty/gta6-twitch-ccu-forecast-01):
forecast how many people watch Grand Theft Auto VI live on Twitch in each
hour of its release day (2026-11-19 UTC), given everything recorded up to the
end of the day's first hour.

## How it works

`main.py` (Python 3.13, standard library only) reads one case from
`/input/<id>.in` and writes `/output/<id>.out` with five quantiles
(5%, 25%, 50%, 75%, 95%) of the viewer count for each of hours 2–24.

The forecast is a **launch-shape library, history-anchored**: every
comparable past launch in the case contributes its release-day hourly curve,
normalised by its own hour-1 print. For each hour we fit a weighted
regression of log(viewers_h / viewers_1) on log(viewers_1) across the
rolling-midnight launches, and predict the target launch at its own hour-1
print. From hour 6 (the US East unlock) a second predictor joins the
regression: r_m1, the log of the viewers in the hour before the release day
relative to the hour-1 print — the pre-launch ramp, which measures how much
of the world is already watching the early-region streams and predicts the
late-day US surge beyond what hour 1 alone says. The spread is the
regression's residual scale with a prediction-interval widening, and the
quantiles are skew-adjusted (wider upper tail: launch days surprise to the
upside far more often than to the downside).

Only launches shaped by a rolling midnight-local unlock like GTA VI's count;
simultaneous global unlocks, early-access-contaminated launches, free-to-play
and slow-burn launches, and the target game's own pre-release history are
excluded. Weights favour console-only launches (x8: GTA VI is console-only) and
older launches (2.5x per year back: the 2020 Sony console launches are the
closest analogues for a Rockstar midnight rolling launch). The median is
shifted up by an amount growing with the hour (0.125 log at h24: the late-day
surge, when the US wakes up, is systematically underpredicted by the shape
library), and the regression is never evaluated past ln(viewers_1) = 12.6 —
GTA VI's hour-1 print will exceed every validated launch, and a linear slope
extrapolated past the data would predict a declining day, which cannot happen
for a rolling-midnight launch. The median is not smoothed over neighbouring hours
(iteration 3: smoothing blurred the sharp h5 jump and h12 crater the truth
actually has), and the upper tail is not widened (upper scale 1.0). If the
pre-launch hour is missing from a case, the model falls back to the pure
hour-1 design for every hour.

Iteration 5 — a poker bet for the single final day, not more practice tuning:
the fitted r_m1 coefficient is scaled up by a base factor of 1.375, plus a
boost of +2.0 per unit of r_m1 above 0.3 (Wolverine-hot), so a hot pre-launch
ramp moves the late-day median much further than the linear fit says, while a
cool anchor (r_m1 <= 0.3) is barely touched. The boost's contribution is
capped at 0.20 log per hour, so the bet stays bounded even if the final
anchor lands far outside the observed range (max r_m1 = 0.58). The scale is
convex in the anchor by design: a ramp that hot signals a qualitatively more
explosive US wave than linear extrapolation suggests. The honest limit: if the
anchor lies (hot ramp, flat day), this model overshoots more than v4 — that is
the bet being taken, and the cap is what bounds it. A fuller poker (base 1.5,
boost 4, shift 0.175, upper 1.1, cap 0.25) lives on the `poker` branch.

Iteration 7 — quantile calibration plus a flatter vintage weight: the
intervals are slightly too wide (coverage [q05,q95] 0.97 vs the ideal
0.90), so every hour's spread is narrowed by 10% (spread scale 0.9);
when the pre-launch anchor is hot (r_m1 above 0.3) the upper quantiles
are widened by +1.0 per unit of excess anchor — pinball is asymmetric
(overpredicting q95 costs 0.05/unit on a flat day, underpredicting it
costs 0.95/unit on an explosive day), so the rank-1 bet belongs in the
upper tail, and it fires only on hot anchors so the cool-anchor practice
cases are untouched. The vintage weight is flattened to 2.0 per year
(was 2.5): with the anchor in the model the optimum moved, and 2.0 beats
2.5 on practice and on the final-day scenarios at every console weight.
The honest costs: leave-one-comparable-out is slightly worse (0.218 vs
0.217) and a flat day after a hot ramp costs more (0.333 vs 0.290) — both
well inside the full-poker branch's numbers.

Local validation on the four practice cases: mean pinball loss **0.130**
(house baseline: 0.387; v5-ship: 0.134; v4: 0.137; v3 entry: 0.143; v2
entry: 0.156; v1 entry: 0.180). Leave-one-comparable-out: 0.218 (v5-ship:
0.217; v4: 0.209). Leave-one-practice-out rest-means beat v4 on 3 of 4
subsets. Final-day scenarios (synthetic days built from practice shapes):
an explosive 400k day 0.192 (v5-ship: 0.212; v4: 0.332), a strong 400k
day 0.216 (v5-ship: 0.215; v4: 0.232), a flat 1M day 0.101 (v5-ship:
0.103; v4: 0.102), a crater 1M day 0.155 (v5-ship: 0.155; v4: 0.158).
Deterministic, offline, runs in under a second per case.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

## License

MIT — see [LICENSE](LICENSE).
