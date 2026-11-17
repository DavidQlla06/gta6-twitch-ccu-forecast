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

The forecast is a **launch-shape library**: every comparable past launch in
the case contributes its release-day hourly curve, normalised by its own
hour-1 print. For each hour we fit a weighted regression of
log(viewers_h / viewers_1) on log(viewers_1) across the rolling-midnight
launches, and predict the target launch at its own hour-1 print. The spread
is the regression's residual scale with a prediction-interval widening, and
the quantiles are skew-adjusted (wider upper tail: launch days surprise to
the upside far more often than to the downside).

Only launches shaped by a rolling midnight-local unlock like GTA VI's count;
simultaneous global unlocks, early-access-contaminated launches, free-to-play
and slow-burn launches, and the target game's own pre-release history are
excluded. Weights favour console-only launches (x8: GTA VI is console-only) and
older launches (2.5x per year back: the 2020 Sony console launches are the
closest analogues for a Rockstar midnight rolling launch). The median is
shifted up by an amount growing with the hour (the late-day surge, when the
US wakes up, is systematically underpredicted by the shape library), and the
regression is never evaluated past ln(viewers_1) = 12.6 — GTA VI's hour-1
print will exceed every validated launch, and a linear slope extrapolated
past the data would predict a declining day, which cannot happen for a
rolling-midnight launch. The median is not smoothed over neighbouring hours
(iteration 3: smoothing blurred the sharp h5 jump and h12 crater the truth
actually has), and the upper tail is not widened (upper scale 1.0).

Local validation on the four practice cases: mean pinball loss **0.143**
(house baseline: 0.387; v2 entry: 0.156; v1 entry: 0.180). Leave-one-practice-
out: 0.162. Deterministic, offline, runs in under a second per case.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

## License

MIT — see [LICENSE](LICENSE).
